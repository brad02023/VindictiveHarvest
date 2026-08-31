from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from viha.data import DATA_DIR

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SOCIAL_HOSTS = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "reddit.com": "reddit",
    "steamcommunity.com": "steam",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "tiktok.com": "tiktok",
    "x.com": "x",
    "twitter.com": "x",
    "snapchat.com": "snapchat",
    "t.me": "telegram",
    "telegram.me": "telegram",
    "twitch.tv": "twitch",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "pinterest.com": "pinterest",
    "linkedin.com": "linkedin",
    "threads.net": "threads",
    "bsky.app": "bluesky",
    "roblox.com": "roblox",
    "xbox.com": "xbox",
    "xboxgamertag.com": "xbox",
    "spotify.com": "spotify",
    "soundcloud.com": "soundcloud",
    "bandcamp.com": "bandcamp",
    "last.fm": "lastfm",
    "linktr.ee": "linktree",
    "about.me": "aboutme",
    "carrd.co": "carrd",
    "bio.link": "biolink",
    "venmo.com": "venmo",
    "cash.app": "cashapp",
    "paypal.me": "paypal",
    "paypal.com": "paypal",
    "patreon.com": "patreon",
    "ko-fi.com": "kofi",
    "medium.com": "medium",
    "substack.com": "substack",
    "tumblr.com": "tumblr",
    "flickr.com": "flickr",
    "deviantart.com": "deviantart",
    "behance.net": "behance",
    "dribbble.com": "dribbble",
    "vimeo.com": "vimeo",
    "kick.com": "kick",
    "rumble.com": "rumble",
    "keybase.io": "keybase",
    "replit.com": "replit",
    "kaggle.com": "kaggle",
    "leetcode.com": "leetcode",
    "tryhackme.com": "tryhackme",
    "chess.com": "chess",
    "lichess.org": "lichess",
    "strava.com": "strava",
    "duolingo.com": "duolingo",
    "letterboxd.com": "letterboxd",
    "anilist.co": "anilist",
    "myanimelist.net": "myanimelist",
    "itch.io": "itchio",
    "quora.com": "quora",
    "imgur.com": "imgur",
    "vsco.co": "vsco",
    "discord.com": "discord",
    "discord.gg": "discord",
    "discord.gift": "discord",
    "discordapp.com": "discord",
}

HIGH_SIGNAL = {
    "Steam",
    "Instagram",
    "Facebook",
    "GitHub",
    "Reddit",
    "TikTok",
    "Snapchat",
    "X",
    "Telegram",
    "Twitch",
    "YouTube",
    "LinkedIn",
    "Linktree",
    "About.me",
    "Roblox",
    "Xbox",
    "Discord",
}


@lru_cache(maxsize=1)
def load_sites() -> list[dict[str, Any]]:
    path = DATA_DIR / "social_sites.json"
    return json.loads(path.read_text(encoding="utf-8"))


def platform_of(url: str) -> str:
    host = (url or "").lower()
    for needle, name in SOCIAL_HOSTS.items():
        if needle in host:
            return name
    return ""


def _fill(template: str, handle: str) -> str:
    return template.replace("{u}", handle)


_LOGIN_MARKERS = ("/login", "/signin", "/sign-in", "accounts.", "login?", "signup")


def page_is_hit(
    site: dict[str, Any],
    status: int,
    body: str,
    handle: str,
    final_url: str = "",
) -> bool:
    text = body or ""
    dest = (final_url or "").lower()
    miss_status = site.get("miss_status") or []
    if status in miss_status:
        return False
    if status >= 400:
        return False
    if any(m in dest for m in _LOGIN_MARKERS):
        return False
    for needle in site.get("miss_any") or []:
        if _fill(needle, handle).lower() in text.lower():
            return False
    hits = site.get("hit_any") or []
    if hits and not any(_fill(n, handle).lower() in text.lower() for n in hits):
        return False
    if not site.get("handle_optional"):
        needle = handle.lower()
        if needle not in text.lower() and needle not in dest:
            return False
    return True


_HREF_RE = re.compile(r"""href=["'](https?://[^"'#]+)""", re.I)


def extract_social_links(html: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href in _HREF_RE.findall(html or ""):
        plat = platform_of(href)
        if not plat or href in seen:
            continue
        seen.add(href)
        found.append((plat, href.split("?")[0]))
    return found
