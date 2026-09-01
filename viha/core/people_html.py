from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

from viha.core.identity import extract_associates_from_text, extract_identity_from_text, name_matches_text
from viha.core.models import Fact, Seed, Source, utc_now
from viha.core.normalize import name_search_variants, name_tokens, phone_digits_in_text

_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_CANON_RE = re.compile(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', re.I)
_CANON_RE_REV = re.compile(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', re.I)
_OG_URL = re.compile(r'property=["\']og:url["\'][^>]*content=["\']([^"\']+)', re.I)
_OG_URL_REV = re.compile(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:url["\']', re.I)
_ADDR_LINK = re.compile(
    r'<a[^>]+href="[^"]*/(?:address|addresses)/[^"]+"[^>]*>\s*([^<]+?)\s*</a>',
    re.I | re.S,
)
_NAME_LINK = re.compile(
    r'<a[^>]+href="[^"]*/name/[^"]+"[^>]*>\s*([^<]+?)\s*</a>',
    re.I | re.S,
)
_PROFILE_LINK = re.compile(
    r'<a[^>]+href=["\']([^"\']+_id_G\d+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_LD_JSON = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.I | re.S,
)
_DETAILS_HEADER = re.compile(r'id=["\']details-header["\'][^>]*>(.*?)</h1>', re.I | re.S)
_AGE_HEADER = re.compile(r'id=["\']age-header["\'][^>]*>(.*?)</h[12]>', re.I | re.S)
_JOB_HEADING = re.compile(
    r"(?:possible\s+job(?:\s*/\s*occupation)?|occupation|employer|works?\s+at)\s*[:</][^A-Za-z]{0,40}([A-Za-z0-9 .,&'/-]{3,80})",
    re.I,
)
_CURRENT_LOC = re.compile(
    r"current\s+location\s*[:</][^A-Za-z]{0,40}([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})",
    re.I,
)
_PAST_CITIES = re.compile(
    r"past\s+addresses?\s*[:</](.{0,400}?)(?:relatives?|view\s+free|phone|email|<h\d|$)",
    re.I | re.S,
)
_CITY_ST = re.compile(r"\b([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})\b")
_CFEMAIL = re.compile(r'data-cfemail=["\']([0-9a-f]+)["\']', re.I)
_MAILTO = re.compile(r'href=["\']mailto:([^"\'?]+)', re.I)
_TITLE_NAME = re.compile(r"^(?:Owner\s+)?(.+?),?\s+Age\s+\d+", re.I)
_CONF = {
    "aka": 0.64,
    "age": 0.62,
    "dob": 0.58,
    "location": 0.6,
    "address": 0.55,
    "email": 0.58,
    "phone": 0.55,
    "associate": 0.5,
    "job": 0.55,
    "org": 0.52,
}


@dataclass
class PeoplePage:
    title: str
    url: str
    publisher: str
    items: list[dict[str, Any]] = field(default_factory=list)
    phone_match: bool = False


def publisher_from_url(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if "fastpeoplesearch" in host:
        return "FastPeopleSearch"
    if "truepeoplesearch" in host:
        return "TruePeopleSearch"
    if "intelius" in host:
        return "Intelius"
    if "spokeo" in host:
        return "Spokeo"
    if "whitepages" in host:
        return "Whitepages"
    if "peoplefinders" in host:
        return "PeopleFinders"
    if "beenverified" in host:
        return "BeenVerified"
    if "thatsthem" in host:
        return "ThatsThem"
    if "clustrmaps" in host:
        return "ClustrMaps"
    return "Indexed people search"


def source_url_from_html(html: str, fallback: str = "") -> str:
    text = html or ""
    for rx in (_CANON_RE, _CANON_RE_REV, _OG_URL, _OG_URL_REV):
        match = rx.search(text)
        if match:
            href = unescape(match.group(1).strip())
            if href.startswith("http"):
                return href
    return fallback


def page_title(html: str) -> str:
    match = _TITLE_RE.search(html or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", unescape(match.group(1))).strip()


def strip_chrome(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html or "", flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", text, flags=re.I | re.S)
    return text


def html_to_plain(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", strip_chrome(html)))).strip()


def seed_for_people_page(seed: Seed, title: str) -> Seed:
    if seed.full_name.strip():
        return seed
    match = _TITLE_NAME.search(title or "")
    if not match:
        return seed
    return Seed(
        full_name=match.group(1).strip(),
        phone=seed.phone,
        email=seed.email,
        city=seed.city,
        state=seed.state,
        org=seed.org,
        username=seed.username,
    )


def _abs_url(href: str, base: str) -> str:
    raw = unescape((href or "").strip())
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    if raw.startswith("http"):
        return raw.split("#")[0]
    origin = base if base.startswith("http") else "https://www.fastpeoplesearch.com"
    return urljoin(origin if origin.endswith("/") else origin + "/", raw.lstrip("/")).split("#")[0]


def _link_text(inner: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG_RE.sub(" ", inner or ""))).strip()


def decode_cfemail(hexstr: str) -> str:
    raw = (hexstr or "").strip()
    if len(raw) < 4 or len(raw) % 2:
        return ""
    try:
        key = int(raw[:2], 16)
        chars = [chr(int(raw[i : i + 2], 16) ^ key) for i in range(2, len(raw), 2)]
    except ValueError:
        return ""
    email = "".join(chars).strip().lower()
    return email if "@" in email else ""


def _ld_objects(html: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return
        if not isinstance(obj, dict):
            return
        out.append(obj)
        if "@graph" in obj:
            walk(obj["@graph"])

    for match in _LD_JSON.finditer(html or ""):
        blob = unescape(match.group(1)).strip()
        if not blob:
            continue
        try:
            walk(json.loads(blob))
        except json.JSONDecodeError:
            continue
    return out


def _ld_types(obj: dict[str, Any]) -> set[str]:
    raw = obj.get("@type")
    if isinstance(raw, list):
        return {str(x).lower() for x in raw}
    if raw:
        return {str(raw).lower()}
    return set()


def _textish(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or value.get("text") or "").strip()
    if isinstance(value, list) and value:
        return _textish(value[0])
    return ""


def _format_ld_address(addr: Any) -> str:
    if isinstance(addr, str):
        return re.sub(r"\s+", " ", addr).strip()
    if not isinstance(addr, dict):
        return ""
    nested = addr.get("address")
    if isinstance(nested, dict):
        addr = nested
    parts = [
        addr.get("streetAddress") or addr.get("street"),
        addr.get("addressLocality") or addr.get("city"),
        addr.get("addressRegion") or addr.get("state"),
        addr.get("postalCode") or addr.get("zip"),
    ]
    street = (parts[0] or "").strip()
    city = (parts[1] or "").strip()
    state = (parts[2] or "").strip()
    zipc = (parts[3] or "").strip()
    place = ", ".join(p for p in (city, state) if p)
    if street and place:
        line = f"{street}, {place}"
    else:
        line = street or place
    if zipc and line:
        line = f"{line} {zipc}" if not line.endswith(zipc) else line
    return re.sub(r"\s+", " ", line).strip(" ,")


def items_from_jsonld(html: str, seed: Seed) -> list[dict[str, str]]:
    """Person + FAQ JSON-LD on FastPeopleSearch / TruePeopleSearch detail pages."""
    out: list[dict[str, str]] = []
    emails: list[str] = []
    for obj in _ld_objects(html):
        types = _ld_types(obj)
        if "person" in types:
            name = _textish(obj.get("name"))
            if name:
                out.append({"predicate": "aka", "value": name, "section": "identity"})
            for aka in obj.get("additionalName") or []:
                text = _textish(aka)
                if text:
                    out.append({"predicate": "aka", "value": text, "section": "identity"})
            born = _textish(obj.get("birthDate"))
            if born:
                out.append({"predicate": "dob", "value": born, "section": "identity"})
            loc = obj.get("homeLocation") or obj.get("address")
            addr = _format_ld_address(loc)
            if addr:
                out.append({"predicate": "address", "value": addr, "section": "identity"})
            for phone in obj.get("telephone") or []:
                text = _textish(phone)
                if text:
                    out.append({"predicate": "phone", "value": text, "section": "contact"})
            job = _textish(obj.get("jobTitle")) or _textish(obj.get("hasOccupation"))
            if job:
                out.append({"predicate": "job", "value": job, "section": "business"})
            org = _textish(obj.get("worksFor"))
            if org:
                out.append({"predicate": "org", "value": org, "section": "business"})
            for rel in obj.get("relatedTo") or []:
                rel_name = _textish(rel)
                if rel_name and not name_matches_text(rel_name, seed):
                    out.append({"predicate": "associate", "value": rel_name, "section": "identity"})
            mail = _textish(obj.get("email"))
            if mail:
                emails.append(mail)
        if "faqpage" in types:
            for q in obj.get("mainEntity") or []:
                if not isinstance(q, dict):
                    continue
                blob = f"{q.get('name') or ''} {(q.get('acceptedAnswer') or {}).get('text') or ''}"
                if "email" in blob.lower():
                    emails.extend(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", blob))
                job_hit = re.search(
                    r"(?:job|occupation|employer|works? at)\s*[:\-]\s*([A-Za-z0-9 .,&'/-]{3,80})",
                    blob,
                    re.I,
                )
                if job_hit:
                    out.append({"predicate": "job", "value": job_hit.group(1), "section": "business"})
    seed_email = (seed.email or "").strip().lower()
    for email in emails:
        val = email.strip().lower()
        if val and val != seed_email:
            out.append({"predicate": "email", "value": val, "section": "contact"})
    return out


def profile_slug_matches_seed(href: str, seed: Seed) -> bool:
    path = urlparse(href).path.lower()
    if "_id_g" not in path:
        return False
    slug = path.rsplit("/", 1)[-1]
    hay = slug.replace("-", " ").replace("_", " ")
    for variant in name_search_variants(seed.full_name) or [seed.full_name]:
        tokens = name_tokens(variant)
        if len(tokens) >= 2 and tokens[0] in hay and tokens[-1] in hay:
            return True
    return False


def detail_profile_urls(html: str, seed: Seed, page_url: str = "") -> list[str]:
    """Follow-on FastPeopleSearch `_id_G` profile URLs that match the seed name."""
    seen: set[str] = set()
    out: list[str] = []
    base = page_url or "https://www.fastpeoplesearch.com/"
    for match in _PROFILE_LINK.finditer(html or ""):
        dest = _abs_url(match.group(1), base)
        text = _link_text(match.group(2))
        if not dest or dest in seen:
            continue
        if profile_slug_matches_seed(dest, seed) or (text and name_matches_text(text, seed)):
            seen.add(dest)
            out.append(dest)
    if page_url and profile_slug_matches_seed(page_url, seed) and page_url not in seen:
        out.insert(0, page_url.split("#")[0])
    return out[:4]


def parse_people_index_html(html: str, seed: Seed, url: str = "") -> PeoplePage:
    """Parse a saved or live people-index page (FastPeopleSearch / TruePeopleSearch / Intelius)."""
    dest = source_url_from_html(html, url)
    title = page_title(html)
    publisher = publisher_from_url(dest)
    work = seed_for_people_page(seed, title)
    chrome_free = strip_chrome(html)
    plain = html_to_plain(html)
    blob = f"{title} {plain}"
    phone_hit = phone_digits_in_text(work.phone, f"{title} {dest} {plain[:4000]}")
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(predicate: str, value: str, section: str, extra: dict[str, Any] | None = None) -> None:
        val = re.sub(r"\s+", " ", (value or "").strip(" .,"))
        if not val:
            return
        key = (predicate, val.lower())
        if key in seen:
            return
        seen.add(key)
        conf = _CONF.get(predicate, 0.45)
        if phone_hit:
            conf = min(0.78, conf + 0.12)
        payload = {"via": "people-index", "phone_match": phone_hit}
        if extra:
            payload.update(extra)
        items.append(
            {
                "predicate": predicate,
                "value": val,
                "section": section,
                "confidence": conf,
                "extra": payload,
            }
        )

    past_at = re.search(r"past addresses?", chrome_free, re.I)
    past_idx = past_at.start() if past_at else None
    for match in _ADDR_LINK.finditer(chrome_free):
        text = re.sub(r"\s+", " ", unescape(match.group(1))).strip()
        extra: dict[str, Any] = {}
        if past_idx is not None and match.start() >= past_idx:
            extra["past"] = True
        add("address", text, "identity", extra)

    for match in _NAME_LINK.finditer(chrome_free):
        name = re.sub(r"\s+", " ", unescape(match.group(1))).strip()
        if len(name.split()) < 2 or name_matches_text(name, work):
            continue
        extra = {"associate": True}
        add("associate", name, "identity", extra)

    seed_email = (work.email or "").strip().lower()
    for match in _MAILTO.finditer(chrome_free):
        email = unescape(match.group(1)).strip().lower()
        if not email or email == seed_email:
            continue
        extra = {"associate": True}
        add("email", email, "contact", extra)

    for item in extract_identity_from_text(blob, work):
        add(item["predicate"], item["value"], "identity")
    for item in extract_associates_from_text(blob, work):
        extra = {"associate": True}
        add(item["predicate"], item["value"], item.get("section") or "contact", extra)

    header = _DETAILS_HEADER.search(html or "")
    if header:
        head = _link_text(header.group(1))
        loc_at = re.search(r"\bin\s+([A-Z][A-Za-z .'-]+,\s*[A-Z]{2})", head)
        if loc_at:
            add("location", loc_at.group(1), "identity")
        name_part = re.split(r"\s+in\s+", head, maxsplit=1)[0].strip()
        if name_part:
            add("aka", name_part, "identity")
    age_h = _AGE_HEADER.search(html or "")
    if age_h:
        age_txt = _link_text(age_h.group(1))
        age_n = re.search(r"(\d{1,3})", age_txt)
        if age_n and 1 <= int(age_n.group(1)) <= 120:
            add("age", age_n.group(1), "identity")
    loc_m = _CURRENT_LOC.search(plain)
    if loc_m:
        add("location", loc_m.group(1), "identity")
    past_m = _PAST_CITIES.search(plain)
    if past_m:
        for city in _CITY_ST.findall(past_m.group(1)):
            add("location", city, "identity", {"past": True})
    job_m = _JOB_HEADING.search(plain)
    if job_m:
        add("job", job_m.group(1), "business")

    for item in items_from_jsonld(html, work):
        extra = {"associate": True} if item["predicate"] == "associate" else None
        add(item["predicate"], item["value"], item["section"], extra)

    for match in _PROFILE_LINK.finditer(html or ""):
        href = _abs_url(match.group(1), dest)
        name = _link_text(match.group(2))
        if not name or name.lower() in {"view free details", "view details", "more details"}:
            if href and profile_slug_matches_seed(href, work):
                add("people_index", href, "identity", {"detail": True, "profile_url": href})
            continue
        if name_matches_text(name, work) or profile_slug_matches_seed(href, work):
            add("people_index", href, "identity", {"detail": True, "profile_url": href})
            continue
        if len(name.split()) >= 2:
            add("associate", name, "identity", {"associate": True, "profile_url": href})

    for hexstr in _CFEMAIL.findall(html or ""):
        email = decode_cfemail(hexstr)
        if email and email != (work.email or "").strip().lower():
            add("email", email, "contact", {"associate": True})

    return PeoplePage(title=title, url=dest, publisher=publisher, items=items, phone_match=phone_hit)


def facts_from_people_html(
    html: str,
    seed: Seed,
    url: str = "",
    collector: str = "viha.db.people",
    imported: bool = False,
) -> list[Fact]:
    page = parse_people_index_html(html, seed, url)
    facts: list[Fact] = []
    for item in page.items:
        extra = dict(item.get("extra") or {})
        if imported:
            extra["imported"] = True
            extra["via"] = "people-html-import"
        src_url = extra.get("profile_url") or page.url or url or "viha://people-html"
        facts.append(
            Fact(
                predicate=item["predicate"],
                value=item["value"],
                section=item["section"],
                confidence=float(item["confidence"]),
                source=Source(
                    publisher=page.publisher,
                    url=src_url,
                    retrieved_at=utc_now(),
                    collector=collector,
                    note=page.title,
                ),
                extra=extra,
                candidate=True,
                raw=page.title,
            )
        )
    if page.phone_match and (page.title or seed.full_name.strip()):
        extra = {"via": "people-html-import" if imported else "people-index", "phone_match": True}
        if imported:
            extra["imported"] = True
        facts.append(
            Fact(
                predicate="web_mention",
                value=page.title or page.publisher,
                section="web",
                confidence=0.7,
                source=Source(
                    publisher=page.publisher,
                    url=page.url or url or "viha://people-html",
                    retrieved_at=utc_now(),
                    collector=collector,
                ),
                extra=extra,
                candidate=False,
            )
        )
    return facts
