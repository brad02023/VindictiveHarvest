from __future__ import annotations

from viha.core.models import Case, Fact


def fact_keyset(case: Case) -> set[tuple[str, str]]:
    return {f.key() for f in case.facts}


def new_facts(current: Case, previous: Case | None) -> list[Fact]:
    if previous is None:
        return list(current.facts)
    prior = fact_keyset(previous)
    return [f for f in current.facts if f.key() not in prior]


def diff_summary(current: Case, previous: Case | None) -> str:
    if previous is None:
        return f"First harvest — {len(current.facts)} facts."
    added = new_facts(current, previous)
    gone = [f for f in previous.facts if f.key() not in fact_keyset(current)]
    return f"+{len(added)} new   −{len(gone)} gone   ({len(current.facts)} total)"
