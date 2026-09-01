from __future__ import annotations

from urllib.parse import quote_plus

from viha.collectors.base import Collector, LogFn
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_phone

_GUADALUPE_CITIES = {
    "cibolo",
    "schertz",
    "seguin",
    "marion",
    "mcqueeney",
    "new berlin",
    "kingsbury",
    "geronimo",
    "staples",
    "guadalupe",
}
_GUADALUPE_ZIPS = ("78108", "78155", "78154", "78124", "78115")


def _public_record_links(seed: Seed) -> list[tuple[str, str, str]]:
    name = seed.full_name.strip()
    org = seed.org.strip()
    city = seed.city.strip()
    state = (seed.state or "").strip().upper()
    phone = normalize_phone(seed.phone)
    qn = quote_plus(name) if name else quote_plus(org)
    if not qn:
        return []
    st = state or ("TX" if phone.startswith("+1210") or (seed.phone or "").replace(" ", "").startswith("210") else "")
    place = " ".join(p for p in (city, st) if p)
    qp = quote_plus(place) if place else ""
    out: list[tuple[str, str, str]] = [
        (
            "CourtListener dockets",
            f"https://www.courtlistener.com/?q=%22{qn}%22&type=d",
            "legal",
        ),
        (
            "PACER / RECAP search",
            f"https://www.courtlistener.com/?q=%22{qn}%22&type=r",
            "legal",
        ),
        (
            "Criminal / docket search",
            f"https://duckduckgo.com/?q=%22{qn}%22+{qp}+(court+OR+docket+OR+criminal+OR+indictment)".replace("++", "+"),
            "legal",
        ),
        (
            "Property / assessor / deed",
            f"https://duckduckgo.com/?q=%22{qn}%22+{qp}+(assessor+OR+appraisal+OR+deed+OR+mortgage+OR+recorder)".replace("++", "+"),
            "property",
        ),
        (
            "UCC / lien search",
            f"https://duckduckgo.com/?q=%22{qn}%22+{qp}+(UCC+OR+lien+OR+%22financing+statement%22)".replace("++", "+"),
            "property",
        ),
    ]
    is_tx = st == "TX" or phone.startswith("+1210") or "210" in (seed.phone or "")[:5]
    city_l = city.lower()
    is_210 = phone.startswith("+1210") or (seed.phone or "").replace(" ", "").startswith("210")
    if is_tx:
        out += [
            ("TX SOS entity / officer search", "https://www.sos.state.tx.us/corp/sosda/index.shtml", "business"),
            ("TX Comptroller taxpayer search", "https://mycpa.cpa.state.tx.us/coa/", "business"),
            ("TX UCC search (SOSDirect)", "https://direct.sos.state.tx.us/", "property"),
            ("TDLR license search", "https://www.tdlr.texas.gov/LicenseSearch/", "business"),
            ("TX courts search", "https://www.txcourts.gov/", "legal"),
        ]
        if is_210 or city_l in {"san antonio", "bexar"} or not city_l:
            out.append(("Bexar County appraisal", "https://bexar.trueautomation.com/clientdb/?cid=110", "property"))
        if is_210 or city_l in _GUADALUPE_CITIES or any(z in city_l for z in _GUADALUPE_ZIPS):
            out.append(
                ("Guadalupe CAD (TrueAutomation)", "https://propaccess.trueautomation.com/clientdb/?cid=75", "property")
            )
            out.append(("Guadalupe CAD eSearch", "https://esearch.guadalupecad.org/", "property"))
        if city_l in {"houston", "harris"}:
            out.append(("Harris CAD", "https://www.hcad.org/property-search/", "property"))
        if city_l in {"austin", "travis"}:
            out.append(("Travis CAD", "https://www.traviscad.org/property-search/", "property"))
        if city_l in {"dallas"}:
            out.append(("Dallas CAD", "https://www.dallascad.org/", "property"))
        if city_l in {"fort worth", "tarrant"}:
            out.append(("Tarrant CAD", "https://www.tad.org/", "property"))
    return out


class TexasRecordsCollector(Collector):
    id = "viha.db.texas"
    label = "Public records"
    blurb = "Court, CAD, UCC, and recorder portals (links only)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        if not seed.full_name.strip() and not seed.org.strip():
            log("Public records skipped — need a name or org")
            return []
        links = _public_record_links(seed)
        log(f"Public-record portals: {len(links)} lookup URLs")
        return [
            self.fact(
                predicate="recipe" if section != "property" else "property",
                value=label,
                section=section,
                confidence=0.35,
                url=url,
                publisher="Public record portal",
                extra={"jurisdiction": (seed.state or "").strip().upper() or "US", "lookup": True},
                candidate=False,
            )
            for label, url, section in links
        ]
