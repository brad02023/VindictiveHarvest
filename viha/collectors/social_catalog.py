from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from urllib.parse import unquote, urlparse

from viha.core.normalize import handle_needles
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
    "speedrun.com": "speedrun",
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
    "SoundCloud",
    "Spotify",
    "Venmo",
    "LinkedIn",
    "Linktree",
    "About.me",
    "Roblox",
    "Xbox",
    "Discord",
    "Speedrun",
    "Bluesky",
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


def _fill_all(template: str, handle: str) -> list[str]:
    seen: list[str] = []
    for needle in handle_needles(handle):
        filled = template.replace("{u}", needle)
        if filled not in seen:
            seen.append(filled)
    return seen


_LOGIN_MARKERS = (
    "/login",
    "/signin",
    "/sign-in",
    "accounts.",
    "login?",
    "signup",
    "authwall",
    "accounts/login",
)
_LOGIN_BODY = (
    "authwall",
    "join linkedin",
    "sign in to linkedin",
    "log in to facebook",
    "log into facebook",
    "log in • instagram",
    "sign in to continue to youtube",
    "sign in to spotify",
    "discord login",
)
_ERROR_DEST = ("request-error", "error?code=404", "/404", "notfound")
_PROFILE_ID_PATH = re.compile(r"/(?:profiles|users|user|id)/(\d{5,})(?:/|$)", re.I)
_NOT_FOUND = (
    "user not found",
    "users not found",
    "profile not found",
    "page not found",
    "page isn't available",
    "page is not available",
    "this page isn't available",
    "this page is not available",
    "could not be found",
    "couldn't be found",
    "couldn't find that",
    "couldn't find this",
    "couldn't find the",
    "couldnt find",
    "cannot be found",
    "can't find that user",
    "can't find this user",
    "we can't find that user",
    "we couldn't find",
    "does not exist",
    "doesn't exist",
    "doesnt exist",
    "account not found",
    "account doesn’t exist",
    "account doesn't exist",
    "this account doesn’t exist",
    "this account doesn't exist",
    "nobody by that name",
    "no user found",
    "profile could not",
    "specified profile could not",
    "this content isn't available",
    "that page doesn't exist",
    "the page you’re looking for doesn’t exist",
    "the page you're looking for doesn't exist",
    "channel does not exist",
    "this channel doesn't exist",
    "this channel isn't available",
    "isn't a valid user",
    "is not a valid user",
    "there is no user",
    "no profile exists",
    "missing page",
    "user profile not found",
    "sorry, not found",
    "404 - sorry",
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_OG_RE = re.compile(r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)', re.I)
_OG_RE_REV = re.compile(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']', re.I)
_GENERIC_TITLES = {
    "twitch",
    "tiktok - make your day",
    "instagram",
    "x",
    "twitter",
    "facebook",
    "linkedin",
    "linkedin: log in or sign up",
    "youtube",
    "reddit",
    "steam community :: error",
    "steam community",
    "not found",
    "page not found",
    "just a moment...",
    "dailymotion",
    "discord",
    "bluesky",
    "spotify",
    "spotify – web player",
    "spotify - web player",
    "codeforces",
    "pinterest",
    "venmo",
    "about.me",
    "roblox",
    "welcome to reddit",
}
_WEAK_TITLE_PREFIXES = (
    "telegram: contact",
    "log in",
    "login",
    "sign in",
    "missing page",
)
_PROFILE_OG = {"profile", "music.musician", "video.other", "music.profile"}
# Markers that appear on a real profile and not on the site chrome / 404 shell.
_EXCLUSIVE_HIT = (
    "g_rgprofiledata =",
    '"kind": "t2"',
    '"kind":"t2"',
    "p-nickname",
    'itemprop="name"',
    "__isprofile",
    "soundcloud:user",
    "data-profileuserid",
    "viewing profile",
    '"player_id":',
    "gamerscore",
)


def _page_titles(html: str) -> list[str]:
    out: list[str] = []
    for match in _TITLE_RE.finditer(html or ""):
        out.append(re.sub(r"\s+", " ", match.group(1)).strip())
    for rx in (_OG_RE, _OG_RE_REV):
        for match in rx.finditer(html or ""):
            out.append(match.group(1).strip())
    return [t for t in out if t]


def _handle_as_token(text: str, handle: str) -> bool:
    blob = (text or "").lower()
    for needle in handle_needles(handle):
        token = needle.lower()
        if len(token) < 3:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob):
            return True
    return False


def _title_is_profile(title: str, handle: str) -> bool:
    low = (title or "").lower().strip()
    if not low or low.strip(" |/-") in _GENERIC_TITLES:
        return False
    if any(low.startswith(prefix) for prefix in _WEAK_TITLE_PREFIXES):
        return False
    if page_says_missing(low):
        return False
    if any(n in low for n in ("missing page", " 404", "error", "just a moment")):
        return False
    return _handle_as_token(title, handle)


def _title_names_handle(titles: list[str], handle: str) -> bool:
    return any(_title_is_profile(title, handle) for title in titles)


