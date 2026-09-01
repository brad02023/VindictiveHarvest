from __future__ import annotations

from dataclasses import asdict

from viha.core.models import Fact, Seed
from viha.core.normalize import split_usernames


def seed_from_fact(base: Seed, fact: Fact) -> Seed:
    seed = Seed(**asdict(base))
    handle = str((fact.extra or {}).get("handle") or "")
    value = fact.value
    if fact.predicate == "email" or "@" in value:
        seed.email = value.split()[0]
    elif fact.predicate == "phone":
        seed.phone = value
    elif fact.predicate == "org" or fact.predicate == "company":
        seed.org = value.split("·")[0].strip()
    elif fact.predicate in {"username", "social_mention"} or handle:
        raw = handle or value.split(":")[-1]
        if "://" in raw:
            raw = raw.rstrip("/").split("/")[-1]
        raw = raw.lstrip("@")
        existing = split_usernames(seed.username)
        if raw and raw.lower() not in existing:
            existing.append(raw)
        seed.username = ", ".join(existing)
    elif fact.predicate == "name":
        seed.full_name = value
    return seed
