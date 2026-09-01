from __future__ import annotations

from viha.collectors.base import Collector, LogFn
from viha.core.models import Fact, Seed
from viha.core.handles import path_seg, shape_handle
from viha.core.normalize import email_local_part, split_usernames, username_candidates


class WaybackCollector(Collector):
    id = "viha.db.wayback"
    label = "Wayback"
    blurb = "Internet Archive CDX snapshots of likely profile URLs"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        urls: list[str] = []
        handles = split_usernames(seed.username) + username_candidates(seed.full_name, seed.email)[:4]
        local = email_local_part(seed.email)
        if local and local not in handles:
            handles.insert(0, local)
        seen_h: set[str] = set()
        for h in handles:
            if not h or h in seen_h:
                continue
            seen_h.add(h)
            def first(style: str) -> str:
                forms = shape_handle(h, style)
                return path_seg(forms[0]) if forms else ""

            gh, ig, tw, st, tt = first("github"), first("instagram"), first("x"), first("steam"), first("tiktok")
            if gh:
                urls.append(f"https://github.com/{gh}")
            if ig:
                urls.append(f"https://www.instagram.com/{ig}/")
            if tw:
                urls.extend([f"https://twitter.com/{tw}", f"https://x.com/{tw}"])
            if st:
                urls.append(f"https://steamcommunity.com/id/{st}")
            if tt:
                urls.append(f"https://www.tiktok.com/@{tt}")
        if seed.email:
            urls.append(f"https://gravatar.com/{email_local_part(seed.email)}")
        facts: list[Fact] = []
        log(f"Wayback CDX: {min(len(urls), 6)} profile URLs")
        for url in urls[:6]:
            try:
                r = await client.get(
                    "https://web.archive.org/cdx/search/cdx",
                    params={"url": url, "output": "json", "limit": 2, "filter": "statuscode:200"},
                    timeout=8.0,
                )
                r.raise_for_status()
                rows = r.json()
            except Exception as exc:
                log(f"Wayback skip {url.split('/')[2] if '//' in url else url}: {exc or 'timeout'}")
                continue
            if not isinstance(rows, list) or len(rows) < 2:
                continue
            latest = rows[1]
            ts = latest[1] if len(latest) > 1 else ""
            orig = latest[2] if len(latest) > 2 else url
            archive = f"https://web.archive.org/web/{ts}/{orig}" if ts else f"https://web.archive.org/web/*/{url}"
            facts.append(
                self.fact(
                    predicate="wayback",
                    value=f"{orig} @ {ts}",
                    section="web",
                    confidence=0.6,
                    url=archive,
                    publisher="Internet Archive",
                    raw=latest,
                    extra={"timestamp": ts},
                    candidate=True,
                )
            )
        if not facts:
            log("Wayback: no public snapshots")
        return facts
