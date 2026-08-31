from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed


class EdgarCollector(Collector):
    id = "viha.db.edgar"
    label = "SEC EDGAR"
    blurb = "Company filings and officer mentions"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("EDGAR skipped — need a name or org")
            return []
        log(f"EDGAR search: {query}")
        headers = {"User-Agent": "Vindictive Harvest VIHA local-research@localhost"}
        data = await fetch_json(
            client,
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": f'"{query}"', "dateRange": "custom", "startdt": "2000-01-01"},
            headers=headers,
        )
        hits = (data.get("hits") or {}).get("hits") or []
        facts: list[Fact] = []
        for hit in hits[:12]:
            src = hit.get("_source") or {}
            entity = src.get("entity_name") or src.get("display_names") or "Filing"
            if isinstance(entity, list):
                entity = ", ".join(str(x) for x in entity[:3])
            form = src.get("form") or ""
            filed = src.get("file_date") or ""
            adsh = src.get("adsh") or hit.get("_id") or ""
            url = f"https://www.sec.gov/edgar/search/#/q={query}"
            facts.append(
                self.fact(
                    predicate="filing",
                    value=f"{entity} · {form} · {filed}".strip(" ·"),
                    section="business",
                    confidence=0.5,
                    url=url,
                    publisher="SEC EDGAR",
                    raw={"id": adsh, "source": src},
                    candidate=True,
                )
            )
        if not facts:
            log("EDGAR: no public hits")
        return facts
