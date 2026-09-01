from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.collectors.social import hunt_handles, mark_social_confidence
from viha.core.models import Fact, Seed
from viha.core.handles import path_seg, shape_handle
from viha.core.identity import fields_from_github_user
from viha.core.normalize import email_local_part, name_tokens, split_usernames
from viha.core.persona import identity_match
from viha.core.settings import load_settings


def github_search_hit_allowed(must_handle: str | None, login: str, name: str = "") -> bool:
    if not must_handle:
        return True
    return identity_match(must_handle, login, name)


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
            forms = shape_handle(handle, "github")
            if not forms:
                log(f"GitHub user skipped (not a GitHub-style handle): {handle}")
                continue
            lookup = forms[0]
            log(f"GitHub user: {lookup}")
            try:
                user = await fetch_json(
                    client,
                    f"https://api.github.com/users/{path_seg(lookup)}",
                    headers=_gh_headers(),
                )
            except Exception:
                continue
            login = (user.get("login") or "").lower()
            if not login or login in seen_logins:
                continue
            seen_logins.add(login)
            exact = login in {handle.lower(), lookup.lower()} or (local and login == local)
            profile_url = user.get("html_url") or f"https://github.com/{user.get('login')}"
            facts.append(
                self.fact(
                    predicate="username",
                    value=f"github:{user.get('login')}",
                    section="social",
                    confidence=0.86 if exact else 0.5,
                    url=profile_url,
                    publisher="GitHub",
                    raw=user,
                    extra={"platform": "github", "handle": user.get("login")},
                    candidate=not exact,
                )
            )
            for field in fields_from_github_user(user):
                facts.append(
                    self.fact(
                        predicate=field["predicate"],
                        value=field["value"],
                        section=field["section"],
                        confidence=0.7 if exact else 0.42,
                        url=profile_url,
                        publisher="GitHub",
                        extra={"handle": user.get("login"), "via": "github-profile"},
                        candidate=not exact,
                    )
                )

        searches: list[tuple[str, str | None]] = []
        tokens = name_tokens(seed.full_name)
        if len(tokens) >= 2:
            searches.append((f'fullname:"{seed.full_name.strip()}"', None))
            searches.append((f"{tokens[0]} {tokens[-1]} in:name", None))
        if local:
            searches.append((local, local))
        for handle in split_usernames(seed.username):
            searches.append((f"{handle} in:login", handle))
            searches.append((f'"{handle}" in:name', handle))

        for q, must_handle in searches:
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
                name = str(user.get("name") or "")
                if must_handle and not github_search_hit_allowed(must_handle, login, name):
                    if must_handle and "in:name" in q:
                        try:
                            full = await fetch_json(
                                client,
                                f"https://api.github.com/users/{path_seg(login)}",
                                headers=_gh_headers(),
                            )
                        except Exception:
                            continue
                        name = str(full.get("name") or "")
                        if not github_search_hit_allowed(must_handle, login, name):
                            continue
                    else:
                        continue
                seen_logins.add(login.lower())
                name_hit = bool(must_handle and github_search_hit_allowed(must_handle, login, name))
                exact = login.lower() in {h.lower() for h in handles} or name_hit
                extra = {"platform": "github", "handle": login}
                if name_hit and not identity_match(must_handle or "", login):
                    extra["via"] = "persona-search"
                facts.append(
                    self.fact(
                        predicate="username",
                        value=f"github:{login}",
                        section="social",
                        confidence=0.78 if exact else 0.42,
                        url=user.get("html_url") or f"https://github.com/{login}",
                        publisher="GitHub",
                        raw=user,
                        extra=extra,
                        candidate=not exact,
                    )
                )
        facts = mark_social_confidence(facts, seed)
        if not facts:
            log("GitHub: no public users")
        return facts
