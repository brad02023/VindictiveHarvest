from __future__ import annotations

import re
from urllib.parse import quote, quote_plus, urlparse


_PHONE_RE = re.compile(r"\D+")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(raw: str) -> str:
    digits = _PHONE_RE.sub("", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1{digits}"
    if digits:
        return f"+{digits}"
    return ""


def format_phone(raw: str) -> str:
    e164 = normalize_phone(raw)
    if e164.startswith("+1") and len(e164) == 12:
        d = e164[2:]
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"
    return raw.strip()


def normalize_email(raw: str) -> str:
    value = (raw or "").strip().lower()
    return value if _EMAIL_RE.match(value) else ""


def normalize_name(raw: str) -> str:
    parts = [p for p in re.split(r"\s+", (raw or "").strip()) if p]
    return " ".join(p.capitalize() for p in parts)


def name_search_variants(raw: str) -> list[str]:
    """Legal-name spellings worth querying (Micheal/Michael)."""
    text = (raw or "").strip()
    if not text:
        return []
    out = [text]
    swapped = re.sub(r"\bMicheal\b", "Michael", text, flags=re.I)
    if swapped not in out:
        out.append(swapped)
    swapped = re.sub(r"\bMichael\b", "Micheal", text, flags=re.I)
    if swapped not in out:
        out.append(swapped)
    return out


def name_tokens(raw: str) -> list[str]:
    return [p.lower() for p in re.split(r"\s+", (raw or "").strip()) if p]


def email_local_part(email: str) -> str:
    norm = normalize_email(email)
    return norm.split("@", 1)[0] if norm else ""


_CTRL = re.compile(r"[\x00-\x1f\x7f<>]")
_QUOTED = re.compile(r'"([^"]+)"|\'([^\']+)\'')


def clean_supplied_handle(raw: str) -> str:
    """Keep spaces and slashes the user typed. Strip only controls and wrapping @."""
    handle = _CTRL.sub("", (raw or "").strip())
    handle = re.sub(r"^[@]+", "", handle)
    handle = re.sub(r"\s+", " ", handle).strip()
    return handle.lower()


def slug_handle(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "", (raw or "").lower()).strip("._-")


def url_handle(raw: str) -> str:
    """Encode a handle as a single URL path segment (spaces and / stay in the query)."""
    return quote(clean_supplied_handle(raw) or raw.strip(), safe="")


def is_simple_handle(raw: str) -> bool:
    """Platforms like GitHub/Reddit only allow this character set."""
    return bool(re.fullmatch(r"[a-z0-9._-]+", (raw or "").strip().lower()))


def handle_needles(handle: str) -> list[str]:
    """Raw + encoded forms to look for in a response body or final URL."""
    raw = clean_supplied_handle(handle) or (handle or "").strip().lower()
    out: list[str] = []
    for item in (raw, quote(raw, safe=""), quote_plus(raw)):
        if item and item not in out:
            out.append(item)
    return out


def split_usernames(raw: str) -> list[str]:
    text = raw or ""
    parts: list[str] = []
    cursor = 0
    for match in _QUOTED.finditer(text):
        before = text[cursor : match.start()]
        parts.extend(re.split(r"[,;]+", before))
        parts.append(match.group(1) or match.group(2) or "")
        cursor = match.end()
    parts.extend(re.split(r"[,;]+", text[cursor:]))
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        handle = clean_supplied_handle(part)
        if len(handle) < 2 or handle in seen:
            continue
        seen.add(handle)
        out.append(handle)
    return out


def username_candidates(name: str, email: str, extra: str = "") -> list[str]:
    tokens = name_tokens(name)
    first = tokens[0] if tokens else ""
    last = tokens[-1] if len(tokens) > 1 else ""
    middle = tokens[1] if len(tokens) > 2 else ""
    local = email_local_part(email)
    digits = re.sub(r"\D", "", local)
    local_alpha = re.sub(r"\d+", "", local)
    supplied = split_usernames(extra)
    guesses = [
        *supplied,
        *[slug_handle(h) for h in supplied],
        local,
        local_alpha,
        "".join(tokens),
        ".".join(tokens),
        "_".join(tokens),
        "-".join(tokens),
        f"{first}{last}",
        f"{first}.{last}",
        f"{first}_{last}",
        f"{first}-{last}",
        f"{first}{last}{digits}" if first and last and digits else "",
        f"{first}{digits}" if first and digits else "",
        f"{last}{digits}" if last and digits else "",
        f"{first}{middle}{last}" if first and last and middle else "",
        f"{first[0]}{last}" if first and last else "",
        f"{first}{last}{middle[:1]}" if first and last and middle else "",
    ]
    seen: set[str] = set()
    out: list[str] = []
    for g in guesses:
        if not g:
            continue
        keep = g.strip().lower() in {s.lower() for s in supplied} or any(ch in g for ch in " /")
        handle = clean_supplied_handle(g) if keep else slug_handle(g)
        min_len = 2 if keep else 3
        if len(handle) < min_len or handle in seen:
            continue
        seen.add(handle)
        out.append(handle)
    return out[:24]


def host_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def phone_search_forms(raw: str) -> list[str]:
    e164 = normalize_phone(raw)
    if not e164.startswith("+1") or len(e164) != 12:
        return [raw.strip()] if raw.strip() else []
    d = e164[2:]
    return [
        e164,
        d,
        f"{d[:3]}-{d[3:6]}-{d[6:]}",
        f"({d[:3]}) {d[3:6]}-{d[6:]}",
        f"{d[:3]}.{d[3:6]}.{d[6:]}",
        f"{d[:3]} {d[3:6]} {d[6:]}",
    ]


def phone_digits_in_text(phone: str, text: str) -> bool:
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())[-10:]
    compact = "".join(ch for ch in (text or "") if ch.isdigit())
    return bool(digits) and len(digits) >= 10 and digits in compact
