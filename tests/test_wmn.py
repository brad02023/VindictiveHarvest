from viha.collectors.social_catalog import dest_is_search_dump, wmn_account_exists


def test_wmn_exists_uses_e_string_not_m_string():
    chess = {
        "m_code": 404,
        "m_string": '"code":0',
        "e_code": 200,
        "e_string": '"player_id":',
    }
    assert wmn_account_exists(chess, 200, '{"player_id": 1, "username": "hikaru"}')
    assert not wmn_account_exists(chess, 404, '{"code":0,"message":"not found"}')


def test_wmn_facebook_login_is_missing():
    fb = {
        "m_code": 200,
        "m_string": "<title>Facebook</title>",
        "e_code": 200,
        "e_string": "__isProfile",
    }
    assert not wmn_account_exists(fb, 200, "<title>Facebook</title> Log in or sign up to view")
    assert wmn_account_exists(
        fb,
        200,
        "<title>Ada Public</title> __isProfile",
    )


def test_wmn_bitbucket_404_is_missing():
    bb = {
        "m_code": 404,
        "m_string": "No workspace with identifier",
        "e_code": 200,
        "e_string": "full_name",
    }
    assert not wmn_account_exists(bb, 404, '{"type": "error", "error": {"message": "No workspace with identifier"}}')
    assert wmn_account_exists(bb, 200, '{"values": [{"full_name": "ada/repo"}]}')


def test_wmn_dailymotion_api():
    dm = {
        "m_code": 404,
        "m_string": '"code":404',
        "e_code": 200,
        "e_string": '"id":',
    }
    assert not wmn_account_exists(dm, 404, '{"error":{"code":404,"message":"Can not find the requested user"}}')
    assert wmn_account_exists(dm, 200, '{"id":"x1","username":"adaexample"}')


def test_search_dump_urls_are_not_profiles():
    assert dest_is_search_dump(
        "https://dota2.ru/forum/search/?type=user&keywords=adaexample&sort_by=username",
        "adaexample",
    )
    assert not dest_is_search_dump(
        "https://xboxgamertag.com/search/adaexample",
        "adaexample",
    )
