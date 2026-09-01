from __future__ import annotations

import re
from typing import Any

from viha.core.persona import identity_match, persona_key

_ROW_SPLIT = re.compile(r'class="search_row"')
_NAME = re.compile(r"searchPersonaName[^>]*>([^<]+)")
_HREF = re.compile(r'href="(https://steamcommunity.com/(?:id|profiles)/[^"?#]+)', re.I)

__all__ = ["identity_match", "match_steam_personas", "parse_steam_user_search", "persona_key", "search_steam_users"]


def parse_steam_user_search(html: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in _ROW_SPLIT.split(html or "")[1:]:
        name_m = _NAME.search(row)
        href_m = _HREF.search(row)
        if not name_m or not href_m:
            continue
        name = re.sub(r"\s+", " ", name_m.group(1)).strip()
        url = href_m.group(1).rstrip("/")
        if not name or url in seen:
            continue
        seen.add(url)
        out.append((name, url))
    return out


def match_steam_personas(html: str, query: str) -> list[tuple[str, str]]:
    if not persona_key(query):
        return []
    return [(name, url) for name, url in parse_steam_user_search(html) if identity_match(query, name)]


async def search_steam_users(client: Any, query: str) -> list[tuple[str, str]]:
    """Public Steam community user search. Returns exact persona-name matches."""
    text = (query or "").strip()
    if len(text) < 2:
        return []
    try:
        await client.get("https://steamcommunity.com/", timeout=10.0)
        session = ""
        cookies = getattr(client, "cookies", None)
        if cookies is not None:
            session = cookies.get("sessionid") or ""
        r = await client.get(
            "https://steamcommunity.com/search/SearchCommunityAjax",
            params={"text": text, "filter": "users", "sessionid": session, "steamid_user": "false"},
            timeout=12.0,
        )
        r.raise_for_status()
        html = (r.json() or {}).get("html") or ""
    except Exception:
        return []
    return match_steam_personas(html, text)
