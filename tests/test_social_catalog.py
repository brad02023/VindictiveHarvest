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
