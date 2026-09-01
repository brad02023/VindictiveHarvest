from viha.collectors.github import github_search_hit_allowed
from viha.core.persona import identity_match, persona_key
from viha.core.persona_search import (
    match_bluesky_actors,
    match_roblox_users,
    match_soundcloud_users,
    match_speedrun_users,
    match_twitch_users,
    match_youtube_channels,
    merge_persona_targets,
)
from viha.core.steam import match_steam_personas


def test_identity_match_is_exact():
    assert identity_match("rm -rf /my/brain", "rm -rf /my/brain")
    assert identity_match("thedjyouneed", "TheDJYouNeed")
    assert identity_match("thedjyouneed", "THE DJ YOU NEED", "thedjyouneed")
    assert not identity_match("thedjyouneed", "THE DJ YOU NEED")
    assert not identity_match("thedjyouneed", "The DJ You Need", "the-dj-you-need")
    assert not identity_match("rm -rf /my/brain", "sudo rm -rf /")
    assert not identity_match("rm -rf /", "rm -rf /my/brain")
    assert not identity_match("thedjyouneed", "brad02023")
    assert not identity_match("rm -rf /my/brain", "RmRfMyEx")
    assert persona_key("  RM -rf   /my/brain ") == "rm -rf /my/brain"


def test_merge_puts_search_hits_first():
    vanity = [("rm-rf-my-brain", "https://steamcommunity.com/id/rm-rf-my-brain")]
    found = [("rm -rf /my/brain", "https://steamcommunity.com/id/JordanJoestar23")]
    merged = merge_persona_targets(vanity, found, "rm -rf /my/brain")
    assert merged[0][1].endswith("JordanJoestar23")
    assert merged[0][0] == "rm -rf /my/brain"


def test_youtube_keeps_exact_channel_not_bts_noise():
    payload = {
        "contents": {
            "channelRenderer": {
                "channelId": "UCreal",
                "title": {"simpleText": "TheDJYouNeed"},
                "navigationEndpoint": {"browseEndpoint": {"canonicalBaseUrl": "/@TheDJYouNeed"}},
            },
            "extra": {
                "channelRenderer": {
                    "channelId": "UCnoise",
                    "title": {"simpleText": "RM's Sexy Brain"},
                    "navigationEndpoint": {"browseEndpoint": {"canonicalBaseUrl": "/@rmssexybrain"}},
                }
            },
        }
    }
    assert match_youtube_channels(payload, "thedjyouneed") == [
        ("TheDJYouNeed", "https://www.youtube.com/@TheDJYouNeed")
    ]
    assert match_youtube_channels(payload, "rm -rf /my/brain") == []


def test_roblox_requires_exact_display_or_login():
    payload = {
        "data": [
            {"id": 1, "name": "rms_2033", "displayName": "rms"},
            {"id": 9, "name": "OtherLogin99", "displayName": "thedjyouneed"},
            {"id": 266806662, "name": "TheDjYouNeed", "displayName": "TheDjYouNeed"},
        ]
    }
    hits = match_roblox_users(payload, "thedjyouneed")
    assert hits == [("TheDjYouNeed", "https://www.roblox.com/users/266806662/profile")]
    assert match_roblox_users(payload, "rm -rf /my/brain") == []


def test_soundcloud_matches_display_or_permalink():
    payload = {
        "collection": [
            {"username": "RmRfMyEx", "permalink": "rmrfmyex", "permalink_url": "https://soundcloud.com/rmrfmyex"},
            {
                "username": "THE DJ YOU NEED",
                "permalink": "thedjyouneed",
                "permalink_url": "https://soundcloud.com/thedjyouneed",
            },
            {
                "username": "The DJ You Need",
                "permalink": "the-dj-you-need",
                "permalink_url": "https://soundcloud.com/the-dj-you-need",
            },
        ]
    }
    hits = match_soundcloud_users(payload, "thedjyouneed")
    assert hits == [("THE DJ YOU NEED", "https://soundcloud.com/thedjyouneed")]
    assert match_soundcloud_users(payload, "rm -rf /my/brain") == []


def test_twitch_drops_fuzzy_brads():
    payload = {
        "data": {
            "searchFor": {
                "channels": {
                    "items": [
                        {"login": "brad1221348", "displayName": "brad1221348"},
                        {"login": "brad02023", "displayName": "Brad02023"},
                    ]
                }
            }
        }
    }
    assert match_twitch_users(payload, "brad02023") == [("Brad02023", "https://www.twitch.tv/brad02023")]
    assert match_twitch_users(payload, "thedjyouneed") == []


def test_speedrun_and_bluesky_exact_only():
    speed = {
        "data": [
            {
                "names": {"international": "TheDJYouNeed"},
                "weblink": "https://www.speedrun.com/users/TheDJYouNeed",
            }
        ]
    }
    assert match_speedrun_users(speed, "thedjyouneed") == [
        ("TheDJYouNeed", "https://www.speedrun.com/users/TheDJYouNeed")
    ]
    assert match_speedrun_users(speed, "rm -rf /my/brain") == []

    bsky = {
        "actors": [
            {"displayName": "Robert Reich", "handle": "rbreich.bsky.social"},
            {"displayName": "thedjyouneed", "handle": "thedjyouneed.bsky.social"},
        ]
    }
    assert match_bluesky_actors(bsky, "thedjyouneed") == [
        ("thedjyouneed", "https://bsky.app/profile/thedjyouneed.bsky.social")
    ]
    assert match_bluesky_actors(bsky, "rm -rf /my/brain") == []


def test_github_search_does_not_keep_unrelated_login():
    assert not github_search_hit_allowed("thedjyouneed", "brad02023")
    assert github_search_hit_allowed("brad02023", "brad02023")
    assert github_search_hit_allowed("rm -rf /my/brain", "otherlogin", "rm -rf /my/brain")
    assert github_search_hit_allowed(None, "anyone")


def test_steam_near_miss_still_rejected():
    html = """
    <div class="search_row">
      <a class="searchPersonaName" href="https://steamcommunity.com/id/examplevanity">rm -rf /my/brain</a>
    </div>
    <div class="search_row">
      <a class="searchPersonaName" href="https://steamcommunity.com/id/otherperson">sudo rm -rf /</a>
    </div>
    """
    hits = match_steam_personas(html, "rm -rf /my/brain")
    assert hits == [("rm -rf /my/brain", "https://steamcommunity.com/id/examplevanity")]
    assert match_steam_personas(html, "sudo rm -rf /")[0][1].endswith("/otherperson")
    assert match_steam_personas(html, "rm -rf /") == []
