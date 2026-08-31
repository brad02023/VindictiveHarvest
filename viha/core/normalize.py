from __future__ import annotations

import re
from urllib.parse import urlparse


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


def name_tokens(raw: str) -> list[str]:
    return [p.lower() for p in re.split(r"\s+", (raw or "").strip()) if p]


def email_local_part(email: str) -> str:
    norm = normalize_email(email)
    return norm.split("@", 1)[0] if norm else ""


def split_usernames(raw: str) -> list[str]:
    parts = re.split(r"[,;]+", raw or "")
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        handle = re.sub(r"^[@]+", "", part.strip().lower())
        handle = re.sub(r"[^a-z0-9._-]", "", handle)
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
    guesses = [
        *split_usernames(extra),
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
        handle = re.sub(r"[^a-zA-Z0-9._-]", "", (g or "").lower()).strip("._-")
        if len(handle) < 3 or handle in seen:
            continue
        seen.add(handle)
        out.append(handle)
    return out[:16]


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
