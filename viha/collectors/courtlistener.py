from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.identity import likely_criminal
from viha.core.models import Fact, Seed


class CourtListenerCollector(Collector):
    id = "viha.db.courtlistener"
    label = "CourtListener"
    blurb = "Federal opinions and RECAP dockets"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("CourtListener skipped — need a name or org")
            return []
        facts: list[Fact] = []
        facts.extend(await self._search(client, log, query, "o", "opinion", seed))
        facts.extend(await self._search(client, log, query, "d", "docket", seed))
        if not facts:
            log("CourtListener: no public hits")
        return facts

    async def _search(self, client, log: LogFn, query: str, kind: str, label: str, seed: Seed) -> list[Fact]:
        log(f"CourtListener {label} search: {query}")
        try:
            data = await fetch_json(
                client,
                "https://www.courtlistener.com/api/rest/v4/search/",
                params={"q": f'"{query}"', "type": kind, "order_by": "score desc"},
            )
        except Exception as exc:
            log(f"CourtListener {label}: {exc}")
            return []
        tokens = [t.lower() for t in query.split() if len(t) > 2]
        last = tokens[-1] if tokens else ""
        facts: list[Fact] = []
        for hit in (data.get("results") or [])[:12]:
            case_name = hit.get("caseName") or hit.get("caseNameFull") or hit.get("docketNumber") or "Matter"
            snippet = (hit.get("snippet") or "")[:400]
            blob = f"{case_name} {snippet}".lower()
            if last and last not in blob:
                continue
            hits_tokens = sum(1 for t in tokens if t in blob)
            if tokens and hits_tokens < min(2, len(tokens)):
                continue
            court = hit.get("court") or hit.get("court_citation_string") or ""
            filed = hit.get("dateFiled") or hit.get("dateArgued") or hit.get("dateTerminated") or ""
            abs_url = hit.get("absolute_url") or ""
            url = f"https://www.courtlistener.com{abs_url}" if abs_url.startswith("/") else abs_url
            criminal = likely_criminal(f"{case_name} {snippet}")
            value = f"{case_name} · {court} · {filed}".strip(" ·")
            facts.append(
                self.fact(
                    predicate="charge" if criminal else "docket",
                    value=value,
                    section="legal",
                    confidence=0.58 if seed.full_name else 0.42,
                    url=url or "https://www.courtlistener.com/",
                    publisher="CourtListener",
                    raw=hit,
                    extra={
                        "snippet": snippet,
                        "docketNumber": hit.get("docketNumber"),
                        "kind": label,
                        "likely_criminal": criminal,
                    },
                    candidate=True,
                )
            )
        log(f"CourtListener {label}: {len(facts)} hit(s)")
        return facts
