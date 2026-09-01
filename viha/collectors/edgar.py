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
        if seed.org.strip():
            facts.extend(await self._company_address(client, log, seed.org.strip(), headers))
        if not facts:
            log("EDGAR: no public hits")
        return facts

    async def _company_address(self, client, log: LogFn, org: str, headers: dict) -> list[Fact]:
        try:
            data = await fetch_json(
                client,
                "https://efts.sec.gov/LATEST/search-index",
                params={"q": f'"{org}"', "forms": "10-K,10-Q,8-K", "dateRange": "all"},
                headers=headers,
            )
        except Exception as exc:
            log(f"EDGAR company address: {exc}")
            return []
        hits = (data.get("hits") or {}).get("hits") or []
        cik = ""
        for hit in hits[:5]:
            src = hit.get("_source") or {}
            ciks = src.get("ciks") or src.get("cik") or []
            if isinstance(ciks, list) and ciks:
                cik = str(ciks[0]).zfill(10)
                break
            if ciks:
                cik = str(ciks).zfill(10)
                break
        if not cik:
            return []
        try:
            sub = await fetch_json(
                client,
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=headers,
            )
        except Exception as exc:
            log(f"EDGAR submissions {cik}: {exc}")
            return []
        addresses = sub.get("addresses") or {}
        facts: list[Fact] = []
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
        for kind in ("business", "mailing"):
            block = addresses.get(kind) or {}
            street = " ".join(p for p in (block.get("street1"), block.get("street2")) if p).strip()
            city = (block.get("city") or "").strip()
            state = (block.get("stateOrCountry") or "").strip()
            zipc = (block.get("zipCode") or "").strip()
            place = ", ".join(p for p in (city, state) if p)
            if street:
                facts.append(
                    self.fact(
                        predicate="address",
                        value=", ".join(p for p in (street, place, zipc) if p),
                        section="property",
                        confidence=0.7,
                        url=url,
                        publisher="SEC EDGAR",
                        extra={"cik": cik, "kind": kind},
                        candidate=True,
                    )
                )
            elif place:
                facts.append(
                    self.fact(
                        predicate="location",
                        value=place,
                        section="identity",
                        confidence=0.62,
                        url=url,
                        publisher="SEC EDGAR",
                        extra={"cik": cik, "kind": kind},
                        candidate=True,
                    )
                )
        if facts:
            log(f"EDGAR address: CIK {cik}")
        return facts
