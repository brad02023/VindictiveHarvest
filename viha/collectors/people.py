from __future__ import annotations

from urllib.parse import quote_plus
import re

from viha.collectors.base import Collector, LogFn
from viha.collectors.social_catalog import BROWSER_UA
from viha.core.models import Case, Fact, Seed, Source
from viha.core.normalize import name_tokens, normalize_phone
from viha.core.people_html import detail_profile_urls, facts_from_people_html, publisher_from_url
from viha.core.searchutil import fetch_priority, is_people_broker_url, wayback_identity, wayback_latest

BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def people_index_urls(seed: Seed) -> list[tuple[str, str]]:
    """Public people-index pages (GET). Name-only indexes are skipped (too many collisions)."""
    out: list[tuple[str, str]] = []
    tokens = name_tokens(seed.full_name)
    city = re.sub(r"[^a-z]+", "-", (seed.city or "").lower()).strip("-")
    state = (seed.state or "").strip().lower()
    if len(tokens) >= 2 and city and state:
        slug = f"{tokens[0]}-{tokens[-1]}"
        out.append(
            (
                "FastPeopleSearch name+city",
                f"https://www.fastpeoplesearch.com/name/{slug}_{city}-{state}",
            )
        )
        qn = quote_plus(seed.full_name.strip())
        place = quote_plus(" ".join(p for p in (seed.city, (seed.state or "").upper()) if p))
        out.append(
            (
                "TruePeopleSearch name+place",
                f"https://www.truepeoplesearch.com/results?name={qn}&citystatezip={place}",
            )
        )
    e164 = normalize_phone(seed.phone)
    if e164.startswith("+1") and len(e164) == 12:
        d = e164[2:]
        dashed = f"{d[:3]}-{d[3:6]}-{d[6:]}"
        out.append(("FastPeopleSearch phone", f"https://www.fastpeoplesearch.com/{dashed}"))
        out.append(("Intelius phone", f"https://www.intelius.com/reverse-phone-lookup/{dashed}"))
    return out


def people_index_link_facts(seed: Seed, collector: str = "viha.db.people") -> list[Fact]:
    """Always-visible FastPeopleSearch / Intelius rows (GET may 403; operator opens the URL)."""
    out: list[Fact] = []
    for label, url in people_index_urls(seed):
        out.append(
            Fact(
                predicate="people_index",
                value=label,
                section="identity",
                confidence=0.4,
                source=Source(
                    publisher="People index",
                    url=url,
                    collector=collector,
                    note="Open in a browser if harvest 403s, save HTML, then IMPORT PEOPLE HTML",
                ),
                extra={"via": "people-index-link"},
                candidate=True,
            )
        )
    return out


def _page_blocked(status: int, html: str) -> bool:
    if status == 0 or status >= 400:
        return True
    head = (html or "")[:2500].lower()
    title = ""
    low = (html or "")[:4000].lower()
    if "<title" in low:
        start = low.find("<title")
        end = low.find("</title>", start)
        title = low[start:end] if end > start else ""
    needles = (
        "just a moment",
        "security challenge",
        "cf-browser-verification",
        "checking your browser",
        "attention required",
        "access denied",
    )
    return any(n in head or n in title for n in needles)


def _url_key(url: str) -> str:
    return (url or "").split("?")[0].rstrip("/").lower()


async def wayback_cdx_url(client, url: str, headers: dict[str, str], log: LogFn) -> str:
    """Latest 200 snapshot as an identity (toolbar-free) Wayback URL."""
    try:
        r = await client.get(
            "https://web.archive.org/cdx/search/cdx",
            params={
                "url": url,
                "output": "json",
                "filter": "statuscode:200",
                "limit": 1,
                "fl": "timestamp,original",
                "fastLatest": "true",
            },
            headers=headers,
            timeout=20.0,
        )
        data = r.json()
        if isinstance(data, list) and len(data) >= 2 and len(data[1]) >= 2:
            return wayback_identity(str(data[1][0]), str(data[1][1]))
    except Exception as exc:
        log(f"Wayback CDX failed: {exc}")
    return ""


