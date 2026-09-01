from __future__ import annotations

import re


def persona_key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def identity_match(query: str, *names: str) -> bool:
    """True when a search result is the same identity as the typed handle.

    Display names and logins must match after case/spacing fold. Hyphens stay,
    so ``thedjyouneed`` does not equal ``the-dj-you-need``.
    """
    want = persona_key(query)
    if not want:
        return False
    return any(persona_key(raw) == want for raw in names if raw)
