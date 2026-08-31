from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import httpx

from viha.core.models import Fact, Seed, Source, utc_now

USER_AGENT = "VIHA/0.1 (Vindictive Harvest; local public-source research)"
TIMEOUT = 18.0

LogFn = Callable[[str], None]


class CollectorError(Exception):
    pass


class Collector:
    id: str = ""
    label: str = ""
    blurb: str = ""
    default_on: bool = True

    async def reap(self, seed: Seed, client: httpx.AsyncClient, log: LogFn) -> list[Fact]:
        raise NotImplementedError

    def fact(
        self,
        *,
        predicate: str,
        value: str,
        section: str,
        confidence: float,
        url: str,
        publisher: str,
        raw: Any = "",
        extra: dict[str, Any] | None = None,
        candidate: bool = False,
        note: str = "",
    ) -> Fact:
        if not isinstance(raw, str):
            try:
                raw = json.dumps(raw, ensure_ascii=True)[:4000]
            except TypeError:
                raw = str(raw)[:4000]
        fact = Fact(
            predicate=predicate,
            value=value.strip(),
            section=section,
            confidence=max(0.0, min(1.0, confidence)),
            source=Source(
                publisher=publisher,
                url=url,
                retrieved_at=utc_now(),
                note=note,
                collector=self.id,
            ),
            raw=raw[:4000],
            extra=extra or {},
            candidate=candidate,
        )
        if fact.raw:
            fact.extra.setdefault("sha256_16", hashlib.sha256(fact.raw.encode("utf-8", "replace")).hexdigest()[:16])
        return fact


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    r = await client.get(url, params=params, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    r = await client.get(url, params=params, headers=headers, timeout=TIMEOUT, follow_redirects=True)
    return r.status_code, str(r.url), r.text
