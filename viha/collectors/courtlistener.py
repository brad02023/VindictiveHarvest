from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed


class CourtListenerCollector(Collector):
    id = "viha.db.courtlistener"
    label = "CourtListener"
    blurb = "Federal opinions and dockets (RECAP)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("CourtListener skipped — need a name or org")
            return []
        log(f"CourtListener search: {query}")
        data = await fetch_json(
            client,
            "https://www.courtlistener.com/api/rest/v4/search/",
            params={"q": f'"{query}"', "type": "o", "order_by": "score desc"},
        )
        tokens = [t.lower() for t in query.split() if len(t) > 2]
        last = tokens[-1] if tokens else ""
        facts: list[Fact] = []
        for hit in (data.get("results") or [])[:12]:
            case_name = hit.get("caseName") or hit.get("caseNameFull") or "Opinion"
            snippet = (hit.get("snippet") or "")[:400]
            blob = f"{case_name} {snippet}".lower()
            if last and last not in blob:
                continue
            hits_tokens = sum(1 for t in tokens if t in blob)
            if tokens and hits_tokens < min(2, len(tokens)):
                continue
            court = hit.get("court") or hit.get("court_citation_string") or ""
            date = hit.get("dateFiled") or hit.get("dateArgued") or ""
            abs_url = hit.get("absolute_url") or ""
            url = f"https://www.courtlistener.com{abs_url}" if abs_url.startswith("/") else abs_url
            label = f"{case_name} · {court} · {date}".strip(" ·")
            facts.append(
                self.fact(
                    predicate="docket",
                    value=label,
                    section="legal",
                    confidence=0.55 if seed.full_name else 0.4,
                    url=url or "https://www.courtlistener.com/",
                    publisher="CourtListener",
                    raw=hit,
                    extra={"snippet": snippet, "docketNumber": hit.get("docketNumber")},
                    candidate=True,
                )
            )
        if not facts:
            log("CourtListener: no public hits")
        return facts
