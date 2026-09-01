from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from html import unescape
from typing import Any

from viha.core.models import Case, Fact, Seed, Source, is_lookup_fact, is_miss_fact, utc_now
from viha.core.normalize import name_tokens, phone_digits_in_text

_STREET = re.compile(
    r"\b(\d{1,6}\s+(?:[A-Z0-9][A-Za-z0-9.'-]+\s+){0,5}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|"
    r"Way|Court|Ct|Circle|Cir|Place|Pl|Parkway|Pkwy|Highway|Hwy|Trail|Ter|Terrace)"
    r"\.?(?:\s+(?:N|S|E|W|North|South|East|West|NE|NW|SE|SW)\.?)?"
    r"(?:\s*,\s*[A-Za-z .]+,\s*[A-Z]{2}(?:\s+\d{5}(?:-\d{4})?)?)?)",
    re.I,
)
_OWNER_AGE = re.compile(r"Owner\s+(.+?),\s*Age\s+(\d{1,3})\s+in\s+(.+)", re.I)
_PLACE_ST = re.compile(r"^([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})")
_AGE = re.compile(r"\bAge\s*[:=]?\s*(\d{1,3})\b", re.I)
_AGE_BULLET = re.compile(
    r"\bAge\s+(\d{1,3})\s*[•·|,]\s*([A-Z][A-Za-z.' -]+,\s*[A-Z]{2})\b"
)
_BORN_MONTH_YEAR = re.compile(r"\bBorn\s+([A-Za-z]+)\s+(\d{4})\b", re.I)
_MONTHS = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}
_DOB = re.compile(
    r"\b(?:DOB|date of birth|born|b\.)\s*[:=]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"[A-Za-z]+\s+\d{1,2},?\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|"
    r"\d{4})",
    re.I,
)
_CITY_STATE = re.compile(
    r"\b(?:in|of|from|near|lives in|resides in|lived in|previously)\s+([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})\b"
)
_CURRENT_LOC_TEXT = re.compile(
    r"(?:current\s+location|lives?\s+in)\s*[:]\s*([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})",
    re.I,
)
_YEARS_OLD = re.compile(r"\b(\d{1,3})\s+years?\s+old\b", re.I)
_JOB = re.compile(
    r"(?:possible\s+job(?:\s*/\s*occupation)?|occupation|employer|job title|works?\s+at)\s*[:/\-]\s*"
    r"([A-Za-z][A-Za-z0-9 .,&']{2,60})",
    re.I,
)
_WD_SKIP = re.compile(
    r"disambiguation|family name|given name|wikimedia|surname|name of|fictional",
    re.I,
)
_CRIMINAL = re.compile(
    r"\b(united states v\.|u\.s\. v\.|usa v\.|criminal|indictment|plea|sentenc|prosecut)",
    re.I,
)


def name_matches_text(text: str, seed: Seed) -> bool:
    tokens = name_tokens(seed.full_name)
    if not tokens:
        return False
    words = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    if len(tokens) == 1:
        return tokens[0] in words
    return tokens[0] in words and tokens[-1] in words


def wikidata_is_person_hit(label: str, description: str, seed: Seed) -> bool:
    if _WD_SKIP.search(description or ""):
        return False
    return name_matches_text(f"{label} {description}", seed)


