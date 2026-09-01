from __future__ import annotations

import asyncio
import re
from html import unescape

from viha.collectors.base import Collector, LogFn, fetch_text
from viha.collectors.social_catalog import BROWSER_UA, platform_of
from viha.core.identity import extract_associates_from_text, extract_identity_from_text, name_matches_text
from viha.core.models import Fact, Seed
from viha.core.normalize import (
    email_local_part,
    name_search_variants,
    name_tokens,
    phone_digits_in_text,
    phone_search_forms,
    split_usernames,
)
from viha.core.people_html import html_to_plain, page_title, parse_people_index_html, publisher_from_url
from viha.core.searchutil import fetch_priority, is_fetchable_result, is_people_broker_url, unwrap_search_url, wayback_latest

PEOPLE_DORK_SITES = (
    "fastpeoplesearch.com",
    "truepeoplesearch.com",
    "intelius.com",
    "spokeo.com",
    "thatsthem.com",
)
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
    "open.spotify.com",
)

_RESULT_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_SNIP_RE = re.compile(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', re.I | re.S)
_BING_H2 = re.compile(
    r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_BING_SNIP = re.compile(
    r'class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return unescape(_TAG_RE.sub("", html or "")).strip()


def parse_ddg_html(html: str) -> list[tuple[str, str, str]]:
    links = _RESULT_RE.findall(html or "")
    if not links:
        links = re.findall(
            r'<a[^>]+rel="nofollow"[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            html or "",
            re.I | re.S,
        )
    snips = [_clean(s) for s in _SNIP_RE.findall(html or "")]
    rows: list[tuple[str, str, str]] = []
    for idx, (href, title_html) in enumerate(links[:8]):
        url = unwrap_search_url(unescape(href))
        if not url.startswith("http") or "duckduckgo.com" in url:
            continue
        title = _clean(title_html) or url
        snippet = snips[idx] if idx < len(snips) else ""
        rows.append((url, title, snippet))
    return rows


def parse_bing_html(html: str) -> list[tuple[str, str, str]]:
    text = unescape(html or "")
    snips = [_clean(s) for s in _BING_SNIP.findall(text)]
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for idx, match in enumerate(_BING_H2.finditer(text)):
        if len(rows) >= 8:
            break
        url = unwrap_search_url(match.group(1))
        if not url.startswith("http"):
            continue
        host = url.lower()
        if "bing.com/" in host or "microsoft.com/" in host:
            continue
        title = _clean(match.group(2))
        if not title:
            continue
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        snippet = snips[idx] if idx < len(snips) else ""
        rows.append((url, title, snippet))
    return rows


class WebSearchCollector(Collector):
    id = "viha.db.search"
    label = "Web search"
    blurb = "DuckDuckGo/Bing dorks, then GET viable result pages (Wayback if blocked)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        queries = _build_queries(seed)
        bing_qs = _bing_queries(seed)
        sem = asyncio.Semaphore(6)
        facts: list[Fact] = []
        seen_urls: set[tuple[str, str, str]] = set()
        fetch_urls: list[str] = []

        async def run_engine(engine: str, q: str) -> tuple[list[Fact], list[str]]:
            log(f"{engine} search: {q}")
            async with sem:
                try:
                    if engine == "Bing":
                        status, _url, html = await fetch_text(
                            client,
                            "https://www.bing.com/search",
                            params={"q": q},
                            headers={"User-Agent": BROWSER_UA, "Accept-Language": "en-US,en;q=0.9"},
                        )
                    else:
                        status, _url, html = await fetch_text(
                            client,
                            "https://html.duckduckgo.com/html/",
                            params={"q": q},
                            headers={"User-Agent": BROWSER_UA},
                        )
                except Exception as exc:
                    log(f"{engine} search failed ({q}): {exc}")
                    return [], []
            if status >= 400:
                log(f"{engine} search HTTP {status} for {q}")
                return [], []
            rows = parse_bing_html(html) if engine == "Bing" else parse_ddg_html(html)
            return _facts_from_rows(self, q, seed, rows, engine)

        jobs = [("DuckDuckGo", q) for q in queries] + [("Bing", q) for q in bing_qs]
        for bundle, urls in await asyncio.gather(*(run_engine(engine, q) for engine, q in jobs)):
            for fact in bundle:
                key = (fact.source.url, fact.predicate, fact.value.lower())
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                facts.append(fact)
            fetch_urls.extend(urls)

        page_facts = await _fetch_result_pages(
            self, client, seed, sorted(_uniq(fetch_urls), key=fetch_priority)[:20], log
        )
        for fact in page_facts:
            key = (fact.source.url, fact.predicate, fact.value.lower())
            if key in seen_urls:
                continue
            seen_urls.add(key)
            facts.append(fact)
        if not facts:
            log("Web search: no indexed hits")
        return facts


def _build_queries(seed: Seed) -> list[str]:
    queries: list[str] = []
    for name in name_search_variants(seed.full_name):
        quoted = f'"{name.strip()}"'
        queries.append(quoted)
        if seed.city:
            queries.append(f"{quoted} {seed.city}")
        queries.append(f'{quoted} (age OR born OR "date of birth")')
        queries.append(f"{quoted} (court OR docket OR charged OR indictment)")
        place = " ".join(x for x in (seed.city, seed.state) if x).strip()
        if place:
            queries.append(f"{quoted} {place} (property OR assessor OR mortgage OR deed)")
    if seed.email.strip():
        queries.append(seed.email.strip())
    if seed.phone.strip():
        queries.extend(phone_search_forms(seed.phone)[:3])
    if seed.org.strip():
        queries.append(f'"{seed.org.strip()}"')
    for handle in split_usernames(seed.username):
        queries.append(f'"{handle}"')
    queries.extend(_site_queries(seed))
    return _uniq(queries)


def _bing_queries(seed: Seed) -> list[str]:
    """Bing still indexes people-search titles that DuckDuckGo dropped."""
    queries: list[str] = []
    for name in name_search_variants(seed.full_name):
        quoted = f'"{name.strip()}"'
        queries.append(quoted)
        queries.append(f'{quoted} (age OR born OR "date of birth")')
    queries.extend(phone_search_forms(seed.phone)[:3])
    queries.extend(_people_dork_queries(seed))
    return _uniq(queries)


def _people_dork_queries(seed: Seed) -> list[str]:
    """site: dorks for people-index hosts. Run on Bing; Google HTML is not a public API."""
    queries: list[str] = []
    names = [f'"{n.strip()}"' for n in name_search_variants(seed.full_name) if n.strip()]
    phones = phone_search_forms(seed.phone)[:3]
    for site in PEOPLE_DORK_SITES:
        for quoted in names:
            queries.append(f"site:{site} {quoted}")
        if phones:
            queries.append(f"site:{site} {phones[2] if len(phones) > 2 else phones[0]}")
    return queries


def _uniq(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _site_queries(seed: Seed) -> list[str]:
    queries: list[str] = []
    name = seed.full_name.strip()
    local = email_local_part(seed.email)
    handles = split_usernames(seed.username)
    for site in SITE_TARGETS:
        token = local if local and len(local) >= 5 else (f'"{name}"' if name else "")
        if token:
            queries.append(f"site:{site} {token}")
        for handle in handles:
            queries.append(f'site:{site} "{handle}"')
    if name:
        queries.append(f'"{name}" (discord OR steam OR instagram OR facebook OR github OR spotify)')
    return queries


def _name_in_text(text: str, seed: Seed) -> bool:
    return name_matches_text(text, seed)


def _relevant(title: str, url: str, query: str, seed: Seed) -> bool:
    blob = f"{title} {url}".lower()
    skip = (
        "accounts.google.com",
        "support.google.com/mail",
        "numlookup.com",
        "robokiller.com",
        "thisnumber.com",
        "411.com",
        "numtrace.com",
        "numberguru.com",
        "whitepages.com/white-pages",
    )
    if any(s in blob for s in skip) and not _name_in_text(title, seed):
        return False
    if seed.phone and phone_digits_in_text(seed.phone, f"{title} {url}") and is_people_broker_url(url):
        return True
    if "site:" in query.lower() or query.lower().endswith((" discord", " steam", " instagram", " facebook")):
        plat = platform_of(url)
        local = email_local_part(seed.email)
        if plat and local and local in blob:
            return True
        if plat and any(h.lower() in blob for h in split_usernames(seed.username)):
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
    if seed.phone and phone_digits_in_text(seed.phone, title) and _name_in_text(title, seed):
        return True
    return False


def _facts_from_rows(
    collector: WebSearchCollector,
    query: str,
    seed: Seed,
    rows: list[tuple[str, str, str]],
    engine: str,
) -> tuple[list[Fact], list[str]]:
    found: list[Fact] = []
    fetch: list[str] = []
    for href, title, snippet in rows:
        blob = f"{title} {snippet}".strip()
        if not _relevant(title, href, query, seed) and not _relevant(blob, href, query, seed):
            continue
        platform = platform_of(href)
        section = "social" if platform else "web"
        predicate = "username" if platform else "web_mention"
        name_hit = _name_in_text(title, seed)
        phone_hit = bool(seed.phone) and phone_digits_in_text(seed.phone, f"{title} {href}")
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
            collector.fact(
                predicate=predicate,
                value=title,
                section=section,
                confidence=conf,
                url=href,
                publisher=engine,
                raw={"query": query, "title": title, "snippet": snippet},
                extra={
                    "platform": platform,
                    "query": query,
                    "title": title,
                    "snippet": snippet,
                    "via": "site-search" if "site:" in query else "search",
                },
                candidate=conf < 0.7,
            )
        )
        found.extend(_extract_people_title(collector, f"{blob} {href}", href, seed, engine, phone_hit))
        if is_fetchable_result(href):
            fetch.append(href)
    return found, fetch


def _extract_people_title(
    collector: WebSearchCollector,
    title: str,
    url: str,
    seed: Seed,
    engine: str = "DuckDuckGo",
    phone_hit: bool | None = None,
) -> list:
    facts = []
    if phone_hit is None:
        phone_hit = bool(seed.phone) and phone_digits_in_text(seed.phone, title)
    for item in extract_identity_from_text(title, seed):
        pred = item["predicate"]
        conf = {"aka": 0.62, "age": 0.55, "dob": 0.5, "location": 0.55, "address": 0.42}.get(pred, 0.45)
        if phone_hit:
            conf = min(0.78, conf + 0.12)
        facts.append(
            collector.fact(
                predicate=pred,
                value=item["value"],
                section="identity",
                confidence=conf,
                url=url,
                publisher="Indexed people search",
                extra={"via": "web title", "engine": engine, "phone_match": phone_hit},
                candidate=True,
            )
        )
    for item in extract_associates_from_text(title, seed):
        pred = item["predicate"]
        conf = 0.52
        if phone_hit:
            conf = min(0.7, conf + 0.12)
        facts.append(
            collector.fact(
                predicate=pred,
                value=item["value"],
                section=item.get("section") or "contact",
                confidence=conf,
                url=url,
                publisher="Indexed people search",
                extra={"via": "web title", "engine": engine, "associate": True, "phone_match": phone_hit},
                candidate=True,
            )
        )
    return facts


def _page_blocked(status: int, html: str) -> bool:
    if status == 0 or status >= 400:
        return True
    title = page_title(html).lower()
    if any(n in title for n in ("just a moment", "security challenge", "access denied", "attention required")):
        return True
    head = (html or "")[:2500].lower()
    return "cf-browser-verification" in head or "checking your browser" in head


def facts_from_result_html(
    collector: WebSearchCollector,
    html: str,
    url: str,
    seed: Seed,
    engine: str = "search-fetch",
) -> list[Fact]:
    """Parse a fetched search-result page the same way as a saved people-index HTML."""
    host = (url or "").lower()
    people_host = is_people_broker_url(url) or any(
        h in host
        for h in ("fastpeoplesearch", "truepeoplesearch", "intelius", "thatsthem", "clustrmaps", "spokeo")
    )
    facts: list[Fact] = []
    if people_host:
        page = parse_people_index_html(html, seed, url)
        dest = page.url or url
        for item in page.items:
            extra = dict(item.get("extra") or {})
            extra["via"] = "search-fetch"
            extra["engine"] = engine
            facts.append(
                collector.fact(
                    predicate=item["predicate"],
                    value=item["value"],
                    section=item["section"],
                    confidence=float(item["confidence"]),
                    url=extra.get("profile_url") or dest,
                    publisher=page.publisher or publisher_from_url(dest),
                    extra=extra,
                    candidate=True,
                    raw=page.title,
                )
            )
        return facts
    title = page_title(html)
    plain = html_to_plain(html)[:16000]
    return _extract_people_title(collector, f"{title} {plain} {url}".strip(), url, seed, engine)


async def _fetch_result_pages(
    collector: WebSearchCollector,
    client,
    seed: Seed,
    urls: list[str],
    log: LogFn,
) -> list[Fact]:
    if not urls:
        return []
    headers = {"User-Agent": BROWSER_UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
    sem = asyncio.Semaphore(4)
    out: list[Fact] = []

    async def one(url: str) -> list[Fact]:
        log(f"Search fetch: {url}")
        html = ""
        status = 0
        dest = url
        async with sem:
            try:
                status, dest, html = await fetch_text(client, url, headers=headers)
            except Exception as exc:
                log(f"Search fetch failed ({url}): {exc}")
        if _page_blocked(status, html):
            archive = wayback_latest(url)
            log(f"Search fetch blocked ({status}) — Wayback {archive}")
            async with sem:
                try:
                    status, dest, html = await fetch_text(client, archive, headers=headers)
                except Exception as exc:
                    log(f"Wayback fetch failed: {exc}")
                    return []
            if _page_blocked(status, html):
                log(f"Wayback also blocked HTTP {status}")
                return []
        return facts_from_result_html(collector, html, dest or url, seed)

    for bundle in await asyncio.gather(*(one(u) for u in urls)):
        out.extend(bundle)
    if out:
        log(f"Search fetch: {len(out)} facts from {len(urls)} page(s)")
    return out
