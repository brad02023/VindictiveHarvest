from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote, quote_plus

from viha.core.normalize import clean_supplied_handle


@dataclass(frozen=True)
class SiteStyle:
    chars: str
    min_len: int = 2
    max_len: int = 32
    seps: tuple[str, ...] = ("", "_", ".", "-")
    encode: str = "path"


STYLES: dict[str, SiteStyle] = {
    "generic": SiteStyle(r"a-z0-9._-", 2, 32, ("", "_", "-", ".")),
    "github": SiteStyle(r"a-z0-9-", 1, 39, ("-", "")),
    "gitlab": SiteStyle(r"a-z0-9._-", 1, 64, ("-", ".", "")),
    "reddit": SiteStyle(r"a-z0-9_-", 3, 20, ("_", "-")),
    "steam": SiteStyle(r"a-z0-9_-", 2, 32, ("_", "-", "")),
    "instagram": SiteStyle(r"a-z0-9._", 1, 30, (".", "_", "")),
    "facebook": SiteStyle(r"a-z0-9.", 5, 50, (".", "")),
    "tiktok": SiteStyle(r"a-z0-9._", 2, 24, (".", "_", "")),
    "x": SiteStyle(r"a-z0-9_", 1, 15, ("_", "")),
    "snapchat": SiteStyle(r"a-z0-9._-", 3, 15, ("_", ".", "-")),
    "telegram": SiteStyle(r"a-z0-9_", 5, 32, ("_", "")),
    "twitch": SiteStyle(r"a-z0-9_", 4, 25, ("_", "")),
    "youtube": SiteStyle(r"a-z0-9._-", 3, 30, ("", "_", ".", "-")),
    "pinterest": SiteStyle(r"a-z0-9_", 3, 30, ("_", "")),
    "linkedin": SiteStyle(r"a-z0-9-", 3, 100, ("-", "")),
    "threads": SiteStyle(r"a-z0-9._", 1, 30, (".", "_", "")),
    "linktree": SiteStyle(r"a-z0-9._-", 2, 30, (".", "_", "-")),
    "aboutme": SiteStyle(r"a-z0-9._-", 2, 30, (".", "-", "_")),
    "roblox": SiteStyle(r"a-z0-9_", 3, 20, ("_", "")),
    "xbox": SiteStyle(r"a-z0-9 ", 1, 15, (" ", "", "-")),
    "keybase": SiteStyle(r"a-z0-9_", 2, 16, ("_", "")),
    "discord": SiteStyle(r"0-9", 17, 20, ("",)),
    "medium": SiteStyle(r"a-z0-9_", 2, 30, ("_", "")),
    "tumblr": SiteStyle(r"a-z0-9-", 1, 32, ("-", "")),
    "cashapp": SiteStyle(r"a-z0-9_", 1, 20, ("_", "")),
    "venmo": SiteStyle(r"a-z0-9_-", 1, 30, ("_", "-", "")),
}

SITE_STYLE_ALIASES = {
    "github": "github",
    "gitlab": "gitlab",
    "reddit": "reddit",
    "steam": "steam",
    "instagram": "instagram",
    "facebook": "facebook",
    "tiktok": "tiktok",
    "x": "x",
    "twitter": "x",
    "snapchat": "snapchat",
    "telegram": "telegram",
    "twitch": "twitch",
    "youtube": "youtube",
    "pinterest": "pinterest",
    "linkedin": "linkedin",
    "threads": "threads",
    "linktree": "linktree",
    "aboutme": "aboutme",
    "about.me": "aboutme",
    "roblox": "roblox",
    "xbox": "xbox",
    "keybase": "keybase",
    "discord": "discord",
    "medium": "medium",
    "tumblr": "tumblr",
    "cashapp": "cashapp",
    "cash.app": "cashapp",
    "venmo": "venmo",
}


def style_name_for(site_name: str) -> str:
    key = re.sub(r"[^a-z0-9.]", "", (site_name or "").lower())
    return SITE_STYLE_ALIASES.get(key, "generic")


def _valid(value: str, style: SiteStyle) -> bool:
    if not (style.min_len <= len(value) <= style.max_len):
        return False
    return bool(re.fullmatch(rf"[{style.chars}]+", value))


