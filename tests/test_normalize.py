from viha.core.normalize import (
    split_usernames,
    email_local_part,
    format_phone,
    normalize_email,
    normalize_name,
    normalize_phone,
    phone_search_forms,
    username_candidates,
)


def test_normalize_phone_us():
    assert normalize_phone("202 555 0100") == "+12025550100"
    assert normalize_phone("1-202-555-0100") == "+12025550100"
    assert format_phone("2025550100") == "(202) 555-0100"


def test_normalize_email():
    assert normalize_email("  AdaExample13@Example.com ") == "adaexample13@example.com"
    assert normalize_email("not-an-email") == ""
    assert email_local_part("adaexample13@example.com") == "adaexample13"


def test_username_candidates():
    handles = username_candidates("Ada Example Public", "adaexample13@example.com")
    assert "adaexample13" in handles
    assert "adapublic" in handles or "ada.example.public" in handles
    assert all(len(h) >= 3 for h in handles)


def test_phone_search_forms():
    forms = phone_search_forms("202-555-0100")
    assert "2025550100" in forms
    assert "202-555-0100" in forms


def test_normalize_name():
    assert normalize_name("ada example public") == "Ada Example Public"


def test_split_usernames():
    assert split_usernames("@Ada, steamguy; discord.one") == ["ada", "steamguy", "discord.one"]
