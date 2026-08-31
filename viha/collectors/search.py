from __future__ import annotations

import asyncio
import re
from html import unescape

from viha.collectors.base import Collector, LogFn, fetch_text
from viha.collectors.social_catalog import BROWSER_UA, platform_of
from viha.core.models import Fact, Seed
from viha.core.normalize import email_local_part, name_tokens, phone_search_forms
from viha.core.searchutil import unwrap_search_url

SITE_TARGETS = (
    "instagram.com",
    "facebook.com",
    "steamcommunity.com",
    "github.com",
    "discord.com",
    "tiktok.com",
    "snapchat.com",
    "linkedin.com",
    "linktr.ee",
)

_RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_SNIP_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return unescape(_TAG_RE.sub("", html or "")).strip()


class WebSearchCollector(Collector):
    id = "viha.db.search"
    label = "Web search"
    blurb = "DuckDuckGo HTML index of public pages"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        queries: list[str] = []
        if seed.full_name.strip():
            queries.append(f'"{seed.full_name.strip()}"')
            if seed.city:
                queries.append(f'"{seed.full_name.strip()}" {seed.city}')
        if seed.email.strip():
            queries.append(seed.email.strip())
        if seed.phone.strip():
            queries.extend(phone_search_forms(seed.phone)[:3])
        if seed.org.strip():
            queries.append(f'"{seed.org.strip()}"')
        if seed.username.strip():
            queries.append(seed.username.strip())
        queries.extend(_site_queries(seed))

        seen_q: set[str] = set()
        uniq = []
        for q in queries:
            if q not in seen_q:
                seen_q.add(q)
                uniq.append(q)

        sem = asyncio.Semaphore(6)
        facts: list[Fact] = []
        seen_urls: set[str] = set()

        async def run_query(q: str) -> list[Fact]:
            log(f"Web search: {q}")
            async with sem:
                try:
                    status, url, html = await fetch_text(
                        client,
                        "https://html.duckduckgo.com/html/",
                        params={"q": q},
                        headers={"User-Agent": BROWSER_UA},
                    )
                except Exception as exc:
                    log(f"Web search failed ({q}): {exc}")
                    return []
            if status >= 400:
                log(f"Web search HTTP {status} for {q}")
                return []
            links = _RESULT_RE.findall(html)
            if not links:
                links = re.findall(
                    r'<a[^>]+rel="nofollow"[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                    html,
                    re.I | re.S,
                )
            found: list[Fact] = []
            for href, title_html in links[:8]:
                href = unwrap_search_url(unescape(href))
                if not href.startswith("http") or "duckduckgo.com" in href:
                    continue
                title = _clean(title_html) or href
                if not _relevant(title, href, q, seed):
                    continue
                platform = platform_of(href)
                section = "social" if platform else "web"
                predicate = "username" if platform else "web_mention"
                name_hit = _name_in_text(title, seed)
                phone_hit = any(
                    p.replace("+", "") in title.replace("-", "").replace(" ", "")
                    for p in phone_search_forms(seed.phone)[:3]
                ) if seed.phone else False
                local = email_local_part(seed.email)
                conf = 0.35
                if name_hit and phone_hit:
                    conf = 0.78
                elif platform and local and local in href.lower():
                    conf = 0.7
                elif platform and name_hit:
                    conf = 0.58
                elif seed.email and seed.email.lower() in (title + href).lower():
                    conf = 0.55
                found.append(
                    self.fact(
                        predicate=predicate,
                        value=title,
                        section=section,
                        confidence=conf,
                        url=href,
                        publisher="DuckDuckGo",
                        raw={"query": q, "title": title},
                        extra={"platform": platform, "query": q, "via": "site-search" if "site:" in q else "search"},
                        candidate=conf < 0.7,
                    )
                )
                found.extend(_extract_people_title(self, title, href, seed))
            return found

        for bundle in await asyncio.gather(*(run_query(q) for q in uniq)):
            for fact in bundle:
                if fact.source.url in seen_urls:
                    continue
                seen_urls.add(fact.source.url)
                facts.append(fact)
        if not facts:
            log("Web search: no indexed hits")
        return facts


def _site_queries(seed: Seed) -> list[str]:
    queries: list[str] = []
    name = seed.full_name.strip()
    local = email_local_part(seed.email)
    for site in SITE_TARGETS:
        token = local if local and len(local) >= 5 else (f'"{name}"' if name else "")
        if token:
            queries.append(f"site:{site} {token}")
    if name:
        queries.append(f'"{name}" (discord OR steam OR instagram OR facebook OR github)')
    return queries


def _name_in_text(text: str, seed: Seed) -> bool:
    tokens = name_tokens(seed.full_name)
    if not tokens:
        return False
    words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    if len(tokens) == 1:
        return tokens[0] in words
    return tokens[0] in words and tokens[-1] in words


def _relevant(title: str, url: str, query: str, seed: Seed) -> bool:
    blob = f"{title} {url}".lower()
    skip = (
        "accounts.google.com",
        "support.google.com/mail",
        "numlookup.com",
        "robokiller.com",
        "thisnumber.com",
        "truepeoplesearch.com/reverse-phone",
        "peoplefinders.com/reverse-phone",
        "411.com",
        "numtrace.com",
        "numberguru.com",
        "spokeo.com/reverse-phone",
        "whitepages.com/white-pages",
    )
    if any(s in blob for s in skip) and not _name_in_text(title, seed):
        return False
    if "site:" in query.lower() or query.lower().endswith((" discord", " steam", " instagram", " facebook")):
        plat = platform_of(url)
        local = email_local_part(seed.email)
        if plat and local and local in blob:
            return True
        if plat and seed.username and seed.username.lower() in blob:
            return True
        if plat and _name_in_text(title + " " + url, seed):
            return True
        if plat and local and local in url.lower():
            return True
        tokens = name_tokens(seed.full_name)
        if plat and tokens and tokens[-1] in blob and (not tokens or tokens[0] in blob or local in blob):
            return True
    if seed.full_name and _name_in_text(title, seed):
        return True
    if seed.email and seed.email.lower() in blob:
        return True
    local = seed.email.split("@", 1)[0].lower() if "@" in seed.email else ""
    if local and len(local) > 4 and local in blob:
        return True
    if seed.phone:
        digits = "".join(ch for ch in seed.phone if ch.isdigit())[-10:]
        compact = "".join(ch for ch in title if ch.isdigit())
        if digits and digits in compact and _name_in_text(title, seed):
            return True
    return False


def _extract_people_title(collector: WebSearchCollector, title: str, url: str, seed: Seed) -> list:
    facts = []
    m = re.search(r"Owner\s+(.+?),\s*Age\s+(\d+)\s+in\s+(.+)", title, re.I)
    if not m:
        return facts
    aka, age, place = m.group(1).strip(), m.group(2), m.group(3).strip(" .")
    place = re.sub(r"\.{2,}$", "", place).strip()
    facts.append(
        collector.fact(
            predicate="aka",
            value=aka,
            section="identity",
            confidence=0.62,
            url=url,
            publisher="Indexed people search",
            extra={"via": "web title"},
            candidate=True,
        )
    )
    facts.append(
        collector.fact(
            predicate="age",
            value=age,
            section="identity",
            confidence=0.55,
            url=url,
            publisher="Indexed people search",
            candidate=True,
        )
    )
    if len(place) >= 6:
        facts.append(
            collector.fact(
                predicate="location",
                value=place,
                section="identity",
                confidence=0.55,
                url=url,
                publisher="Indexed people search",
                candidate=True,
            )
        )
    return facts

