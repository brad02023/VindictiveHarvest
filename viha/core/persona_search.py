from __future__ import annotations

import re
import time
from typing import Any, Awaitable, Callable

from viha.core.persona import identity_match
from viha.core.steam import search_steam_users

SearchFn = Callable[[Any, str], Awaitable[list[tuple[str, str]]]]

_YT_VER = "2.20240827.00.00"
_YT_CHANNEL_FILTER = "EgIQAg=="
_TWITCH_CLIENT = "kimne78kx3ncx6brgo4mv6wki5h1ko"
_SC_ID = ""
_SC_AT = 0.0
_YT_CLIENT_VER = ""
_YT_VER_AT = 0.0


def merge_persona_targets(
    targets: list[tuple[str, str]],
    found: list[tuple[str, str]],
    handle: str,
) -> list[tuple[str, str]]:
    """Put exact display-name hits in front of vanity/slug URLs."""
    have = {u.rstrip("/") for _, u in targets}
    extras: list[tuple[str, str]] = []
    for _name, url in found:
        key = (url or "").rstrip("/")
        if not key or key in have:
            continue
        extras.append((handle, url))
        have.add(key)
    return extras + list(targets)


def parse_youtube_channels(payload: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    stack: list[Any] = [payload]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            renderer = obj.get("channelRenderer")
            if isinstance(renderer, dict):
                title = _yt_title(renderer)
                url = _yt_channel_url(renderer)
                if title and url and url not in seen:
                    seen.add(url)
                    out.append((title, url))
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)
    return out


def parse_roblox_users(payload: Any) -> list[tuple[str, str, str]]:
    """(displayName, username, profile_url)"""
    out: list[tuple[str, str, str]] = []
    for user in (payload or {}).get("data") or []:
        uid = user.get("id")
        if not uid:
            continue
        display = str(user.get("displayName") or "")
        login = str(user.get("name") or "")
        url = f"https://www.roblox.com/users/{uid}/profile"
        out.append((display, login, url))
    return out


def match_roblox_users(payload: Any, query: str) -> list[tuple[str, str]]:
    login_hits: list[tuple[str, str]] = []
    display_hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for display, login, url in parse_roblox_users(payload):
        if url in seen:
            continue
        if identity_match(query, login):
            seen.add(url)
            login_hits.append((display or login, url))
        elif identity_match(query, display):
            seen.add(url)
            display_hits.append((display, url))
    return login_hits or display_hits


def parse_soundcloud_users(payload: Any) -> list[tuple[str, str, str]]:
    """(username, permalink, url)"""
    out: list[tuple[str, str, str]] = []
    for user in (payload or {}).get("collection") or []:
        url = str(user.get("permalink_url") or "")
        if not url:
            permalink = str(user.get("permalink") or "")
            if permalink:
                url = f"https://soundcloud.com/{permalink}"
        if not url:
            continue
        out.append((str(user.get("username") or ""), str(user.get("permalink") or ""), url.rstrip("/")))
    return out


