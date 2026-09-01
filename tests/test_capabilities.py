"""Capability defeat tests: hunt findings must display; social default is green only."""

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QTableWidget

from viha.collectors.github import github_search_hit_allowed
from viha.collectors.people import people_index_urls
from viha.collectors.social_catalog import load_sites
from viha.collectors.texas import _public_record_links
from viha.core.identity import corroborate_identity, extract_associates_from_text, extract_identity_from_text, persona_brief
from viha.core.models import Case, Fact, Seed, Source
from viha.core.normalize import name_search_variants
from viha.core.people_html import parse_people_index_html
from viha.core.recipes import recipe_links
from viha.gui.views.persona import PersonaView

ROOT = Path(__file__).resolve().parents[1]


def _qt_app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _src(pub: str, url: str = "") -> Source:
    return Source(publisher=pub, url=url or f"https://example.com/{pub}")


def _fact(pred: str, value: str, publisher: str, **kwargs) -> Fact:
    section = kwargs.pop("section", "identity")
    return Fact(
        predicate=pred,
        value=value,
        section=section,
        confidence=kwargs.pop("confidence", 0.62),
        source=_src(publisher),
        candidate=kwargs.pop("candidate", True),
        extra=kwargs.pop("extra", {}),
        **kwargs,
    )


def harvest_shaped_case() -> Case:
    """Ada-shaped stand-in for the public-source hunt (no operator PII)."""
    case = Case(seed=Seed(full_name="Ada Example Public", phone="202 555 0100", email="ada@example.com"))
    case.add_fact(_fact("age", "26", "FastPeopleSearch"))
    case.add_fact(_fact("age", "25", "Indexed people search"))
    case.add_fact(_fact("dob", "2000-07", "FastPeopleSearch"))
    case.add_fact(_fact("location", "Austin, TX", "FastPeopleSearch"))
    case.add_fact(_fact("address", "123 Main Street, Austin, TX 78701", "FastPeopleSearch", extra={"past": False}))
    case.add_fact(_fact("address", "500 Commerce Street, Dallas, TX", "FastPeopleSearch", extra={"past": True}))
    case.add_fact(_fact("email", "jane.neighbor@example.net", "FastPeopleSearch", section="contact", extra={"associate": True}))
    case.add_fact(_fact("associate", "Jane Neighbor", "FastPeopleSearch", extra={"associate": True}))
    case.add_fact(_fact("job", "Retail associate", "FastPeopleSearch", section="business"))
    case.add_fact(
        Fact(
            predicate="username",
            value="steam:ada-persona",
            section="social",
            confidence=0.78,
            source=_src("Steam", "https://steamcommunity.com/id/AdaExample23"),
            extra={"platform": "steam", "handle": "ada-persona", "via": "persona-search"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="youtube:adaexample",
            section="social",
            confidence=0.76,
            source=_src("YouTube", "https://www.youtube.com/@AdaExample"),
            extra={"platform": "youtube", "handle": "adaexample", "via": "persona-search"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="github:otherlogin",
            section="social",
            confidence=0.78,
            source=_src("GitHub", "https://github.com/otherlogin"),
            extra={"platform": "github", "handle": "otherlogin", "via": "persona-search"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="soundcloud:adaexample",
            section="social",
            confidence=0.76,
            source=_src("SoundCloud", "https://soundcloud.com/adaexample"),
            extra={"platform": "soundcloud", "handle": "adaexample", "via": "persona-search"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="speedrun:adaexample",
            section="social",
            confidence=0.76,
            source=_src("Speedrun", "https://www.speedrun.com/users/adaexample"),
            extra={"platform": "speedrun", "handle": "adaexample", "via": "persona-search"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="instagram:randomsmash",
            section="social",
            confidence=0.48,
            source=_src("Instagram", "https://instagram.com/randomsmash"),
            extra={"platform": "instagram", "handle": "randomsmash"},
            candidate=True,
        )
    )
    case.add_fact(
        Fact(
            predicate="miss",
            value="Facebook: adaexample",
            section="social",
            confidence=0.1,
            source=_src("Facebook", "https://facebook.com/adaexample"),
            extra={"miss": True},
            candidate=True,
        )
    )
    corroborate_identity(case)
    return case


def test_parsers_cover_hunt_title_shapes():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    bullet = extract_identity_from_text("Ada Example Public Age 26 • Austin, TX Born July 2000", seed)
    preds = {i["predicate"]: i["value"] for i in bullet}
    assert preds["age"] == "26"
    assert preds["location"] == "Austin, TX"
    assert preds["dob"] == "2000-07"
    intelius = extract_identity_from_text(
        "(202) 555-0100 Phone number Owner Ada E Public, Age 25 in San Antonio, TX",
        seed,
    )
    assert {i["predicate"]: i["value"] for i in intelius}["age"] == "25"
    assert extract_identity_from_text("Owner Ida Public, Age 24 in Dallas, TX", seed) == []


def test_broker_ages_stay_separate_candidates():
    case = harvest_shaped_case()
    ages = {f.value for f in case.facts if f.predicate == "age"}
    assert ages == {"25", "26"}
    assert all(f.candidate for f in case.facts if f.predicate == "age")


def test_associates_and_past_addresses_display():
    seed = Seed(full_name="Ada Example Public", email="ada@example.com", phone="202 555 0100")
    items = extract_associates_from_text(
        "Ada Example Public Related To: Jane Neighbor email jane.neighbor@example.net (512) 555-0199",
        seed,
    )
    assert any(i["predicate"] == "email" and "jane.neighbor" in i["value"] for i in items)
    case = harvest_shaped_case()
    brief = persona_brief(case)
    shown = " ".join(f.value for f in case.display_facts())
    assert "123 Main Street" in shown
    assert "Commerce Street" in shown
    assert "jane.neighbor@example.net" in shown
    assert any("Austin" in f.value or "Main Street" in f.value for f in brief["locations"])
    assert any("Main Street" in f.value or "Commerce" in f.value for f in brief["property"])
    assert brief["age"].value in {"25", "26"}
    assert brief["dob"].value == "2000-07"


def test_gui_default_is_green_social_only():
    case = harvest_shaped_case()
    social = [f for f in case.display_facts() if f.section == "social"]
    assert {f.value for f in social} == {
        "steam:ada-persona",
        "youtube:adaexample",
        "github:otherlogin",
        "soundcloud:adaexample",
        "speedrun:adaexample",
    }
    assert all(f.confidence >= 0.7 and not f.candidate for f in social)
    hidden_vals = {f.value for f in case.hidden_facts()}
    assert "instagram:randomsmash" in hidden_vals
    assert "Facebook: adaexample" in hidden_vals


def test_persona_view_brief_fills_from_candidates():
    _qt_app()
    case = harvest_shaped_case()
    view = PersonaView()
    view.render(case)
    assert "26" in view._brief_labels["age"].text() or "25" in view._brief_labels["age"].text()
    assert "2000-07" in view._brief_labels["dob"].text()
    loc = view._brief_labels["location"].text()
    assert "Austin" in loc or "Main Street" in loc
    assert "Retail" in view._brief_labels["job"].text()
    assert "Jane Neighbor" in view._brief_labels["relatives"].text()
    assert "fastpeoplesearch" in view._index_label.text().lower()
    assert "26" != "—"
    assert view._brief_labels["age"].text() != "—"
    cells = []
    for table in view.findChildren(QTableWidget):
        for row in range(table.rowCount()):
            item = table.item(row, 1)
            if item:
                cells.append(item.text())
    assert "steam:ada-persona" in cells
    assert "youtube:adaexample" in cells
    assert "instagram:randomsmash" not in cells
    assert "Facebook: adaexample" not in cells


def test_tx_210_has_guadalupe_not_hardcoded_street():
    seed = Seed(full_name="Ada Example Public", phone="210 555 0100")
    labels = " ".join(l for l, _, _ in _public_record_links(seed))
    recipes = " ".join(l for l, _, _ in recipe_links(seed))
    assert "Guadalupe CAD" in labels
    assert "Bexar" in labels
    assert "Guadalupe CAD" in recipes
    assert "Still Brook" not in labels + recipes
    urls = " ".join(u for _, u in people_index_urls(seed))
    assert "fastpeoplesearch.com" in urls


def test_micheal_variant_and_github_exact_name():
    assert "Ada Michael Public" in name_search_variants("Ada Micheal Public")
    assert github_search_hit_allowed("adaexample", "otherlogin", "AdaExample")
    assert not github_search_hit_allowed("adaexample", "unrelateduser", "Someone Else")


def test_spotify_in_catalog_and_no_constellation_module():
    names = {s["name"] for s in load_sites()}
    assert "Spotify" in names
    assert not (ROOT / "viha" / "gui" / "views" / "constellation.py").exists()


def test_saved_people_html_yields_display_hits():
    html = """
    <html><head>
    <title>Ada Example Public Age 26 • Austin, TX</title>
    <link rel="canonical" href="https://www.fastpeoplesearch.com/ada-example-public_id_G123">
    </head><body>
    Ada Example Public Age 26 • Austin, TX Born July 2000
    <h2>Current Address:</h2>
    <a href="/address/123-main-street-austin-tx">123 Main Street, Austin, TX 78701</a>
    <h2>Past Addresses:</h2>
    <a href="/address/500-commerce-street-dallas-tx">500 Commerce Street, Dallas, TX</a>
    <a href="mailto:jane.neighbor@example.net">jane.neighbor@example.net</a>
    </body></html>
    """
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100", email="ada@example.com")
    page = parse_people_index_html(html, seed)
    case = Case(seed=seed)
    for item in page.items:
        case.add_fact(
            Fact(
                predicate=item["predicate"],
                value=item["value"],
                section=item["section"],
                confidence=item["confidence"],
                source=_src(page.publisher, page.url),
                extra=item["extra"],
                candidate=True,
            )
        )
    shown = {f.predicate: f.value for f in case.display_facts()}
    assert shown.get("age") == "26"
    assert any("Main Street" in f.value for f in case.display_facts() if f.predicate == "address")
    assert any(f.predicate == "email" for f in case.display_facts())