def _og_types(html: str) -> list[str]:
    out: list[str] = []
    for rx in (
        re.compile(r'property=["\']og:type["\'][^>]*content=["\']([^"\']+)', re.I),
        re.compile(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:type["\']', re.I),
    ):
        out.extend(m.group(1).strip().lower() for m in rx.finditer(html or ""))
    return out


def _looks_like_json(text: str) -> bool:
    s = (text or "").lstrip()
    return s.startswith("{") or s.startswith("[")


def _unbound_hit_is_exclusive(needle: str) -> bool:
    low = (needle or "").lower()
    return any(m in low for m in _EXCLUSIVE_HIT)


def page_says_missing(text: str) -> bool:
    """True when the fetched page is a 200 'user not found' shell."""
    blob = (text or "").lower()
    if not blob:
        return False
    titles = " ".join(_page_titles(text)).lower() if "<" in blob else ""
    hay = f"{blob[:12000]} {titles}"
    return any(needle in hay for needle in _NOT_FOUND)


def handle_in_url(url: str, handle: str) -> bool:
    dest = unquote((url or "").lower())
    if not dest or not handle:
        return False
    for needle in handle_needles(handle):
        if len(needle) >= 2 and needle.lower() in dest:
            return True
    return False


def dest_is_generic(url: str) -> bool:
    """Homepage / explore dumps, not vanity paths like xboxgamertag.com/search/{u}."""
    if not url:
        return False
    path = (urlparse(url).path or "/").rstrip("/") or "/"
    if path == "/":
        return True
    parts = [p for p in path.split("/") if p]
    if not parts:
        return True
    if parts[0] in {"explore", "discover", "feed", "home", "results"}:
        return True
    if parts[0] == "search" and len(parts) < 2:
        return True
    return False


def dest_is_search_dump(url: str, handle: str) -> bool:
    """Search-result pages that echo the query, not a vanity profile URL."""
    parsed = urlparse(url or "")
    query = (parsed.query or "").lower()
    path = (parsed.path or "").lower()
    if "keywords=" in query or "type=user" in query or "search=members" in query:
        return True
    if "/search/" in path or path.endswith("/search"):
        return not handle_in_url(path, handle)
    return False


def url_still_names_user(requested: str, final: str, handle: str) -> bool:
    """Vanity URLs that 200 after redirect must still be that user's profile."""
    dest = final or requested or ""
    if dest_is_generic(dest):
        return False
    if dest_is_search_dump(dest, handle):
        return False
    path = urlparse(dest).path or ""
    if _PROFILE_ID_PATH.search(path):
        return True
    if handle_in_url(dest, handle):
        return True
    req = requested or ""
    if handle_in_url(req, handle) and not handle_in_url(dest, handle):
        return False
    return True


def wmn_account_exists(site: dict[str, Any], status: int, body: str) -> bool:
    """WhatsMyName: e_* means exists, m_* means missing. Do not invert them."""
    text = body or ""
    low = text.lower()
    e_string = (site.get("e_string") or "").lower()
    m_string = (site.get("m_string") or "").lower()
    e_code = site.get("e_code")
    m_code = site.get("m_code")
    has_e = bool(e_string) and e_string in low
    has_m = bool(m_string) and m_string in low
    if has_m and not has_e:
        return False
    if has_e:
        if e_code is not None and status != e_code:
            return False
        if m_code is not None and e_code is not None and m_code != e_code and status == m_code:
            return False
        return True
    if e_string:
        return False
    if e_code is not None and status == e_code:
        if m_code is not None and m_code != e_code and status == m_code:
            return False
        return True
    return False


def page_is_hit(
    site: dict[str, Any],
    status: int,
    body: str,
    handle: str,
    final_url: str = "",
    requested_url: str = "",
) -> bool:
    text = body or ""
    dest = (final_url or "").lower()
    miss_status = site.get("miss_status") or []
    if status in miss_status:
        return False
    if status >= 400:
        return False
    if not text.strip():
        return False
    if any(m in dest for m in _LOGIN_MARKERS):
        return False
    if any(m in dest for m in _ERROR_DEST):
        return False
    titles = _page_titles(text)
    title_blob = " ".join(titles).lower()
    if "just a moment" in title_blob or "just a moment" in text[:2500].lower():
        return False
    if page_says_missing(text):
        return False
    if final_url and dest_is_generic(final_url) and not site.get("handle_optional"):
        return False
    if final_url and dest_is_search_dump(final_url, handle):
        return False
    req = requested_url or final_url
    if final_url and not site.get("handle_optional") and not url_still_names_user(req, final_url, handle):
        return False
    blob = text.lower()
    if any(m in blob for m in _LOGIN_BODY):
        return False
    for needle in site.get("miss_any") or []:
        if any(v.lower() in blob for v in _fill_all(needle, handle)):
            return False
    titled = _title_names_handle(titles, handle)
    if titled:
        return True
    hits = site.get("hit_any") or []
    bound = [n for n in hits if "{u}" in n]
    unbound = [n for n in hits if "{u}" not in n]
    if bound and any(v.lower() in blob for n in bound for v in _fill_all(n, handle)):
        return True
    if _looks_like_json(text) and unbound and any(n.lower() in blob for n in unbound):
        return True
    if unbound:
        matched = [n for n in unbound if n.lower() in blob]
        if matched and (titled or any(_unbound_hit_is_exclusive(n) for n in matched)):
            return True
    if site.get("handle_optional") and "/users/" in dest and "/profile" in dest:
        return titled or any(t in _PROFILE_OG for t in _og_types(text))
    return False


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
