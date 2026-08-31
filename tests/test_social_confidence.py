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


def test_name_in_text_requires_first_and_last():
    seed = Seed(full_name="Ada Example Public")
    assert _name_in_text("Ada E Public, Age 25", seed)
    assert not _name_in_text("Public University Business School", seed)
