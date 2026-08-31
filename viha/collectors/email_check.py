from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_email
from viha.core.settings import load_settings


class EmailCheckCollector(Collector):
    id = "viha.db.emailcheck"
    label = "Email checks"
    blurb = "Public GET checks: Gravatar, Keybase, GitHub commits"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        email = normalize_email(seed.email)
        if not email:
            log("Email checks skipped — need an email")
            return []
        facts: list[Fact] = []
        log(f"Email checks: {email}")

        try:
            kb = await fetch_json(
                client,
                "https://keybase.io/_/api/1.0/user/lookup.json",
                params={"email": email},
            )
            if kb.get("status", {}).get("code") == 0 and kb.get("them"):
                them = kb["them"]
                if isinstance(them, dict):
                    them = [them]
                user = (them[0] or {}).get("basics", {})
                uname = user.get("username") or "keybase"
                facts.append(
                    self.fact(
                        predicate="username",
                        value=f"keybase:{uname}",
                        section="social",
                        confidence=0.88,
                        url=f"https://keybase.io/{uname}",
                        publisher="Keybase",
                        raw=kb,
                        extra={"platform": "keybase", "handle": uname, "via": "email"},
                    )
                )
        except Exception as exc:
            log(f"Keybase email: {exc}")

        headers = {"Accept": "application/vnd.github+json"}
        token = (load_settings().get("github_token") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            data = await fetch_json(
                client,
                "https://api.github.com/search/commits",
                params={"q": f"author-email:{email}", "per_page": 5},
                headers=headers,
            )
            items = data.get("items") or []
            if items:
                author = ((items[0].get("author") or {}) or {})
                login = author.get("login") or ""
                facts.append(
                    self.fact(
                        predicate="email_registered",
                        value=f"GitHub commits as {login or email}",
                        section="social",
                        confidence=0.8,
                        url=author.get("html_url") or "https://github.com/",
                        publisher="GitHub",
                        raw={"count": data.get("total_count"), "login": login},
                        extra={"platform": "github", "handle": login, "via": "email"},
                        candidate=True,
                    )
                )
        except Exception as exc:
            log(f"GitHub commit-email: {exc}")

        try:
            users = await fetch_json(
                client,
                "https://api.github.com/search/users",
                params={"q": f"{email} in:email", "per_page": 5},
                headers=headers,
            )
            for user in users.get("items") or []:
                login = user.get("login") or ""
                facts.append(
                    self.fact(
                        predicate="username",
                        value=f"github:{login}",
                        section="social",
                        confidence=0.7,
                        url=user.get("html_url") or f"https://github.com/{login}",
                        publisher="GitHub",
                        extra={"platform": "github", "handle": login, "via": "email"},
                        candidate=True,
                    )
                )
        except Exception as exc:
            log(f"GitHub email search: {exc}")

        if not facts:
            log("Email checks: no public registrations")
        return facts