def shape_handle(handle: str, style_key: str) -> list[str]:
    """Site-legal forms of a typed handle. Empty if this site cannot take it."""
    raw = clean_supplied_handle(handle)
    if not raw:
        return []
    style = STYLES.get(style_key) or STYLES["generic"]
    if style_key == "discord":
        digits = re.sub(r"\D", "", raw)
        return [digits] if _valid(digits, style) else []
    if _valid(raw, style):
        return [raw]
    out: list[str] = []
    seen: set[str] = set()
    for sep in style.seps:
        carved = re.sub(rf"[^{style.chars}]+", sep, raw)
        if sep:
            carved = re.sub(rf"{re.escape(sep)}+", sep, carved).strip(sep + "._-")
        else:
            carved = re.sub(r"[^a-z0-9]+", "", carved)
        if style_key == "github":
            carved = carved.strip("-")
            carved = re.sub(r"-{2,}", "-", carved)
        if style_key == "instagram" or style_key == "threads":
            carved = carved.strip(".")
            carved = re.sub(r"\.{2,}", ".", carved)
        if not _valid(carved, style) or carved in seen:
            continue
        seen.add(carved)
        out.append(carved)
        if len(out) >= 3:
            break
    return out


def path_seg(handle: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9._~-]+", handle or ""):
        return handle
    return quote(handle, safe="._-")


def fill_url(template: str, shaped: str, original: str = "") -> str:
    query = quote_plus(original or shaped)
    hyphen = re.sub(r"[^a-z0-9]+", "-", (original or shaped).lower()).strip("-")
    return (
        template.replace("{u}", path_seg(shaped))
        .replace("{q}", query)
        .replace("{h}", hyphen)
    )


def probe_urls(site: dict, handle: str) -> list[tuple[str, str]]:
    """(shaped_handle, url) pairs this site will actually accept."""
    style = site.get("style") or style_name_for(site.get("name") or "")
    shaped = shape_handle(handle, style)
    templates = [t for t in (site.get("urls") or []) if t]
    primary = site.get("url") or ""
    if primary and primary not in templates:
        templates.insert(0, primary)
    if style == "steam" and re.fullmatch(r"\d{16,18}", clean_supplied_handle(handle)):
        templates.append("https://steamcommunity.com/profiles/{u}")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for form in shaped:
        for tmpl in templates:
            if "{q}" in tmpl:
                url = fill_url(tmpl, form, handle)
            else:
                url = fill_url(tmpl, form, form)
            if not url or url in seen:
                continue
            seen.add(url)
            out.append((form, url))
    return out[:6]


def recipe_profile_urls(handle: str) -> list[tuple[str, str]]:
    """Browser lookup URLs using each platform's preferred handle shape."""
    pairs = [
        ("Steam", "steam", "https://steamcommunity.com/id/{u}"),
        ("Steam search", "steam", "https://steamcommunity.com/search/users/#text={q}"),
        ("GitHub", "github", "https://github.com/{u}"),
        ("Instagram", "instagram", "https://www.instagram.com/{u}/"),
        ("TikTok", "tiktok", "https://www.tiktok.com/@{u}"),
        ("X", "x", "https://x.com/{u}"),
        ("YouTube", "youtube", "https://www.youtube.com/@{u}"),
        ("YouTube search", "youtube", "https://www.youtube.com/results?search_query={q}&sp=EgIQAg%253D%253D"),
        ("Reddit", "reddit", "https://www.reddit.com/user/{u}"),
        ("LinkedIn", "linkedin", "https://www.linkedin.com/in/{u}"),
        ("Twitch", "twitch", "https://www.twitch.tv/{u}"),
        ("Twitch search", "twitch", "https://www.twitch.tv/search?term={q}"),
        ("Roblox search", "roblox", "https://www.roblox.com/search/users?keyword={q}"),
        ("SoundCloud search", "generic", "https://soundcloud.com/search/people?q={q}"),
        ("Spotify user", "generic", "https://open.spotify.com/user/{u}"),
        ("Speedrun search", "generic", "https://www.speedrun.com/search?q={q}"),
        ("Telegram", "telegram", "https://t.me/{u}"),
    ]
    out: list[tuple[str, str]] = []
    for label, style, tmpl in pairs:
        forms = shape_handle(handle, style)
        if not forms:
            continue
        url = fill_url(tmpl, forms[0], handle)
        out.append((f"{label} {forms[0]}", url))
    return out
