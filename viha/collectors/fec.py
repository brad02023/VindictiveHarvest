from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.settings import load_settings


class FecCollector(Collector):
    id = "viha.db.fec"
    label = "FEC"
    blurb = "US campaign finance names (free DEMO_KEY)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip()
        if not query:
            log("FEC skipped — need a name")
            return []
        key = (load_settings().get("fec_api_key") or "DEMO_KEY").strip()
        log(f"FEC name search: {query}")
        try:
            data = await fetch_json(
                client,
                "https://api.open.fec.gov/v1/names/candidates/",
                params={"q": query, "api_key": key, "per_page": 5},
            )
        except Exception as exc:
            log(f"FEC: {exc}")
            return []
        facts: list[Fact] = []
        for hit in data.get("results") or []:
            name = hit.get("name") or query
            cid = hit.get("id") or ""
            office = hit.get("office_sought") or ""
            url = f"https://www.fec.gov/data/candidate/{cid}/" if cid else "https://www.fec.gov/data/"
            facts.append(
                self.fact(
                    predicate="campaign",
                    value=f"{name} · {office} · {cid}".strip(" ·"),
                    section="legal",
                    confidence=0.4,
                    url=url,
                    publisher="FEC",
                    raw=hit,
                    candidate=True,
                )
            )
        if not facts:
            log("FEC: no candidate-name hits")
        return facts