def match_soundcloud_users(payload: Any, query: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for username, permalink, url in parse_soundcloud_users(payload):
        if identity_match(query, username, permalink) and url not in seen:
            seen.add(url)
            hits.append((username or permalink, url))
    return hits


def parse_twitch_users(payload: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    data = (payload or {}).get("data") or payload or {}
    items = (((data.get("searchFor") or {}).get("channels") or {}).get("items")) or []
    for user in items:
        login = str(user.get("login") or "")
        if not login:
            continue
        url = f"https://www.twitch.tv/{login}"
        if url in seen:
            continue
        seen.add(url)
        out.append((str(user.get("displayName") or login), url))
    return out


def match_twitch_users(payload: Any, query: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for name, url in parse_twitch_users(payload):
        login = url.rsplit("/", 1)[-1]
        if identity_match(query, name, login):
            hits.append((name, url))
    return hits


def parse_speedrun_users(payload: Any) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for user in (payload or {}).get("data") or []:
        name = str(((user.get("names") or {}).get("international")) or "")
        url = str(user.get("weblink") or "")
        if not url and name:
            url = f"https://www.speedrun.com/users/{name}"
        if name and url:
            out.append((name, url.rstrip("/")))
    return out


def match_speedrun_users(payload: Any, query: str) -> list[tuple[str, str]]:
    return [(n, u) for n, u in parse_speedrun_users(payload) if identity_match(query, n)]


def parse_bluesky_actors(payload: Any) -> list[tuple[str, str, str]]:
    """(displayName, handle, url)"""
    out: list[tuple[str, str, str]] = []
    for actor in (payload or {}).get("actors") or []:
        handle = str(actor.get("handle") or "")
        if not handle:
            continue
        url = f"https://bsky.app/profile/{handle}"
        out.append((str(actor.get("displayName") or ""), handle, url))
    return out


def match_bluesky_actors(payload: Any, query: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for display, handle, url in parse_bluesky_actors(payload):
        local = handle.split(".", 1)[0]
        if identity_match(query, display, handle, local) and url not in seen:
            seen.add(url)
            hits.append((display or handle, url))
    return hits


def _yt_title(renderer: dict) -> str:
    title = renderer.get("title") or {}
    if isinstance(title, str):
        return title.strip()
    if isinstance(title, dict):
        if title.get("simpleText"):
            return str(title["simpleText"]).strip()
        runs = title.get("runs") or []
        return "".join(str(r.get("text") or "") for r in runs if isinstance(r, dict)).strip()
    return ""


def _yt_channel_url(renderer: dict) -> str:
    cid = str(renderer.get("channelId") or "")
    canon = ""
    browse = ((renderer.get("navigationEndpoint") or {}).get("browseEndpoint")) or {}
    canon = str(browse.get("canonicalBaseUrl") or "")
    if canon.startswith("/"):
        return "https://www.youtube.com" + canon
    if cid:
        return f"https://www.youtube.com/channel/{cid}"
    return ""


def match_youtube_channels(payload: Any, query: str) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()
    for title, url in parse_youtube_channels(payload):
        handle = ""
        if "/@" in url:
            handle = url.rsplit("/@", 1)[-1]
        if identity_match(query, title, handle) and url not in seen:
            seen.add(url)
            hits.append((title, url))
    return hits


async def _youtube_client_version(client: Any) -> str:
    global _YT_CLIENT_VER, _YT_VER_AT
    if _YT_CLIENT_VER and time.time() - _YT_VER_AT < 86400:
        return _YT_CLIENT_VER
    try:
        r = await client.get("https://www.youtube.com/", timeout=10.0)
        m = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', r.text or "")
        _YT_CLIENT_VER = (m.group(1) if m else _YT_VER) or _YT_VER
    except Exception:
        _YT_CLIENT_VER = _YT_VER
    _YT_VER_AT = time.time()
    return _YT_CLIENT_VER


async def search_youtube_channels(client: Any, query: str) -> list[tuple[str, str]]:
    try:
        version = await _youtube_client_version(client)
        r = await client.post(
            "https://www.youtube.com/youtubei/v1/search?prettyPrint=false",
            json={
                "context": {"client": {"clientName": "WEB", "clientVersion": version}},
                "query": query,
                "params": _YT_CHANNEL_FILTER,
            },
            timeout=14.0,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []
    return match_youtube_channels(payload, query)


async def search_roblox_users(client: Any, query: str) -> list[tuple[str, str]]:
    try:
        r = await client.get(
            "https://users.roblox.com/v1/users/search",
            params={"keyword": query, "limit": 25},
            timeout=12.0,
        )
        if r.status_code >= 400:
            return []
        payload = r.json()
    except Exception:
        return []
    return match_roblox_users(payload, query)


async def _soundcloud_client_id(client: Any) -> str:
    global _SC_ID, _SC_AT
    if _SC_ID and time.time() - _SC_AT < 21600:
        return _SC_ID
    try:
        home = await client.get("https://soundcloud.com/", timeout=12.0)
        scripts = re.findall(r'src="(https://[^"]+\.js)"', home.text or "")
        for src in scripts:
            if "sndcdn.com" not in src:
                continue
            js = await client.get(src, timeout=12.0)
            m = re.search(r"client_id[=:\"']{1,3}([A-Za-z0-9]{16,32})", js.text or "")
            if m:
                _SC_ID = m.group(1)
                _SC_AT = time.time()
                return _SC_ID
    except Exception:
        return ""
    return _SC_ID


async def search_soundcloud_users(client: Any, query: str) -> list[tuple[str, str]]:
    client_id = await _soundcloud_client_id(client)
    if not client_id:
        return []
    try:
        r = await client.get(
            "https://api-v2.soundcloud.com/search/users",
            params={"q": query, "client_id": client_id, "limit": 10},
            timeout=12.0,
        )
        if r.status_code in {401, 403}:
            global _SC_ID, _SC_AT
            _SC_ID, _SC_AT = "", 0.0
            return []
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []
    return match_soundcloud_users(payload, query)


async def search_twitch_users(client: Any, query: str) -> list[tuple[str, str]]:
    try:
        r = await client.post(
            "https://gql.twitch.tv/gql",
            headers={"Client-ID": _TWITCH_CLIENT},
            json={
                "query": (
                    'query($q: String!) { searchFor(userQuery: $q, platform: "web") { '
                    "channels { items { ... on User { login displayName } } } } }"
                ),
                "variables": {"q": query},
            },
            timeout=12.0,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []
    return match_twitch_users(payload, query)


async def search_speedrun_users(client: Any, query: str) -> list[tuple[str, str]]:
    try:
        r = await client.get(
            "https://www.speedrun.com/api/v1/users",
            params={"name": query, "max": 10},
            timeout=12.0,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []
    return match_speedrun_users(payload, query)


async def search_bluesky_actors(client: Any, query: str) -> list[tuple[str, str]]:
    try:
        r = await client.get(
            "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors",
            params={"q": query, "limit": 10},
            timeout=12.0,
        )
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return []
    return match_bluesky_actors(payload, query)


SEARCHERS: dict[str, SearchFn] = {
    "steam": search_steam_users,
    "youtube": search_youtube_channels,
    "soundcloud": search_soundcloud_users,
    "twitch": search_twitch_users,
    "roblox": search_roblox_users,
    "speedrun": search_speedrun_users,
    "bluesky": search_bluesky_actors,
}


def platform_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


async def search_personas(client: Any, platform: str, query: str) -> list[tuple[str, str]]:
    """Exact identity matches from a platform's public user search."""
    text = (query or "").strip()
    fn = SEARCHERS.get(platform_key(platform))
    if not fn or len(text) < 2:
        return []
    try:
        return await fn(client, text)
    except Exception:
        return []
