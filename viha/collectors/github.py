from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.collectors.social import hunt_handles
from viha.core.models import Fact, Seed
from viha.core.normalize import email_local_part, name_tokens
from viha.core.settings import load_settings


def _gh_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = (load_settings().get("github_token") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class GitHubCollector(Collector):
    id = "viha.db.github"
    label = "GitHub"
    blurb = "Public users matching name, handle, or email local-part"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        handles = hunt_handles(seed)
        local = email_local_part(seed.email)
        facts: list[Fact] = []
        seen_logins: set[str] = set()

        for handle in handles:
            log(f"GitHub user: {handle}")
            try:
                user = await fetch_json(
                    client,
                    f"https://api.github.com/users/{handle}",
                    headers=_gh_headers(),
                )
            except Exception:
                continue
            login = (user.get("login") or "").lower()
            if not login or login in seen_logins:
                continue
            seen_logins.add(login)
            exact = login == handle.lower() or (local and login == local)
            facts.append(
                self.fact(
                    predicate="username",
                    value=f"github:{user.get('login')}",
                    section="social",
                    confidence=0.86 if exact else 0.5,
                    url=user.get("html_url") or f"https://github.com/{user.get('login')}",
                    publisher="GitHub",
                    raw=user,
                    extra={"platform": "github", "handle": user.get("login")},
                    candidate=not exact,
                )
            )

        queries: list[str] = []
        tokens = name_tokens(seed.full_name)
        if len(tokens) >= 2:
            queries.append(f'fullname:"{seed.full_name.strip()}"')
            queries.append(f"{tokens[0]} {tokens[-1]} in:name")
        if local:
            queries.append(local)
        if seed.username.strip():
            queries.append(seed.username.strip())

        for q in queries:
            log(f"GitHub search: {q}")
            try:
                data = await fetch_json(
                    client,
                    "https://api.github.com/search/users",
                    params={"q": q, "per_page": 8},
                    headers=_gh_headers(),
                )
            except Exception as exc:
                log(f"GitHub: {exc}")
                continue
            for user in data.get("items") or []:
                login = user.get("login") or ""
                if not login or login.lower() in seen_logins:
                    continue
                seen_logins.add(login.lower())
                exact = login.lower() in {h.lower() for h in handles}
                facts.append(
                    self.fact(
                        predicate="username",
                        value=f"github:{login}",
                        section="social",
                        confidence=0.78 if exact else 0.42,
                        url=user.get("html_url") or f"https://github.com/{login}",
                        publisher="GitHub",
                        raw=user,
                        extra={"platform": "github", "handle": login},
                        candidate=not exact,
                    )
                )
        if not facts:
            log("GitHub: no public users")
        return facts
