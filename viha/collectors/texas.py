from __future__ import annotations

from viha.collectors.base import Collector, LogFn
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_phone


class TexasRecordsCollector(Collector):
    id = "viha.db.texas"
    label = "Texas records"
    blurb = "Public TX SOS / CAD / license lookup URLs (210 / Bexar)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        state = (seed.state or "").strip().upper()
        phone = normalize_phone(seed.phone)
        is_tx = state == "TX" or phone.startswith("+1210") or "210" in (seed.phone or "")[:5]
        if not is_tx:
            log("Texas records skipped — set State=TX or use a 210 number")
            return []
        if not seed.full_name.strip() and not seed.org.strip():
            log("Texas records skipped — need a name or org")
            return []
        log("Texas public-record portals (open in browser)")
        links = [
            ("TX SOS entity / officer search", "https://www.sos.state.tx.us/corp/sosda/index.shtml"),
            ("TX Comptroller taxpayer search", "https://mycpa.cpa.state.tx.us/coa/"),
            ("Bexar County appraisal", "https://bexar.trueautomation.com/clientdb/?cid=110"),
            ("TDLR license search", "https://www.tdlr.texas.gov/LicenseSearch/"),
            ("TX courts search", "https://www.txcourts.gov/"),
        ]
        if seed.city.strip().lower() in {"houston", "harris"}:
            links.append(("Harris CAD", "https://www.hcad.org/property-search/"))
        if seed.city.strip().lower() in {"austin", "travis"}:
            links.append(("Travis CAD", "https://www.traviscad.org/property-search/"))
        facts = [
            self.fact(
                predicate="recipe",
                value=label,
                section="recipes",
                confidence=0.35,
                url=url,
                publisher="Texas public record",
                extra={"jurisdiction": "TX"},
                candidate=False,
            )
            for label, url in links
        ]
        return facts
