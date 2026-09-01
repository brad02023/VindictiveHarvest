from viha.core.normalize import (
    split_usernames,
    email_local_part,
    format_phone,
    handle_needles,
    name_search_variants,
    normalize_email,
    normalize_name,
    normalize_phone,
    phone_digits_in_text,
    phone_search_forms,
    slug_handle,
    url_handle,
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


def test_name_search_variants_micheal_michael():
    variants = name_search_variants("Ada Micheal Public")
    assert "Ada Micheal Public" in variants
    assert "Ada Michael Public" in variants
    assert phone_digits_in_text("202 555 0100", "(202) 555-0100 Phone number Owner Ada")


def test_normalize_name():
    assert normalize_name("ada example public") == "Ada Example Public"


def test_split_usernames():
    assert split_usernames("@Ada, steamguy; discord.one") == ["ada", "steamguy", "discord.one"]


def test_split_usernames_keeps_spaces_and_slashes():
    assert split_usernames("rm -rf /my/brain") == ["rm -rf /my/brain"]
    assert split_usernames('"rm -rf /my/brain", other') == ["rm -rf /my/brain", "other"]
    assert split_usernames("'foo / bar'; baz") == ["foo / bar", "baz"]


def test_username_candidates_keep_typed_special_handle():
    handles = username_candidates("", "", "rm -rf /my/brain")
    assert "rm -rf /my/brain" in handles
    assert "rm-rfmybrain" in handles
    assert slug_handle("rm -rf /my/brain") == "rm-rfmybrain"


def test_url_handle_encodes_one_path_segment():
    assert url_handle("rm -rf /my/brain") == "rm%20-rf%20%2Fmy%2Fbrain"
    needles = handle_needles("rm -rf /my/brain")
    assert "rm -rf /my/brain" in needles
    assert "rm%20-rf%20%2Fmy%2Fbrain" in needles
