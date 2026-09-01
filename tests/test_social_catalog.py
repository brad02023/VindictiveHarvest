from viha.collectors.social_catalog import extract_social_links, page_is_hit
from viha.core.normalize import username_candidates


def test_steam_hit_and_miss():
    site = {
        "hit_any": ["g_rgProfileData ="],
        "miss_any": ["The specified profile could not be found"],
    }
    assert page_is_hit(site, 200, 'var g_rgProfileData = {"url": "someone"', "someone")
    assert not page_is_hit(site, 200, "The specified profile could not be found.", "someone")
    assert not page_is_hit(site, 404, "", "someone")
    assert not page_is_hit(site, 200, "Welcome to Spotify", "someone", "https://open.spotify.com/")
    assert not page_is_hit(site, 200, "login please someone", "someone", "https://replit.com/login?goto=@someone")


def test_instagram_requires_handle_in_page():
    site = {"hit_any": ['"username":"{u}"'], "miss_any": ["Sorry, this page isn't available"]}
    assert page_is_hit(site, 200, '{"username":"brendonx"}', "brendonx")
    assert not page_is_hit(site, 200, '{"username":"other"}', "brendonx")


def test_page_is_hit_uses_profile_title():
    site = {"hit_any": ["isLiveBroadcast"]}
    assert page_is_hit(
        site,
        200,
        '<title>TheDJYouNeed - Twitch</title><meta property="og:title" content="TheDJYouNeed - Twitch">',
        "thedjyouneed",
        "https://www.twitch.tv/thedjyouneed",
    )
    assert not page_is_hit(
        site,
        200,
        '<title>Twitch</title><meta property="og:title" content="Twitch">',
        "thedjyouneed",
        "https://www.twitch.tv/thedjyouneed",
    )


def test_page_is_hit_x_title_and_skips_telegram_invite():
    x = {"hit_any": ['"screen_name":"{u}"']}
    assert page_is_hit(
        x,
        200,
        '<title>Brendon Cornell (@TheDJYouNeed) / X</title>',
        "thedjyouneed",
        "https://x.com/thedjyouneed",
    )
    tg = {"hit_any": ["tgme_page_title"]}
    assert not page_is_hit(
        tg,
        200,
        '<title>Telegram: Contact @thedjyouneed</title> If you have Telegram',
        "thedjyouneed",
        "https://t.me/thedjyouneed",
    )


def test_page_is_hit_rejects_roblox_error_dest():
    site = {"hit_any": ["- Roblox"], "handle_optional": True}
    assert not page_is_hit(
        site,
        200,
        "",
        "someone",
        "https://www.roblox.com/request-error?code=404",
    )


def test_page_is_hit_matches_encoded_handle():
    site = {"hit_any": ["g_rgProfileData ="]}
    handle = "rm -rf /my/brain"
    encoded = "rm%20-rf%20%2Fmy%2Fbrain"
    assert page_is_hit(
        site,
        200,
        "var g_rgProfileData = {}",
        handle,
        f"https://steamcommunity.com/id/{encoded}",
    )


def test_login_walls_are_not_hits():
    ig = {"hit_any": ['"username":"{u}"'], "miss_any": ["Log in • Instagram"]}
    assert not page_is_hit(
        ig,
        200,
        "<title>Log in • Instagram</title> Log in • Instagram",
        "thedjyouneed",
        "https://www.instagram.com/thedjyouneed/",
    )
    yt = {
        "hit_any": ["channelId", "og:type"],
        "miss_any": ["This page isn't available", "Sign in to continue to YouTube"],
    }
    assert not page_is_hit(
        yt,
        200,
        '<title>YouTube</title><meta property="og:type" content="website"> Sign in to continue to YouTube',
        "thedjyouneed",
        "https://www.youtube.com/@thedjyouneed",
    )
    li = {"hit_any": ["urn:li:member"], "miss_any": ["authwall", "Sign in to LinkedIn"]}
    assert not page_is_hit(
        li,
        200,
        "<title>LinkedIn: Log In or Sign Up</title> authwall Sign in to LinkedIn",
        "thedjyouneed",
        "https://www.linkedin.com/in/thedjyouneed",
    )


def test_user_not_found_page_is_not_a_hit():
    site = {"hit_any": ["speedrun.com/users/{u}"]}
    url = "https://www.speedrun.com/users/adaexample"
    assert not page_is_hit(
        site,
        200,
        "<title>User not found</title> User not found. That player does not exist.",
        "adaexample",
        url,
        requested_url=url,
    )
    steam = {"hit_any": ["g_rgProfileData ="]}
    steam_url = "https://steamcommunity.com/id/adaexample"
    assert not page_is_hit(
        steam,
        200,
        "<title>Steam Community :: Error</title> The specified profile could not be found.",
        "adaexample",
        steam_url,
        requested_url=steam_url,
    )


def test_redirect_off_profile_is_not_a_hit():
    site = {"hit_any": ["soundcloud:user"]}
    assert not page_is_hit(
        site,
        200,
        "soundcloud:user",
        "adaexample",
        "https://soundcloud.com/discover",
        requested_url="https://soundcloud.com/adaexample",
    )
    assert page_is_hit(
        {"hit_any": ["Gamerscore"]},
        200,
        "Gamerscore 12",
        "adaexample",
        "https://xboxgamertag.com/search/adaexample",
        requested_url="https://xboxgamertag.com/search/adaexample",
    )


def test_generic_spa_and_login_are_not_hits():
    assert not page_is_hit(
        {"hit_any": ["dailymotion"]},
        200,
        "<title>Dailymotion</title> dailymotion adaexample",
        "adaexample",
        "https://www.dailymotion.com/adaexample",
        requested_url="https://www.dailymotion.com/adaexample",
    )
    assert not page_is_hit(
        {"hit_any": ["fb://profile/", '"userID"']},
        200,
        '<title>Facebook</title> fb://profile/ "userID" adaexample',
        "adaexample",
        "https://www.facebook.com/login/?next=https://www.facebook.com/adaexample",
        requested_url="https://www.facebook.com/adaexample/",
    )
    assert not page_is_hit(
        {"hit_any": ["bsky.app/profile"]},
        200,
        '<title>Bluesky</title><meta property="og:type" content="profile"> bsky.app/profile',
        "adaexample",
        "https://bsky.app/profile/adaexample.bsky.social",
        requested_url="https://bsky.app/profile/adaexample.bsky.social",
    )


def test_exclusive_marker_without_title_is_still_a_hit():
    assert page_is_hit(
        {"hit_any": ["g_rgProfileData ="]},
        200,
        'var g_rgProfileData = {"url": "https://steamcommunity.com/id/someone"}',
        "someone",
        "https://steamcommunity.com/id/someone",
        requested_url="https://steamcommunity.com/id/someone",
    )


def test_facebook_profile_marker_is_a_hit():
    assert page_is_hit(
        {"hit_any": ["__isProfile"]},
        200,
        "<title>Ada Example (adaexample)</title> __isProfile",
        "adaexample",
        "https://www.facebook.com/adaexample",
        requested_url="https://www.facebook.com/adaexample",
    )


def test_extract_social_links():
    html = '<a href="https://steamcommunity.com/id/foo">s</a><a href="https://instagram.com/foo">'
    links = extract_social_links(html)
    plats = {p for p, _ in links}
    assert "steam" in plats
    assert "instagram" in plats


def test_username_candidates_include_email_digits():
    handles = username_candidates("Ada Example Public", "adaexample13@example.com")
    assert "adaexample13" in handles
    assert "adapublic13" in handles
