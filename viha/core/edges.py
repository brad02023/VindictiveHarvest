from __future__ import annotations

from viha.core.models import Case, Edge


def build_edges(case: Case) -> list[Edge]:
    persona = case.seed.display_name()
    edges: list[Edge] = []
    seen: set[tuple[str, str, str]] = set()
    for fact in case.facts:
        rel = {
            "phone": "uses_phone",
            "email": "uses_email",
            "username": "appears_as",
            "docket": "party_in",
            "filing": "mentioned_in",
            "officer": "officer_of",
            "company": "related_org",
            "org": "related_org",
            "recipe": "search_recipe",
            "subdomain": "controls",
            "dns_a": "resolves",
            "certificate": "has_cert",
            "wayback": "archived",
            "photo": "pictured_as",
            "age": "aged",
            "dob": "born",
            "location": "located_in",
            "address": "addressed_at",
            "charge": "charged_in",
            "property": "property_record",
            "employer": "employed_by",
            "occupation": "works_as",
            "gps": "seen_at",
        }.get(fact.predicate, f"has_{fact.predicate}")
        key = (persona, fact.value[:80], rel)
        if key in seen:
            continue
        seen.add(key)
        edges.append(Edge(a=persona, b=fact.value[:80], relation=rel, source_url=fact.source.url))
    case.edges = edges
    return edges
