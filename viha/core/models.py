from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class Seed:
    full_name: str = ""
    phone: str = ""
    email: str = ""
    org: str = ""
    city: str = ""
    state: str = ""
    username: str = ""

    def display_name(self) -> str:
        name = self.full_name.strip()
        if name:
            return name.title()
        if self.email:
            return self.email.split("@", 1)[0]
        if self.phone:
            return self.phone
        if self.org:
            return self.org
        return "Unknown persona"

    def is_empty(self) -> bool:
        return not any(
            [
                self.full_name.strip(),
                self.phone.strip(),
                self.email.strip(),
                self.org.strip(),
                self.username.strip(),
            ]
        )


@dataclass
class Source:
    publisher: str
    url: str
    retrieved_at: str = field(default_factory=utc_now)
    note: str = ""
    collector: str = ""

    def chip(self) -> str:
        return self.publisher


@dataclass
class Fact:
    predicate: str
    value: str
    section: str
    confidence: float
    source: Source
    id: str = field(default_factory=lambda: new_id("viha.fact"))
    raw: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    pinned: bool = False
    candidate: bool = False

    def key(self) -> tuple[str, str]:
        return (self.predicate, self.value.strip().lower())


def is_lookup_fact(fact: Fact) -> bool:
    extra = fact.extra or {}
    if extra.get("lookup") or extra.get("kind") == "recipe":
        return True
    if fact.predicate == "recipe":
        return True
    if fact.source.publisher in {"Search recipe", "Public record portal", "Texas public record"}:
        return True
    return False


def is_miss_fact(fact: Fact) -> bool:
    extra = fact.extra or {}
    return bool(extra.get("miss") or extra.get("kind") == "miss" or fact.predicate == "miss")


def is_deferred_row(fact: Fact) -> bool:
    """Lookups, 404s, and unconfirmed social (not green) stay behind SHOW MISSES."""
    if is_lookup_fact(fact) or is_miss_fact(fact):
        return True
    if fact.section == "social" and (fact.candidate or fact.confidence < 0.7):
        return True
    return False


@dataclass
class Edge:
    a: str
    b: str
    relation: str
    source_url: str = ""


@dataclass
class Case:
    id: str = field(default_factory=lambda: new_id("viha.case"))
    title: str = "Untitled harvest"
    created_at: str = field(default_factory=utc_now)
    seed: Seed = field(default_factory=Seed)
    facts: list[Fact] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def add_fact(self, fact: Fact) -> Fact:
        for existing in self.facts:
            if existing.key() == fact.key():
                extra_sources = existing.extra.setdefault("sources", [])
                chip = {
                    "publisher": fact.source.publisher,
                    "url": fact.source.url,
                    "collector": fact.source.collector,
                }
                if chip not in extra_sources and fact.source.url != existing.source.url:
                    extra_sources.append(chip)
                existing.confidence = max(existing.confidence, fact.confidence)
                if fact.pinned:
                    existing.pinned = True
                if not fact.candidate:
                    existing.candidate = False
                return existing
        self.facts.append(fact)
        return fact

    def facts_in(self, section: str) -> list[Fact]:
        return [f for f in self.facts if f.section == section]

    def visible_facts(self) -> list[Fact]:
        return [f for f in self.facts if not is_lookup_fact(f) and not is_miss_fact(f)]

    def candidates(self) -> list[Fact]:
        return [f for f in self.facts if f.candidate and not f.pinned]

    def hit_facts(self) -> list[Fact]:
        """Resolved findings, including unverified candidates. Lookups and 404s stay hidden."""
        return self.visible_facts()

    def display_facts(self) -> list[Fact]:
        """GUI default rows: identity candidates stay; social is green confirmed only."""
        return [f for f in self.facts if not is_deferred_row(f)]

    def hidden_facts(self) -> list[Fact]:
        return [f for f in self.facts if is_deferred_row(f)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "seed": asdict(self.seed),
            "facts": [
                {
                    **{k: v for k, v in asdict(f).items() if k != "source"},
                    "source": asdict(f.source),
                }
                for f in self.facts
            ],
            "edges": [asdict(e) for e in self.edges],
            "logs": self.logs,
            "errors": self.errors,
            "notes": self.notes,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Case:
        facts = []
        for raw in data.get("facts", []):
            src = raw.get("source", {})
            facts.append(
                Fact(
                    id=raw.get("id", new_id("viha.fact")),
                    predicate=raw.get("predicate", ""),
                    value=raw.get("value", ""),
                    section=raw.get("section", ""),
                    confidence=float(raw.get("confidence", 0)),
                    source=Source(**{k: src[k] for k in Source.__dataclass_fields__ if k in src}),
                    raw=raw.get("raw", ""),
                    extra=raw.get("extra") or {},
                    pinned=bool(raw.get("pinned")),
                    candidate=bool(raw.get("candidate")),
                )
            )
        return cls(
            id=data.get("id", new_id("viha.case")),
            title=data.get("title", "Untitled harvest"),
            created_at=data.get("created_at", utc_now()),
            seed=Seed(**{k: data.get("seed", {}).get(k, "") for k in Seed.__dataclass_fields__}),
            facts=facts,
            edges=[Edge(**e) for e in data.get("edges", [])],
            logs=list(data.get("logs", [])),
            errors=list(data.get("errors", [])),
            notes=data.get("notes", ""),
            tags=list(data.get("tags", [])),
        )