def parse_wikidata_time(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("+"):
        text = text[1:]
    text = text.split("T", 1)[0]
    if re.fullmatch(r"\d{4}-00-00", text):
        return text[:4]
    if re.fullmatch(r"\d{4}-\d{2}-00", text):
        return text[:7]
    return text


def normalize_dob(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{4}-\d{2}", text) or re.fullmatch(r"\d{4}", text):
        return text
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 1900 if year >= 30 else 2000
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return text
    try:
        return datetime.strptime(re.sub(r",", "", text), "%B %d %Y").date().isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(re.sub(r",", "", text), "%b %d %Y").date().isoformat()
    except ValueError:
        return text


def age_from_dob(dob: str, today: date | None = None) -> str:
    norm = normalize_dob(dob)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", norm):
        return ""
    born = date.fromisoformat(norm)
    now = today or date.today()
    years = now.year - born.year - ((now.month, now.day) < (born.month, born.day))
    if 0 < years < 120:
        return str(years)
    return ""


def location_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (raw or "").lower()).strip()


def is_truncated_place(place: str) -> bool:
    text = (place or "").strip()
    return len(text) < 6 or text.endswith("...") or text.endswith("…")


def likely_criminal(text: str) -> bool:
    return bool(_CRIMINAL.search(text or ""))


def _identity_gate(blob: str, seed: Seed, require_name: bool | None) -> bool:
    """True when the blob is about the seed (name tokens and/or reverse-phone digits)."""
    named = (not seed.full_name.strip()) or name_matches_text(blob, seed)
    phone_ok = bool(seed.phone) and phone_digits_in_text(seed.phone, blob)
    if require_name is False:
        return True
    if require_name is True:
        return named
    return named or phone_ok


def extract_identity_from_text(
    text: str,
    seed: Seed,
    *,
    require_name: bool | None = None,
) -> list[dict[str, str]]:
    """Pull age / DOB / city / street / job from an indexed title, snippet, or URL."""
    blob = re.sub(r"\s+", " ", unescape(text or "")).strip()
    if not blob:
        return []
    if seed.full_name.strip() and not _identity_gate(blob, seed, require_name):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(predicate: str, value: str) -> None:
        val = re.sub(r"\s+", " ", (value or "").strip(" .,"))
        val = re.sub(r"\.{2,}$", "", val).strip()
        if not val:
            return
        key = (predicate, val.lower())
        if key in seen:
            return
        seen.add(key)
        out.append({"predicate": predicate, "value": val})

    owner = _OWNER_AGE.search(blob)
    if owner:
        add("aka", owner.group(1))
        age = owner.group(2)
        if 1 <= int(age) <= 120:
            add("age", age)
        place = owner.group(3).strip()
        city = _PLACE_ST.match(place)
        if city and not is_truncated_place(city.group(1)):
            add("location", city.group(1).strip())

    for match in _AGE_BULLET.finditer(blob):
        age = match.group(1)
        if 1 <= int(age) <= 120:
            add("age", age)
        place = match.group(2).strip()
        if not is_truncated_place(place):
            add("location", place)

    born = _BORN_MONTH_YEAR.search(blob)
    if born:
        month = _MONTHS.get(born.group(1).lower())
        year = born.group(2)
        if month:
            add("dob", f"{year}-{month}")

    for match in _AGE.finditer(blob):
        age = match.group(1)
        if 1 <= int(age) <= 120:
            add("age", age)

    for match in _DOB.finditer(blob):
        dob = normalize_dob(match.group(1))
        if dob:
            add("dob", dob)
            derived = age_from_dob(dob)
            if derived:
                add("age", derived)

    for match in _CITY_STATE.finditer(blob):
        place = match.group(1).strip()
        if not is_truncated_place(place):
            add("location", place)

    for match in _STREET.finditer(blob):
        street = match.group(1).strip()
        if len(street) >= 8:
            add("address", street)

    loc_now = _CURRENT_LOC_TEXT.search(blob)
    if loc_now and not is_truncated_place(loc_now.group(1)):
        add("location", loc_now.group(1).strip())

    for match in _YEARS_OLD.finditer(blob):
        age = match.group(1)
        if 1 <= int(age) <= 120:
            add("age", age)

    job = _JOB.search(blob)
    if job:
        add("job", job.group(1).strip(" ./,-"))

    return out


_EMAIL_FIND = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_FIND = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_RELATED_NAME = r"[A-Z][A-Za-z.'\-]+\s+[A-Z][A-Za-z.'\-]+"
_RELATED_TO = re.compile(
    rf"(?i:related to|relatives?)\s*[:]\s*({_RELATED_NAME}(?:\s*,\s*{_RELATED_NAME})*)"
)
_SKIP_EMAIL_HOSTS = (
    "fastpeoplesearch",
    "truepeoplesearch",
    "intelius",
    "spokeo",
    "whitepages",
    "sentry.io",
    "cloudflare",
    "wix.com",
    "facebook.com",
    "google.com",
    "schema.org",
)


def extract_associates_from_text(
    text: str,
    seed: Seed,
    *,
    require_name: bool | None = None,
) -> list[dict[str, str]]:
    """Other emails, phones, and relative names on a people-index page."""
    blob = re.sub(r"\s+", " ", unescape(text or "")).strip()
    if not blob:
        return []
    if seed.full_name.strip() and not _identity_gate(blob, seed, require_name):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    seed_email = (seed.email or "").strip().lower()
    seed_digits = "".join(ch for ch in (seed.phone or "") if ch.isdigit())[-10:]

    def add(predicate: str, value: str, section: str) -> None:
        val = re.sub(r"\s+", " ", (value or "").strip(" .,"))
        if not val:
            return
        key = (predicate, val.lower())
        if key in seen:
            return
        seen.add(key)
        out.append({"predicate": predicate, "value": val, "section": section})

    for match in _EMAIL_FIND.finditer(blob):
        email = match.group(0).lower()
        host = email.split("@", 1)[-1]
        if email == seed_email or any(skip in host for skip in _SKIP_EMAIL_HOSTS):
            continue
        add("email", email, "contact")

    for match in _PHONE_FIND.finditer(blob):
        digits = "".join(ch for ch in match.group(0) if ch.isdigit())[-10:]
        if len(digits) < 10 or digits == seed_digits:
            continue
        pretty = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        add("phone", pretty, "contact")

    related = _RELATED_TO.search(blob)
    if related:
        for raw in re.split(r",|;| and ", related.group(1)):
            name = re.sub(r"https?://\S+", "", raw)
            name = re.sub(r"\s+", " ", name).strip(" .")
            if len(name.split()) < 2 or name_matches_text(name, seed):
                continue
            add("associate", name, "identity")
    return out


def fields_from_github_user(user: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    loc = (user.get("location") or "").strip()
    if loc:
        out.append({"predicate": "location", "value": loc, "section": "identity"})
    name = (user.get("name") or "").strip()
    if name:
        out.append({"predicate": "aka", "value": name, "section": "identity"})
    company = (user.get("company") or "").strip().lstrip("@")
    if company:
        out.append({"predicate": "org", "value": company, "section": "business"})
    return out


def _best(facts: list[Fact]) -> Fact | None:
    if not facts:
        return None
    return sorted(facts, key=lambda f: (f.candidate, -f.confidence, f.source.publisher))[0]


def persona_brief(case: Case) -> dict[str, Any]:
    def usable(fact: Fact) -> bool:
        return not is_lookup_fact(fact) and not is_miss_fact(fact)

    by_pred: dict[str, list[Fact]] = defaultdict(list)
    for fact in case.facts:
        if usable(fact):
            by_pred[fact.predicate].append(fact)
    age = _best(by_pred.get("age") or [])
    dob = _best(by_pred.get("dob") or [])
    job = _best(by_pred.get("job") or [])
    locations = _unique_places((by_pred.get("address") or []) + (by_pred.get("location") or []))
    gps = _best(by_pred.get("gps") or [])
    relatives = [
        f
        for f in case.facts
        if usable(f) and f.predicate == "associate"
    ]
    dockets = [f for f in case.facts if usable(f) and f.predicate in {"docket", "charge"}]
    charges = [
        f
        for f in dockets
        if f.predicate == "charge" or f.extra.get("likely_criminal") or likely_criminal(f.value)
    ]
    property_facts = [
        f
        for f in case.facts
        if usable(f)
        and (f.section == "property" or f.predicate in {"property", "mortgage", "deed", "lien", "address"})
    ]
    lines: list[str] = []

    def chip(label: str, fact: Fact | None, empty: str = "—") -> str:
        if not fact:
            return f"{label} {empty}"
        mark = " · candidate" if fact.candidate and not fact.pinned else ""
        return f"{label} {fact.value}{mark}"

    lines.append(chip("Age", age))
    lines.append(chip("Born", dob))
    if job:
        lines.append(chip("Job", job))
    if locations:
        loc_txt = " · ".join(
            f.value + (" · candidate" if f.candidate and not f.pinned else "") for f in locations[:4]
        )
        lines.append(f"Locations {loc_txt}")
    else:
        lines.append(chip("Location", gps))
    legal_facts = charges or dockets
    if legal_facts:
        lines.append("Legal " + " · ".join(f.value[:48] for f in legal_facts[:2]))
    else:
        lines.append("Legal —")
    if property_facts:
        lines.append("Property " + " · ".join(f.value[:48] for f in property_facts[:3]))
    else:
        lines.append("Property —")
    return {
        "age": age,
        "dob": dob,
        "location": locations[0] if locations else gps,
        "locations": locations,
        "address": next((f for f in locations if f.predicate == "address"), None),
        "gps": gps,
        "dockets": dockets,
        "charges": charges,
        "property": property_facts,
        "legal_facts": legal_facts,
        "job": job,
        "relatives": relatives,
        "summary": "   ·   ".join(lines),
    }


def _unique_places(facts: list[Fact]) -> list[Fact]:
    out: list[Fact] = []
    seen: set[str] = set()
    for fact in sorted(facts, key=lambda f: (f.candidate, -f.confidence)):
        key = location_key(fact.value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(fact)
    return out


_PEOPLE_BROKER_NEEDLES = (
    "indexedpeoplesearch",
    "fastpeoplesearch",
    "truepeoplesearch",
    "intelius",
    "spokeo",
    "whitepages",
    "beenverified",
    "peoplefinders",
    "thatsthem",
    "cyberbackgroundchecks",
)


def is_people_broker(publisher: str) -> bool:
    compact = re.sub(r"[^a-z]", "", (publisher or "").lower())
    return any(needle in compact for needle in _PEOPLE_BROKER_NEEDLES)


def is_people_broker_url(url: str) -> bool:
    return any(needle in (url or "").lower() for needle in _PEOPLE_BROKER_NEEDLES)


_SKIP_INGEST_PRED = {
    "age",
    "dob",
    "location",
    "address",
    "job",
    "associate",
    "aka",
    "org",
    "email",
    "phone",
}


def _mention_blob(fact: Fact) -> str:
    bits: list[str] = [fact.value, fact.raw, fact.source.note, fact.source.url]
    extra = fact.extra or {}
    for key in ("title", "snippet", "query"):
        if extra.get(key):
            bits.append(str(extra[key]))
    raw = (fact.raw or "").strip()
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            bits.extend(str(obj.get(k) or "") for k in ("title", "snippet", "query"))
    return re.sub(r"\s+", " ", " ".join(b for b in bits if b)).strip()


def ingest_mention_facts(case: Case) -> int:
    """Turn Bing/DDG titles and people-index URLs already in the case into identity facts."""
    seed = case.seed
    added = 0
    for fact in list(case.facts):
        if fact.section == "social" or fact.predicate in _SKIP_INGEST_PRED:
            continue
        url = fact.source.url or ""
        people_page = (
            is_people_broker(fact.source.publisher)
            or is_people_broker_url(url)
            or fact.predicate in {"web_mention", "people_index"}
        )
        blob = _mention_blob(fact)
        if len(blob) < 8:
            continue
        if not people_page and not name_matches_text(blob, seed):
            continue
        before = len(case.facts)
        pub = fact.source.publisher
        if pub in {"Bing", "DuckDuckGo"}:
            pub = "Indexed people search"
        for item in extract_identity_from_text(blob, seed):
            case.add_fact(
                Fact(
                    predicate=item["predicate"],
                    value=item["value"],
                    section="identity" if item["predicate"] != "job" else "business",
                    confidence=0.54,
                    source=Source(
                        publisher=pub,
                        url=url,
                        retrieved_at=utc_now(),
                        collector="viha.identity.mentions",
                        note="Parsed from indexed title/snippet",
                    ),
                    extra={"via": "mention-parse"},
                    candidate=True,
                    raw=(fact.value or "")[:500],
                )
            )
        for item in extract_associates_from_text(blob, seed):
            case.add_fact(
                Fact(
                    predicate=item["predicate"],
                    value=item["value"],
                    section=item.get("section") or "identity",
                    confidence=0.5,
                    source=Source(
                        publisher=pub,
                        url=url,
                        retrieved_at=utc_now(),
                        collector="viha.identity.mentions",
                        note="Parsed from indexed title/snippet",
                    ),
                    extra={"via": "mention-parse", "associate": item["predicate"] == "associate"},
                    candidate=True,
                    raw=(fact.value or "")[:500],
                )
            )
        added += max(0, len(case.facts) - before)
    return added


def corroborate_identity(case: Case) -> None:
    """Confirm city/age when two independent public sources agree. Streets stay candidates unless official sources agree."""
    groups: dict[tuple[str, str], list[Fact]] = defaultdict(list)
    for fact in case.facts:
        if fact.predicate not in {"age", "dob", "location", "address"}:
            continue
        key_val = location_key(fact.value) if fact.predicate in {"location", "address"} else fact.value.strip().lower()
        if not key_val:
            continue
        groups[(fact.predicate, key_val)].append(fact)

    def _publishers(items: list[Fact]) -> set[str]:
        pubs: set[str] = set()
        for fact in items:
            pubs.add(fact.source.publisher)
            for extra in fact.extra.get("sources") or []:
                if isinstance(extra, dict) and extra.get("publisher"):
                    pubs.add(str(extra["publisher"]))
        return pubs

    for (pred, _key), items in groups.items():
        pubs = _publishers(items)
        if len(pubs) < 2:
            continue
        if pred == "address":
            official = pubs & {"FEC", "SEC EDGAR", "OpenCorporates", "Wikidata"}
            if len(official) < 2:
                continue
        elif all(is_people_broker(p) for p in pubs):
            continue
        for fact in items:
            fact.candidate = False
            fact.confidence = max(fact.confidence, 0.72)

    dobs = [f for f in case.facts if f.predicate == "dob" and f.value]
    if dobs and not any(f.predicate == "age" for f in case.facts):
        derived = age_from_dob(dobs[0].value)
        if derived:
            src = dobs[0].source
            case.add_fact(
                Fact(
                    predicate="age",
                    value=derived,
                    section="identity",
                    confidence=min(0.7, dobs[0].confidence),
                    source=src,
                    extra={"via": "dob"},
                    candidate=dobs[0].candidate,
                )
            )
