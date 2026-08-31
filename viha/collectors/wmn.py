from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from viha.collectors.base import Collector, LogFn
from viha.collectors.social import handle_is_strong, hunt_handles, mark_social_confidence
from viha.collectors.social_catalog import BROWSER_UA, page_is_hit
from viha.core.casefile import ensure_cases_dir
from viha.core.models import Fact, Seed

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
            url = (site.get("uri_check") or "").replace("{account}", handle)
            if not url:
                return None
            async with sem:
                try:
                    r = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
                except Exception:
                    return None
            pretty = (site.get("uri_pretty") or url).replace("{account}", handle)
            fake = {
                "hit_any": [site["m_string"]] if site.get("m_string") else [],
                "miss_any": [site["e_string"]] if site.get("e_string") else [],
                "miss_status": [site["e_code"]] if site.get("e_code") and site.get("e_code") != site.get("m_code") else [],
            }
            # Prefer WMN semantics: exist if m_code matches and m_string (if any) is present.
            body = r.text or ""
            m_code = site.get("m_code")
            m_string = site.get("m_string") or ""
            e_string = site.get("e_string") or ""
            if m_code is not None and r.status_code != m_code:
                if not page_is_hit(fake, r.status_code, body, handle, str(r.url)):
                    return None
            if e_string and e_string.lower() in body.lower() and not (m_string and m_string.lower() in body.lower()):
                return None
            if m_string and m_string.lower() not in body.lower() and not fake["hit_any"]:
                if handle.lower() not in body.lower() and handle.lower() not in str(r.url).lower():
                    return None
            if handle.lower() not in body.lower() and handle.lower() not in str(r.url).lower():
                return None
            name = site.get("name") or "site"
            return self.fact(
                predicate="username",
                value=f"{name.lower()}:{handle}",
                section="social",
                confidence=0.62,
                url=pretty or str(r.url),
                publisher=name,
                extra={"platform": name.lower(), "handle": handle, "via": "wmn"},
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
