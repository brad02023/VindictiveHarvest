from __future__ import annotations

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


def unwrap_search_url(href: str) -> str:
    raw = (href or "").strip()
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
    return raw
