from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed


class WikidataCollector(Collector):
    id = "viha.db.wikidata"
    label = "Wikidata"
    blurb = "Notable people and organization IDs"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("Wikidata skipped — need a name or org")
            return []
        log(f"Wikidata search: {query}")
        data = await fetch_json(
            client,
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": 8,
            },
        )
        facts: list[Fact] = []
        for hit in data.get("search") or []:
            label = hit.get("label") or query
            desc = hit.get("description") or ""
            qid = hit.get("id") or ""
            url = hit.get("concepturi") or f"https://www.wikidata.org/wiki/{qid}"
            facts.append(
                self.fact(
                    predicate="wikidata",
                    value=f"{label} — {desc}".strip(" —"),
                    section="identity",
                    confidence=0.4,
                    url=url,
                    publisher="Wikidata",
                    raw=hit,
                    candidate=True,
                )
            )
        if not facts:
            log("Wikidata: no notable-entity hits")
        return facts
