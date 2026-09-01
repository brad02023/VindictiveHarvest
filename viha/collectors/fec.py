from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.identity import name_matches_text
from viha.core.models import Fact, Seed
from viha.core.normalize import name_tokens
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
        facts.extend(await self._schedule_a(client, log, query, key))
        if not facts:
            log("FEC: no candidate or donor hits")
        return facts

    async def _schedule_a(self, client, log: LogFn, query: str, key: str) -> list[Fact]:
        tokens = name_tokens(query)
        alt = f"{tokens[-1]}, {tokens[0]}" if len(tokens) >= 2 else query
        log(f"FEC donor search: {alt}")
        try:
            data = await fetch_json(
                client,
                "https://api.open.fec.gov/v1/schedules/schedule_a/",
                params={
                    "contributor_name": alt,
                    "api_key": key,
                    "per_page": 8,
                    "sort": "-contribution_receipt_date",
                },
            )
        except Exception as exc:
            log(f"FEC donors: {exc}")
            return []
        facts: list[Fact] = []
        seen: set[str] = set()
        for hit in data.get("results") or []:
            name = (hit.get("contributor_name") or "").strip()
            if name and not name_matches_text(name.replace(",", " "), Seed(full_name=query)):
                continue
            city = (hit.get("contributor_city") or "").strip().title()
            state = (hit.get("contributor_state") or "").strip().upper()
            street = (hit.get("contributor_street_1") or "").strip()
            employer = (hit.get("contributor_employer") or "").strip()
            occupation = (hit.get("contributor_occupation") or "").strip()
            zipc = (hit.get("contributor_zip") or "").strip()[:5]
            url = "https://www.fec.gov/data/receipts/"
            place = ", ".join(p for p in (city, state) if p)
            if place and place.lower() not in seen:
                seen.add(place.lower())
                facts.append(
                    self.fact(
                        predicate="location",
                        value=place,
                        section="identity",
                        confidence=0.6,
                        url=url,
                        publisher="FEC",
                        raw=hit,
                        extra={"via": "schedule-a", "zip": zipc},
                        candidate=True,
                    )
                )
            if street:
                addr = ", ".join(p for p in (street, place, zipc) if p)
                if addr.lower() not in seen:
                    seen.add(addr.lower())
                    facts.append(
                        self.fact(
                            predicate="address",
                            value=addr,
                            section="identity",
                            confidence=0.55,
                            url=url,
                            publisher="FEC",
                            raw=hit,
                            extra={"via": "schedule-a"},
                            candidate=True,
                        )
                    )
            if employer and employer.lower() not in {"none", "not employed", "retired"}:
                if f"emp:{employer.lower()}" not in seen:
                    seen.add(f"emp:{employer.lower()}")
                    facts.append(
                        self.fact(
                            predicate="employer",
                            value=employer,
                            section="identity",
                            confidence=0.52,
                            url=url,
                            publisher="FEC",
                            candidate=True,
                        )
                    )
            if occupation and f"occ:{occupation.lower()}" not in seen:
                seen.add(f"occ:{occupation.lower()}")
                facts.append(
                    self.fact(
                        predicate="occupation",
                        value=occupation,
                        section="identity",
                        confidence=0.5,
                        url=url,
                        publisher="FEC",
                        candidate=True,
                    )
                )
        if facts:
            log(f"FEC donors: {len(facts)} public finance field(s)")
        return facts
