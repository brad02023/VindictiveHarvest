from __future__ import annotations

import os

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed


class OpenSanctionsCollector(Collector):
    id = "viha.db.opensanctions"
    label = "OpenSanctions"
    blurb = "Sanctions, PEPs, and watchlists"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("OpenSanctions skipped — need a name or org")
            return []
        log(f"OpenSanctions search: {query}")
        key = os.environ.get("OPENSANCTIONS_API_KEY", "").strip()
        headers = {"Authorization": f"ApiKey {key}"} if key else {}
        try:
            data = await fetch_json(
                client,
                "https://api.opensanctions.org/search/default",
                params={"q": query, "limit": 8},
                headers=headers,
            )
        except Exception as exc:
            if "401" in str(exc):
                log("OpenSanctions needs OPENSANCTIONS_API_KEY — skipped")
                return []
            raise
        facts: list[Fact] = []
        for hit in data.get("results") or []:
            caption = hit.get("caption") or query
            schema = hit.get("schema") or "Entity"
            score = float(hit.get("score") or 0)
            datasets = ", ".join((hit.get("datasets") or [])[:4])
            ident = hit.get("id") or ""
            url = f"https://www.opensanctions.org/entities/{ident}" if ident else "https://www.opensanctions.org/"
            facts.append(
                self.fact(
                    predicate="watchlist",
                    value=f"{caption} · {schema} · {datasets}".strip(" ·"),
                    section="sanctions",
                    confidence=min(0.9, 0.35 + score / 100),
                    url=url,
                    publisher="OpenSanctions",
                    raw=hit,
                    candidate=score < 70,
                )
            )
        if not facts:
            log("OpenSanctions: no watchlist hits")
        return facts
