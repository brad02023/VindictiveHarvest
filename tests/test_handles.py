from viha.collectors.social import handle_is_strong, hunt_handles
from viha.core.handles import fill_url, probe_urls, shape_handle
from viha.core.models import Case, Fact, Seed, Source, is_lookup_fact


def test_shape_github_strips_dots_and_spaces():
    assert shape_handle("ada.example", "github")[0] == "ada-example"
    assert "brendon-cornell" in shape_handle("brendon cornell", "github")


def test_shape_instagram_prefers_dots():
    forms = shape_handle("brendon cornell", "instagram")
    assert forms[0] in {"brendon.cornell", "brendon_cornell", "brendoncornell"}
    assert all(" " not in f and "/" not in f for f in forms)


def test_shape_x_no_dots_max_15():
    forms = shape_handle("ada.example", "x")
    assert forms[0] == "ada_example"
    assert all("." not in f and len(f) <= 15 for f in forms)
    assert shape_handle("ada.example.public", "x") == []


def test_shape_discord_only_snowflake():
    assert shape_handle("coolname", "discord") == []
    assert shape_handle("123456789012345678", "discord") == ["123456789012345678"]


def test_probe_urls_use_site_legal_path():
    site = {"name": "Instagram", "style": "instagram", "url": "https://www.instagram.com/{u}/"}
    pairs = probe_urls(site, "rm -rf /my/brain")
    assert pairs
    for shaped, url in pairs:
        assert " " not in shaped
        assert "/" not in shaped
        assert "%2F" not in url
        assert f"/{shaped}/" in url


def test_youtube_tries_at_and_user():
    site = {
        "name": "YouTube",
        "style": "youtube",
        "url": "https://www.youtube.com/@{u}",
        "urls": ["https://www.youtube.com/@{u}", "https://www.youtube.com/user/{u}"],
    }
    urls = [u for _, u in probe_urls(site, "adaexample")]
    assert "https://www.youtube.com/@adaexample" in urls
    assert "https://www.youtube.com/user/adaexample" in urls


def test_fill_query_placeholder():
    url = fill_url("https://xboxgamertag.com/search/{q}", "brendoncornell", "brendon cornell")
    assert "brendon+cornell" in url or "brendon%20cornell" in url


def test_shape_does_not_truncate_into_a_different_user():
    assert shape_handle("brendonmicheal13", "x") == []
    assert shape_handle("thedjyouneed", "x") == ["thedjyouneed"]


def test_hunt_keeps_all_typed_usernames_and_name_smash():
    seed = Seed(
        full_name="Ada Example Public",
        email="adaexample13@example.com",
        username="onehandle, twohandle, threehandle, fourhandle",
    )
    handles = hunt_handles(seed)
    for needed in ("onehandle", "twohandle", "threehandle", "fourhandle", "adaexample13", "adaexamplepublic"):
        assert needed in handles


def test_shaped_supplied_handle_is_strong():
    seed = Seed(username="brendon cornell")
    assert handle_is_strong("brendon-cornell", seed)
    assert handle_is_strong("brendon.cornell", seed)


def test_lookup_facts_are_hidden():
    case = Case(seed=Seed(full_name="Ada"))
    case.add_fact(
        Fact(
            predicate="recipe",
            value="Steam search",
            section="recipes",
            confidence=0.3,
            source=Source(publisher="Search recipe", url="https://example.com"),
            extra={"kind": "recipe", "lookup": True},
        )
    )
    case.add_fact(
        Fact(
            predicate="email",
            value="a@example.com",
            section="contact",
            confidence=1.0,
            source=Source(publisher="Operator seed", url="viha://seed"),
        )
    )
    assert is_lookup_fact(case.facts[0])
    assert [f.predicate for f in case.hit_facts()] == ["email"]
    assert len(case.hidden_facts()) == 1


def test_candidate_identity_counts_as_hit_not_miss():
    case = Case(seed=Seed(full_name="Ada Example Public"))
    case.add_fact(
        Fact(
            predicate="age",
            value="26",
            section="identity",
            confidence=0.62,
            source=Source(publisher="Indexed people search", url="https://example.com/age"),
            candidate=True,
        )
    )
    case.add_fact(
        Fact(
            predicate="miss",
            value="Instagram: adaexample",
            section="social",
            confidence=0.1,
            source=Source(publisher="Instagram", url="https://instagram.com/adaexample"),
            extra={"miss": True},
            candidate=True,
        )
    )
    assert [f.predicate for f in case.hit_facts()] == ["age"]
    assert [f.predicate for f in case.hidden_facts()] == ["miss"]
    assert [f.predicate for f in case.display_facts()] == ["age"]


def test_weak_social_hidden_from_gui_default():
    case = Case(seed=Seed(full_name="Ada Example Public", username="exacthandle"))
    case.add_fact(
        Fact(
            predicate="username",
            value="steam:exacthandle",
            section="social",
            confidence=0.78,
            source=Source(publisher="Steam", url="https://steamcommunity.com/id/exacthandle"),
            extra={"platform": "steam", "handle": "exacthandle"},
            candidate=False,
        )
    )
    case.add_fact(
        Fact(
            predicate="username",
            value="github:adalovelace",
            section="social",
            confidence=0.48,
            source=Source(publisher="GitHub", url="https://github.com/adalovelace"),
            extra={"platform": "github", "handle": "adalovelace"},
            candidate=True,
        )
    )
    shown = [f.value for f in case.display_facts()]
    hidden = [f.value for f in case.hidden_facts()]
    assert "steam:exacthandle" in shown
    assert "github:adalovelace" in hidden
    assert "github:adalovelace" not in shown
