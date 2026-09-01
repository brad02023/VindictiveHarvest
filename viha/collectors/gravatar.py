from __future__ import annotations

import hashlib

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_email


class GravatarCollector(Collector):
    id = "viha.db.gravatar"
    label = "Gravatar"
    blurb = "Public avatar and profile for an opted-in email"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        email = normalize_email(seed.email)
        if not email:
            log("Gravatar skipped — need an email")
            return []
        digest = hashlib.md5(email.encode("utf-8"), usedforsecurity=False).hexdigest()
        avatar = f"https://www.gravatar.com/avatar/{digest}?d=404"
        log("Gravatar avatar check")
        facts: list[Fact] = []
        r = await client.get(avatar, timeout=12.0, follow_redirects=True)
        if r.status_code == 200:
            facts.append(
                self.fact(
                    predicate="photo",
                    value=avatar,
                    section="identity",
                    confidence=0.8,
                    url=avatar,
                    publisher="Gravatar",
                    extra={"md5": digest},
                )
            )
        try:
            profile = await fetch_json(client, f"https://www.gravatar.com/{digest}.json")
            entry = (profile.get("entry") or [None])[0] or {}
            display = entry.get("displayName") or entry.get("preferredUsername") or ""
            if display:
                facts.append(
                    self.fact(
                        predicate="aka",
                        value=display,
                        section="identity",
                        confidence=0.7,
                        url=entry.get("profileUrl") or f"https://gravatar.com/{digest}",
                        publisher="Gravatar",
                        raw=entry,
                    )
                )
            loc = ""
            current = entry.get("currentLocation")
            if isinstance(current, dict):
                loc = (current.get("name") or current.get("title") or "").strip()
            elif current:
                loc = str(current).strip()
            if loc:
                facts.append(
                    self.fact(
                        predicate="location",
                        value=loc,
                        section="identity",
                        confidence=0.68,
                        url=entry.get("profileUrl") or f"https://gravatar.com/{digest}",
                        publisher="Gravatar",
                        extra={"via": "gravatar-profile"},
                    )
                )
            for account in entry.get("accounts") or []:
                uname = account.get("username") or account.get("shortname") or ""
                domain = account.get("domain") or account.get("name") or "account"
                url = account.get("url") or ""
                if not uname:
                    continue
                facts.append(
                    self.fact(
                        predicate="username",
                        value=f"{domain}:{uname}",
                        section="social",
                        confidence=0.72,
                        url=url or f"https://gravatar.com/{digest}",
                        publisher="Gravatar",
                        raw=account,
                        extra={"platform": domain, "handle": uname},
                    )
                )
        except Exception as exc:
            if r.status_code != 200:
                log(f"Gravatar: no public profile ({exc})")
        return facts