async def fetch_people_html(client, url: str, headers: dict[str, str], log: LogFn) -> tuple[str, str]:
    """GET a people-index URL; Wayback CDX then /web/2/ if live 403/challenge."""
    try:
        r = await client.get(url, headers=headers, timeout=16.0, follow_redirects=True)
        status, dest, html = r.status_code, str(r.url), r.text or ""
    except Exception as exc:
        log(f"People index fetch failed ({url}): {exc}")
        status, dest, html = 0, url, ""
    if not _page_blocked(status, html):
        return dest, html
    archives: list[str] = []
    cdx = await wayback_cdx_url(client, url, headers, log)
    if cdx:
        archives.append(cdx)
    latest = wayback_latest(url)
    if latest not in archives:
        archives.append(latest)
    for archive in archives:
        log(f"People index blocked ({status}) — Wayback {archive}")
        try:
            r = await client.get(archive, headers=headers, timeout=22.0, follow_redirects=True)
            if not _page_blocked(r.status_code, r.text or ""):
                return str(r.url), r.text or ""
            log(f"Wayback also blocked HTTP {r.status_code}")
        except Exception as exc:
            log(f"Wayback fetch failed: {exc}")
    return "", ""


def discovered_people_urls(case: Case) -> list[str]:
    """People-broker URLs already sitting on facts (Bing hits, profile links)."""
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for fact in case.facts:
        candidates = [fact.source.url, (fact.extra or {}).get("profile_url")]
        val = (fact.value or "").strip()
        if val.startswith("http"):
            candidates.append(val)
        for url in candidates:
            if not url or not str(url).startswith("http"):
                continue
            raw = str(url)
            low = raw.lower()
            if any(n in low for n in ("web.archive.org", "bing.com/", "duckduckgo.com")):
                continue
            if not is_people_broker_url(raw) and "_id_g" not in low:
                continue
            key = _url_key(raw)
            if key in seen:
                continue
            seen.add(key)
            scored.append((fetch_priority(raw), raw))
    scored.sort(key=lambda item: item[0])
    return [u for _, u in scored][:16]


async def parse_people_queue(
    seed: Seed,
    client,
    log: LogFn,
    queued: list[tuple[str, str]],
    *,
    collector: str,
    follow_cap: int = 4,
) -> list[Fact]:
    facts: list[Fact] = []
    seen: set[str] = set()
    followed = 0
    while queued:
        label, url = queued.pop(0)
        key = _url_key(url)
        if key in seen:
            continue
        seen.add(key)
        log(f"People index: {label}")
        dest, html = await fetch_people_html(client, url, BROWSER_HEADERS, log)
        if not html:
            continue
        batch = facts_from_people_html(html, seed, dest or url, collector=collector)
        facts.extend(batch)
        parsed = sum(1 for f in batch if f.predicate not in {"web_mention", "people_index"})
        if parsed:
            log(f"People index {label}: {parsed} facts")
        else:
            log(f"People index {label}: page loaded but no matching name/phone facts")
        if followed >= follow_cap:
            continue
        for detail in detail_profile_urls(html, seed, dest or url):
            dkey = _url_key(detail)
            if dkey in seen:
                continue
            queued.append((f"{publisher_from_url(detail)} profile", detail))
            followed += 1
            facts.append(
                Fact(
                    predicate="people_index",
                    value=f"{publisher_from_url(detail)} profile",
                    section="identity",
                    confidence=0.55,
                    source=Source(
                        publisher=publisher_from_url(detail),
                        url=detail,
                        collector=collector,
                        note="Follow-on person page from reverse-phone / name listing",
                    ),
                    extra={"via": "people-index-detail", "detail": True},
                    candidate=True,
                )
            )
    return facts


async def fetch_discovered_people_pages(case: Case, client, log: LogFn) -> list[Fact]:
    """GET people-broker URLs found by search (not just the seed reverse-phone listing)."""
    html_via = {"people-index", "search-fetch", "people-html-import", "people-index-detail"}
    parsed_keys = {
        _url_key(f.source.url)
        for f in case.facts
        if f.predicate in {"age", "dob", "address", "job"} and (f.extra or {}).get("via") in html_via
    }
    urls = [u for u in discovered_people_urls(case) if _url_key(u) not in parsed_keys]
    if not urls:
        return []
    log(f"People index: fetching {len(urls)} discovered page(s)")
    queued = [(publisher_from_url(u), u) for u in urls]
    return await parse_people_queue(case.seed, client, log, queued, collector="viha.db.people")


class PeopleIndexCollector(Collector):
    id = "viha.db.people"
    label = "People index"
    blurb = "Public people-search pages: age/city when the seed phone or name is on the page"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        urls = people_index_urls(seed)
        if not urls:
            log("People index skipped — need a US phone or name with city/state")
            return []
        facts: list[Fact] = list(people_index_link_facts(seed, self.id))
        facts.extend(
            await parse_people_queue(seed, client, log, list(urls), collector=self.id)
        )
        if not any(f.predicate not in {"people_index", "web_mention"} for f in facts):
            log("People index: no parsed records. Open the profile URL, Ctrl+S, IMPORT PEOPLE HTML.")
        return facts
