from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from viha.collectors.base import USER_AGENT, Collector
from viha.collectors.registry import enabled_collectors
from viha.core.edges import build_edges
from viha.core.models import Case, Fact, Seed, Source, utc_now
from viha.core.normalize import format_phone, normalize_email, normalize_name, normalize_phone

LogFn = Callable[[str], None]
FactFn = Callable[[Fact], None]


async def harvest_async(
    seed: Seed,
    *,
    selected: list[str] | None = None,
    on_log: LogFn | None = None,
    on_fact: FactFn | None = None,
    into: Case | None = None,
) -> Case:
    case = into or Case(title=f"Harvest — {seed.display_name()}", seed=seed)
    if into:
        case.seed = seed
        case.title = f"Harvest — {seed.display_name()}"
    logs: list[str] = []

    def log(msg: str) -> None:
        line = msg
        logs.append(line)
        case.logs.append(line)
        if on_log:
            on_log(line)

    if seed.is_empty():
        log("No seed provided.")
        return case

    _seed_facts(case, seed)
    collectors = enabled_collectors(selected)
    log(f"Reaping {len(collectors)} collectors for {seed.display_name()}")

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9"}
    limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    async with httpx.AsyncClient(headers=headers, limits=limits, follow_redirects=True) as client:

        async def run_one(collector: Collector) -> list[Fact]:
            try:
                return await collector.reap(seed, client, log)
            except Exception as exc:
                err = f"{collector.label} failed: {exc}"
                case.errors.append(err)
                log(err)
                return []

        bundles = await asyncio.gather(*(run_one(c) for c in collectors))

    for facts in bundles:
        for fact in facts:
            stored = case.add_fact(fact)
            if on_fact:
                on_fact(stored)

    build_edges(case)
    log(f"Done. {len(case.facts)} facts, {len(case.edges)} edges, {len(case.errors)} collector errors.")
    return case


def _seed_facts(case: Case, seed: Seed) -> None:
    src = Source(publisher="Operator seed", url="viha://seed", retrieved_at=utc_now(), collector="viha.seed")
    if seed.full_name.strip():
        case.add_fact(
            Fact(
                predicate="name",
                value=normalize_name(seed.full_name),
                section="identity",
                confidence=1.0,
                source=src,
            )
        )
    if seed.phone.strip():
        case.add_fact(
            Fact(
                predicate="phone",
                value=format_phone(seed.phone) or seed.phone,
                section="contact",
                confidence=1.0,
                source=src,
                extra={"e164": normalize_phone(seed.phone)},
            )
        )
    if seed.email.strip():
        case.add_fact(
            Fact(
                predicate="email",
                value=normalize_email(seed.email) or seed.email,
                section="contact",
                confidence=1.0,
                source=src,
            )
        )
    if seed.org.strip():
        case.add_fact(
            Fact(
                predicate="org",
                value=seed.org.strip(),
                section="business",
                confidence=1.0,
                source=src,
            )
        )


def harvest(
    seed: Seed,
    *,
    selected: list[str] | None = None,
    on_log: LogFn | None = None,
) -> Case:
    return asyncio.run(harvest_async(seed, selected=selected, on_log=on_log))
