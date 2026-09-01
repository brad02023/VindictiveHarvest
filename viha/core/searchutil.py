from __future__ import annotations

import base64
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

CONSUMER_MAIL = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "ymail.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "mail.com",
}


def is_consumer_mail(domain: str) -> bool:
    return (domain or "").strip().lower() in CONSUMER_MAIL


PEOPLE_FETCH_HOSTS = (
    "fastpeoplesearch.com",
    "truepeoplesearch.com",
    "intelius.com",
    "spokeo.com",
    "whitepages.com",
    "peoplefinders.com",
    "beenverified.com",
    "thatsthem.com",
    "clustrmaps.com",
    "cyberbackgroundchecks.com",
)
FETCH_HOSTS = PEOPLE_FETCH_HOSTS + (
    "courtlistener.com",
    "opencorporates.com",
    "fec.gov",
    "sec.gov",
    "wikidata.org",
)
SKIP_FETCH = (
    "accounts.google.com",
    "facebook.com/login",
    "linkedin.com/authwall",
    "instagram.com/accounts",
)


def is_fetchable_result(url: str) -> bool:
    raw = (url or "").lower()
    if not raw.startswith("http"):
        return False
    if any(s in raw for s in SKIP_FETCH):
        return False
    host = urlparse(raw).netloc
    return any(h in host for h in FETCH_HOSTS)


def is_people_broker_url(url: str) -> bool:
    raw = (url or "").lower()
    host = urlparse(raw).netloc
    return any(h in host for h in PEOPLE_FETCH_HOSTS)


def fetch_priority(url: str) -> int:
    raw = (url or "").lower()
    if "_id_g" in raw:
        return 0
    if is_people_broker_url(url):
        return 1
    return 2


def wayback_latest(url: str) -> str:
    return f"https://web.archive.org/web/2/{url}"


def wayback_identity(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def unwrap_search_url(href: str) -> str:
    raw = unescape((href or "").strip())
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw
    host = (parsed.netloc or "").lower()
    if "duckduckgo.com" in host:
        qs = parse_qs(parsed.query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    if "bing.com" in host and "/ck/" in (parsed.path or ""):
        qs = parse_qs(parsed.query)
        payload = (qs.get("u") or [""])[0]
        decoded = _decode_bing_u(payload)
        if decoded:
            return decoded
    return raw


def _decode_bing_u(payload: str) -> str:
    text = (payload or "").strip()
    if text.startswith("a1"):
        text = text[2:]
    if not text:
        return ""
    pad = text + "=" * (-len(text) % 4)
    try:
        out = base64.urlsafe_b64decode(pad).decode("utf-8", "replace")
    except Exception:
        return ""
    if out.startswith("/"):
        return ""
    if out.startswith("http://") or out.startswith("https://"):
        return out
    return ""
