from viha.core.models import Case, Fact, Seed, Source
from viha.export.case_md import render_markdown


def test_fact_merge_keeps_sources():
    case = Case(seed=Seed(full_name="Test Person"))
    a = Fact(
        predicate="username",
        value="github:demo",
        section="social",
        confidence=0.4,
        source=Source(publisher="GitHub", url="https://github.com/demo"),
        candidate=True,
    )
    b = Fact(
        predicate="username",
        value="github:demo",
        section="social",
        confidence=0.8,
        source=Source(publisher="Web search", url="https://example.com"),
        candidate=False,
    )
    case.add_fact(a)
    case.add_fact(b)
    assert len(case.facts) == 1
    assert case.facts[0].confidence == 0.8
    assert case.facts[0].candidate is False
    assert case.facts[0].extra["sources"]


def test_markdown_export_includes_persona():
    case = Case(title="Harvest — Test", seed=Seed(full_name="Test Person", email="t@example.com"))
    case.add_fact(
        Fact(
            predicate="email",
            value="t@example.com",
            section="contact",
            confidence=1.0,
            source=Source(publisher="Operator seed", url="viha://seed"),
        )
    )
    md = render_markdown(case)
    assert "Test Person" in md
    assert "t@example.com" in md
    assert "Contact" in md
