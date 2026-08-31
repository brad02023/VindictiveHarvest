from __future__ import annotations

import xml.sax.saxutils as sax

from viha.core.edges import build_edges
from viha.core.models import Case


def render_graphml(case: Case) -> str:
    edges = case.edges or build_edges(case)
    labels: list[str] = []
    kinds: dict[str, str] = {}
    for lab, kind in [(case.seed.display_name(), "persona")] + [(f.value[:80], f.section) for f in case.facts]:
        if lab not in kinds:
            labels.append(lab)
            kinds[lab] = kind
    id_of = {lab: f"n{i}" for i, lab in enumerate(labels)}
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="kind" for="node" attr.name="kind" attr.type="string"/>',
        '<key id="rel" for="edge" attr.name="relation" attr.type="string"/>',
        '<key id="label" for="node" attr.name="label" attr.type="string"/>',
        '<graph id="VIHA" edgedefault="directed">',
    ]
    for lab, nid in id_of.items():
        lines.append(
            f'<node id="{nid}"><data key="kind">{sax.escape(kinds.get(lab, "fact"))}</data>'
            f'<data key="label">{sax.escape(lab)}</data></node>'
        )
    for edge in edges:
        a, b = id_of.get(edge.a), id_of.get(edge.b)
        if not a or not b:
            continue
        lines.append(
            f'<edge source="{a}" target="{b}"><data key="rel">{sax.escape(edge.relation)}</data></edge>'
        )
    lines += ["</graph>", "</graphml>"]
    return "\n".join(lines) + "\n"
