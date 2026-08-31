from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed


class OpenCorporatesCollector(Collector):
    id = "viha.db.opencorp"
    label = "OpenCorporates"
    blurb = "Company and officer registry search"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("OpenCorporates skipped — need a name or org")
            return []
        facts: list[Fact] = []
        log(f"OpenCorporates officers: {query}")
        try:
            data = await fetch_json(
                client,
                "https://api.opencorporates.com/v0.4/officers/search",
                params={"q": query, "per_page": 5},
            )
            officers = ((data.get("results") or {}).get("officers")) or []
            for wrap in officers[:8]:
                officer = wrap.get("officer") or wrap
                name = officer.get("name") or query
                company = ((officer.get("company") or {}).get("name")) or ""
                pos = officer.get("position") or ""
                url = officer.get("opencorporates_url") or "https://opencorporates.com/"
                facts.append(
                    self.fact(
                        predicate="officer",
                        value=f"{name} · {pos} · {company}".strip(" ·"),
                        section="business",
                        confidence=0.48,
                        url=url,
                        publisher="OpenCorporates",
                        raw=officer,
                        candidate=True,
                    )
                )
        except Exception as exc:
            if "401" in str(exc):
                log("OpenCorporates officers need OPENCORPORATES_API_TOKEN — skipped")
            else:
                log(f"OpenCorporates officers: {exc}")

        org = seed.org.strip() or query
        log(f"OpenCorporates companies: {org}")
        try:
            data = await fetch_json(
                client,
                "https://api.opencorporates.com/v0.4/companies/search",
                params={"q": org, "per_page": 5},
            )
            companies = ((data.get("results") or {}).get("companies")) or []
            for wrap in companies[:8]:
                company = wrap.get("company") or wrap
                name = company.get("name") or org
                jur = company.get("jurisdiction_code") or ""
                url = company.get("opencorporates_url") or "https://opencorporates.com/"
                facts.append(
                    self.fact(
                        predicate="company",
                        value=f"{name} ({jur})".strip(),
                        section="business",
                        confidence=0.45,
                        url=url,
                        publisher="OpenCorporates",
                        raw=company,
                        candidate=True,
                    )
                )
        except Exception as exc:
            if "401" in str(exc):
                log("OpenCorporates companies need OPENCORPORATES_API_TOKEN — skipped")
            else:
                log(f"OpenCorporates companies: {exc}")

        if not facts:
            log("OpenCorporates: no public hits (rate limit or empty)")
        return facts
