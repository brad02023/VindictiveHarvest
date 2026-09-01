from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from viha.collectors.base import Collector, LogFn
from viha.collectors.social import handle_is_strong, hunt_handles, mark_social_confidence
from viha.collectors.social_catalog import (
    BROWSER_UA,
    dest_is_generic,
    dest_is_search_dump,
    page_is_hit,
    page_says_missing,
    url_still_names_user,
    wmn_account_exists,
)
from viha.core.casefile import ensure_cases_dir
from viha.core.models import Fact, Seed
from viha.core.handles import path_seg, shape_handle, style_name_for
from viha.core.normalize import handle_needles

WMN_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
KEEP_CATS = {"social", "gaming", "coding", "images", "video", "music", "blog", "hobby", "tech"}
MAX_SITES = 100


def _cache_path():
    return ensure_cases_dir() / "wmn-data.json"


def _usable(site: dict[str, Any]) -> bool:
    if site.get("post_body"):
        return False
    if "{account}" not in (site.get("uri_check") or ""):
        return False
    if (site.get("cat") or "") not in KEEP_CATS:
        return False
    prot = " ".join(site.get("protection") or []).lower()
    if "captcha" in prot:
        return False
    return True


class WhatsMyNameCollector(Collector):
    id = "viha.db.wmn"
    label = "WhatsMyName"
    blurb = "Cached public username catalog (GET sites only, strong handles)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        handles = [h for h in hunt_handles(seed) if handle_is_strong(h, seed)]
        if not handles:
            log("WhatsMyName skipped — need a unique email local-part or typed username")
            return []
        sites = await self._sites(client, log)
        if not sites:
            return []
        log(f"WhatsMyName: {len(handles)} strong handle(s) × {len(sites)} sites")
        sem = asyncio.Semaphore(12)
        headers = {"User-Agent": BROWSER_UA}

        async def probe(handle: str, site: dict[str, Any]) -> Fact | None:
            forms = shape_handle(handle, style_name_for(site.get("name") or ""))
            account = forms[0] if forms else ""
            if not account:
                return None
            url = (site.get("uri_check") or "").replace("{account}", path_seg(account))
            if not url:
                return None
            async with sem:
                try:
                    r = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
                except Exception:
                    return None
            pretty = (site.get("uri_pretty") or url).replace("{account}", path_seg(account))
            body = r.text or ""
            dest = str(r.url)
            if not wmn_account_exists(site, r.status_code, body):
                return None
            if page_says_missing(body):
                return None
            if dest_is_generic(dest) or dest_is_search_dump(dest, account):
                return None
            if not url_still_names_user(url, dest, account):
                return None
            catalog = {
                "hit_any": [site["e_string"]] if site.get("e_string") else [],
                "miss_any": [site["m_string"]] if site.get("m_string") else [],
                "miss_status": (
                    [site["m_code"]]
                    if site.get("m_code") is not None and site.get("m_code") != site.get("e_code")
                    else []
                ),
            }
            jsonish = (body or "").lstrip().startswith(("{", "["))
            if not jsonish and not page_is_hit(
                catalog, r.status_code, body, account, dest, requested_url=url
            ):
                return None
            needles = [n.lower() for n in handle_needles(account)]
            blob = body.lower()
            if (
                not any(n in blob for n in needles)
                and account.lower() not in url.lower()
                and account.lower() not in dest.lower()
            ):
                return None
            name = site.get("name") or "site"
            return self.fact(
                predicate="username",
                value=f"{name.lower()}:{handle}",
                section="social",
                confidence=0.62,
                url=pretty or str(r.url),
                publisher=name,
                extra={"platform": name.lower(), "handle": account, "supplied": handle, "via": "wmn"},
                candidate=not handle_is_strong(handle, seed),
            )

        tasks = [probe(h, s) for h in handles for s in sites]
        results = await asyncio.gather(*tasks)
        facts = [f for f in results if f is not None]
        facts = mark_social_confidence(facts, seed)
        log(f"WhatsMyName: {len(facts)} hits")
        return facts

    async def _sites(self, client, log: LogFn) -> list[dict[str, Any]]:
        path = _cache_path()
        if path.exists() and time.time() - path.stat().st_mtime < 7 * 86400:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sites = [s for s in data.get("sites", []) if _usable(s)][:MAX_SITES]
                log(f"WhatsMyName cache: {len(sites)} sites")
                return sites
            except json.JSONDecodeError:
                pass
        log("WhatsMyName: downloading catalog")
        try:
            r = await client.get(WMN_URL, timeout=40.0)
            r.raise_for_status()
            data = r.json()
            path.write_text(json.dumps(data), encoding="utf-8")
        except Exception as exc:
            log(f"WhatsMyName download failed: {exc}")
            return []
        return [s for s in data.get("sites", []) if _usable(s)][:MAX_SITES]
