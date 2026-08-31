from __future__ import annotations

from collections import defaultdict

from viha.core.models import Case, Fact


SECTIONS = [
    ("identity", "Identity"),
    ("contact", "Contact"),
    ("social", "Social"),
    ("legal", "Legal"),
    ("business", "Business"),
    ("sanctions", "Watchlists"),
    ("infra", "Web & infra"),
    ("web", "Web"),
    ("recipes", "Search recipes"),
]


def render_markdown(case: Case) -> str:
    lines = [
        f"# {case.title}",
        "",
        f"- Case: `{case.id}`",
        f"- Created: {case.created_at}",
        f"- Seed name: {case.seed.full_name or '—'}",
        f"- Seed phone: {case.seed.phone or '—'}",
        f"- Seed email: {case.seed.email or '—'}",
        "",
        "Public-source case file. Verify before use.",
        "",
    ]
    if case.notes.strip():
        lines += ["## Notes", "", case.notes.strip(), ""]
    if case.tags:
        lines += [f"Tags: {', '.join(case.tags)}", ""]
    grouped: dict[str, list[Fact]] = defaultdict(list)
    for fact in case.visible_facts():
        grouped[fact.section].append(fact)

    for key, label in SECTIONS:
        facts = grouped.get(key) or []
        if not facts:
            continue
        lines.append(f"## {label}")
        lines.append("")
        for fact in facts:
            conf = f"{fact.confidence:.2f}"
            lines.append(f"- **{fact.predicate}:** {fact.value}  ")
            lines.append(
                f"  source: [{fact.source.publisher}]({fact.source.url}) · confidence {conf}"
            )
        lines.append("")

    cands = case.candidates()
    if cands:
        lines.append("## Candidates")
        lines.append("")
        for fact in cands:
            lines.append(f"- {fact.predicate}: {fact.value} ({fact.source.publisher})")
        lines.append("")

    lines.append("## Sources")
    lines.append("")
    seen: set[str] = set()
    for fact in case.facts:
        url = fact.source.url
        if url in seen:
            continue
        seen.add(url)
        lines.append(f"- {fact.source.publisher}: {url}")
    return "\n".join(lines).rstrip() + "\n"
