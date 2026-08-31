from viha.core.edges import build_edges
from viha.core.expand import seed_from_fact
from viha.core.models import Case, Fact, Seed, Source
from viha.core.recipes import recipe_links, reverse_image_links
from viha.export.graphml import render_graphml


def test_recipes_include_name_and_tx_for_210():
    seed = Seed(full_name="Ada Example Public", phone="210 555 0100", email="ada@example.com", state="TX")
    labels = [l for l, _, _ in recipe_links(seed)]
    assert any("Instagram" in l for l in labels)
    assert any("SOS" in l for l in labels)
    assert any("email" in l.lower() or "Gravatar" in l for l in labels)


def test_reverse_image_links():
    links = reverse_image_links("https://example.com/p.jpg")
    assert len(links) >= 3
    assert all(u.startswith("http") for _, u in links)


def test_expand_username_into_seed():
    base = Seed(full_name="Ada Example")
    fact = Fact(
        predicate="username",
        value="github:adalovelace",
        section="social",
        confidence=0.8,
        source=Source(publisher="GitHub", url="https://github.com/adalovelace"),
        extra={"handle": "adalovelace"},
    )
    out = seed_from_fact(base, fact)
    assert "adalovelace" in out.username


def test_edges_and_graphml():
    case = Case(seed=Seed(full_name="Ada Example"))
    case.add_fact(
        Fact(
            predicate="email",
            value="ada@example.com",
            section="contact",
            confidence=1,
            source=Source(publisher="seed", url="viha://seed"),
        )
    )
    edges = build_edges(case)
    assert edges
    xml = render_graphml(case)
    assert "<graphml" in xml
    assert "ada@example.com" in xml
