from viha.collectors.search import _name_in_text
from viha.collectors.social import handle_is_strong, mark_social_confidence
from viha.core.models import Fact, Seed, Source


def _fact(platform: str, handle: str, confidence: float = 0.84) -> Fact:
    return Fact(
        predicate="username",
        value=f"{platform}:{handle}",
        section="social",
        confidence=confidence,
        source=Source(publisher=platform, url=f"https://example.com/{handle}"),
        extra={"platform": platform, "handle": handle},
    )


def test_email_local_with_digits_is_strong():
    seed = Seed(email="adaexample13@example.com", full_name="Ada Example Public")
    assert handle_is_strong("adaexample13", seed)
    assert not handle_is_strong("adaexample", seed)
    assert not handle_is_strong("adapublic", seed)


def test_operator_username_is_strong():
    seed = Seed(username="exacthandle", full_name="Ada Example Public")
    assert handle_is_strong("exacthandle", seed)
    assert not handle_is_strong("adaexamplepublic", seed)


def test_operator_username_with_slash_is_strong():
    seed = Seed(username="rm -rf /my/brain")
    assert handle_is_strong("rm -rf /my/brain", seed)
    assert not handle_is_strong("rm-rfmybrain", seed)


def test_name_smash_profiles_are_candidates():
    seed = Seed(full_name="Ada Lovelace")
    facts = mark_social_confidence(
        [
            _fact("github", "adalovelace"),
            _fact("github", "alovelace"),
            _fact("gitlab", "AdaLovelace"),
        ],
        seed,
    )
    assert all(f.candidate for f in facts)
    assert all(f.confidence <= 0.48 for f in facts)


def test_strong_handle_stays_confirmed_and_dedupes_platform():
    seed = Seed(email="adalovelace13@example.com")
    facts = mark_social_confidence(
        [_fact("github", "adalovelace13"), _fact("github", "alovelace")],
        seed,
    )
    by_handle = {f.extra["handle"]: f for f in facts}
    assert by_handle["adalovelace13"].candidate is False
    assert by_handle["alovelace"].candidate is True


def test_github_identity_fields_do_not_crash_confidence():
    seed = Seed(username="adaexample")
    profile = _fact("github", "adaexample", confidence=0.86)
    aka = Fact(
        predicate="aka",
        value="Ada Example",
        section="identity",
        confidence=0.7,
        source=Source(publisher="GitHub", url="https://github.com/adaexample"),
        extra={"handle": "adaexample", "via": "github-profile"},
        candidate=False,
    )
    loc = Fact(
        predicate="location",
        value="Austin, TX",
        section="identity",
        confidence=0.7,
        source=Source(publisher="GitHub", url="https://github.com/adaexample"),
        extra={"handle": "adaexample", "via": "github-profile"},
        candidate=False,
    )
    mark_social_confidence([profile, aka, loc], seed)
    assert profile.candidate is False
    assert profile.confidence >= 0.7
    assert aka.predicate == "aka"
    assert aka.candidate is False
    assert loc.candidate is False


def test_display_name_github_stays_green_beside_exact_login():
    seed = Seed(username="adaexample")
    exact = _fact("github", "adaexample", confidence=0.86)
    display = Fact(
        predicate="username",
        value="github:otherlogin",
        section="social",
        confidence=0.78,
        source=Source(publisher="GitHub", url="https://github.com/otherlogin"),
        extra={"platform": "github", "handle": "otherlogin", "via": "persona-search"},
    )
    mark_social_confidence([exact, display], seed)
    assert exact.candidate is False
    assert display.candidate is False
    assert display.confidence >= 0.7


def test_persona_search_via_is_confirmed():
    seed = Seed(username="rm -rf /my/brain")
    fact = Fact(
        predicate="username",
        value="steam:rm -rf /my/brain",
        section="social",
        confidence=0.76,
        source=Source(publisher="Steam", url="https://steamcommunity.com/id/AdaExample"),
        extra={"platform": "steam", "handle": "rm -rf /my/brain", "via": "persona-search"},
    )
    mark_social_confidence([fact], seed)
    assert fact.candidate is False
    assert fact.confidence >= 0.76


def test_strong_handle_bumps_to_green():
    seed = Seed(username="exacthandle")
    fact = _fact("steam", "exacthandle", confidence=0.62)
    mark_social_confidence([fact], seed)
    assert fact.candidate is False
    assert fact.confidence >= 0.7


def test_name_in_text_requires_first_and_last():
    seed = Seed(full_name="Ada Example Public")
    assert _name_in_text("Ada E Public, Age 25", seed)
    assert not _name_in_text("Public University Business School", seed)
