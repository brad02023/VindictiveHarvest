from __future__ import annotations

import asyncio

from viha.collectors.base import Collector, LogFn
from viha.collectors.social_catalog import (
    BROWSER_UA,
    HIGH_SIGNAL,
    extract_social_links,
    load_sites,
    page_is_hit,
    platform_of,
)
from viha.core.models import Fact, Seed
from viha.core.identity import fields_from_github_user
from viha.core.handles import STYLES, path_seg, probe_urls, shape_handle
from viha.core.persona_search import SEARCHERS, merge_persona_targets, platform_key, search_personas
from viha.core.normalize import (
    email_local_part,
    is_simple_handle,
    name_tokens,
    split_usernames,
    username_candidates,
)


def handle_is_strong(handle: str, seed: Seed) -> bool:
    raw = (handle or "").strip().lower()
    supplied = {h.lower() for h in split_usernames(seed.username)}
    if raw in supplied:
        return True
    for supplied_handle in supplied:
        for style in STYLES:
            if raw in shape_handle(supplied_handle, style):
                return True
    if " " not in raw and "/" not in raw and raw.split(".")[0] in supplied:
        return True
    local = email_local_part(seed.email)
    if local and raw == local and (any(ch.isdigit() for ch in local) or len(local) >= 10):
        return True
    return False


def _is_social_profile(fact: Fact) -> bool:
    if fact.section != "social" or fact.predicate != "username":
        return False
    extra = fact.extra or {}
    return not bool(extra.get("miss") or extra.get("kind") == "miss")


def mark_social_confidence(facts: list[Fact], seed: Seed) -> list[Fact]:
    for fact in facts:
        if fact.extra.get("miss") or fact.predicate == "miss":
            fact.candidate = True
            continue
        if not _is_social_profile(fact):
            continue
        handle = (fact.extra or {}).get("handle") or fact.value.split(":", 1)[-1]
        if fact.extra.get("via") == "link-in-bio":
            fact.candidate = False
            fact.confidence = max(fact.confidence, 0.72)
            continue
        if fact.extra.get("via") == "persona-search":
            fact.candidate = False
            fact.confidence = max(fact.confidence, 0.76)
            continue
        if fact.extra.get("via") == "site-search":
            continue
        if handle_is_strong(str(handle), seed):
            fact.candidate = False
            fact.confidence = max(fact.confidence, 0.72)
            continue
        fact.candidate = True
        fact.confidence = min(fact.confidence, 0.48)

    by_handle: dict[tuple[str, str], list[Fact]] = {}
    for fact in facts:
        if not _is_social_profile(fact) or fact.candidate:
            continue
        plat = str((fact.extra or {}).get("platform") or fact.source.publisher).lower()
        handle = str((fact.extra or {}).get("handle") or fact.value.split(":", 1)[-1]).lower()
        by_handle.setdefault((plat, handle), []).append(fact)
    for group in by_handle.values():
        if len(group) <= 1:
            continue
        group.sort(key=lambda f: f.confidence, reverse=True)
        for extra in group[1:]:
            extra.candidate = True
            extra.confidence = min(extra.confidence, 0.45)
    return facts


def hunt_handles(seed: Seed) -> list[str]:
    local = email_local_part(seed.email)
    tokens = name_tokens(seed.full_name)
    handles: list[str] = []
    handles.extend(split_usernames(seed.username))
    if local:
        handles.append(local)
    for h in username_candidates(seed.full_name, seed.email, seed.username):
        if h not in handles:
            handles.append(h)
    if len(tokens) > 1:
        firstlast = f"{tokens[0]}{tokens[-1]}"
        if firstlast not in handles:
            handles.append(firstlast)
    return handles[:24]


class SocialHuntCollector(Collector):
    id = "viha.db.social"
    label = "Social hunt"
    blurb = "Public profiles across social, gaming, and app platforms"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        handles = hunt_handles(seed)
        if not handles:
            log("Social hunt skipped — need name, email, or username")
            return []
        log(f"Social hunt handles: {', '.join(handles)}")
        log("Discord has no public email/phone lookup — add a Discord username in Seeds if you have one.")
        sites = load_sites()
        strong = {h for h in handles if handle_is_strong(h, seed)}
        sem = asyncio.Semaphore(16)
        headers = {"User-Agent": BROWSER_UA, "Accept": "text/html,application/json"}

        async def probe(handle: str, site: dict) -> list[Fact]:
            if handle not in strong and site.get("name") not in HIGH_SIGNAL:
                return []
            targets = probe_urls(site, handle)
            found: list[tuple[str, str]] = []
            if handle in strong and platform_key(site.get("name") or "") in SEARCHERS:
                async with sem:
                    found = await search_personas(client, site.get("name") or "", handle)
            search_urls = {u.rstrip("/") for _, u in found}
            targets = merge_persona_targets(targets, found, handle)
            if not targets:
                return []
            plat = (site["name"] or "").lower().replace(".", "").replace(" ", "")
            for shaped, url in targets:
                async with sem:
                    try:
                        r = await client.get(
                            url,
                            headers=headers,
                            timeout=12.0,
                            follow_redirects=True,
                        )
                    except Exception as exc:
                        log(f"Social {site['name']}/{shaped}: {exc}")
                        continue
                body = r.text or ""
                from_search = (url or "").rstrip("/") in search_urls or str(r.url).rstrip("/") in search_urls
                check_handle = handle if from_search else shaped
                if not page_is_hit(
                    site,
                    r.status_code,
                    body,
                    check_handle,
                    str(r.url),
                    requested_url=url,
                ):
                    continue
                extra = {"platform": plat, "handle": check_handle, "supplied": handle}
                if from_search:
                    extra["via"] = "persona-search"
                facts = [
                    self.fact(
                        predicate="username",
                        value=f"{plat}:{check_handle}",
                        section="social",
                        confidence=0.78 if from_search else 0.74,
                        url=str(r.url) or url,
                        publisher=site["name"],
                        extra=extra,
                    )
                ]
                if site.get("parse_links"):
                    for linked_plat, href in extract_social_links(body):
                        facts.append(
                            self.fact(
                                predicate="username",
                                value=f"{linked_plat}:{href}",
                                section="social",
                                confidence=0.76,
                                url=href,
                                publisher=linked_plat,
                                extra={
                                    "platform": linked_plat,
                                    "handle": check_handle,
                                    "via": "link-in-bio",
                                    "from": site["name"],
                                },
                            )
                        )
                return facts
            if handle in strong and targets:
                _, miss_url = targets[0]
                return [
                    self.fact(
                        predicate="miss",
                        value=f"{site['name']}: {handle}",
                        section="social",
                        confidence=0.1,
                        url=miss_url,
                        publisher=site["name"],
                        extra={
                            "platform": plat,
                            "handle": handle,
                            "miss": True,
                            "kind": "miss",
                        },
                        candidate=True,
                    )
                ]
            return []

        tasks = [probe(handle, site) for handle in handles for site in sites]
        api_github = []
        api_reddit = []
        api_bsky = []
        for handle in handles:
            api_github.extend(shape_handle(handle, "github"))
            api_reddit.extend(shape_handle(handle, "reddit"))
            api_bsky.extend(shape_handle(handle, "generic"))
        tasks.extend([self._reddit_api(client, h, sem) for h in dict.fromkeys(api_reddit)])
        tasks.extend([self._github_api(client, h, sem) for h in dict.fromkeys(api_github)])
        tasks.extend([self._bluesky_api(client, h, sem) for h in dict.fromkeys(api_bsky) if is_simple_handle(h)])

        bundles = await asyncio.gather(*tasks)
        facts: list[Fact] = []
        seen: set[str] = set()
        for bundle in bundles:
            for fact in bundle:
                key = (fact.extra.get("platform"), fact.value.lower(), fact.source.url)
                if key in seen:
                    continue
                seen.add(key)
                facts.append(fact)
        facts = mark_social_confidence(facts, seed)
        hits = [f for f in facts if f.predicate != "miss" and not f.extra.get("miss")]
        confirmed = sum(1 for f in hits if not f.candidate)
        misses = len(facts) - len(hits)
        if not hits and not misses:
            log("Social hunt: no public profiles found")
        else:
            log(
                f"Social hunt: {len(hits)} profiles "
                f"({confirmed} confirmed, {len(hits) - confirmed} candidates, {misses} misses hidden)"
            )
        return facts

    async def _reddit_api(self, client, handle: str, sem) -> list[Fact]:
        async with sem:
            r = await client.get(
                f"https://www.reddit.com/user/{path_seg(handle)}/about.json",
                headers={"User-Agent": "VIHA/0.1 local-research"},
                timeout=10.0,
            )
        if r.status_code != 200:
            return []
        try:
            data = r.json()
        except Exception:
            return []
        if data.get("kind") != "t2":
            return []
        name = ((data.get("data") or {}).get("name")) or handle
        return [
            self.fact(
                predicate="username",
                value=f"reddit:{name}",
                section="social",
                confidence=0.82,
                url=f"https://www.reddit.com/user/{name}",
                publisher="Reddit",
                raw=data.get("data"),
                extra={"platform": "reddit", "handle": name},
            )
        ]

    async def _github_api(self, client, handle: str, sem) -> list[Fact]:
        async with sem:
            r = await client.get(f"https://api.github.com/users/{path_seg(handle)}", timeout=10.0)
        if r.status_code != 200:
            return []
        try:
            user = r.json()
        except Exception:
            return []
        login = user.get("login") or handle
        profile_url = user.get("html_url") or f"https://github.com/{login}"
        facts = [
            self.fact(
                predicate="username",
                value=f"github:{login}",
                section="social",
                confidence=0.86,
                url=profile_url,
                publisher="GitHub",
                raw=user,
                extra={"platform": "github", "handle": login},
            )
        ]
        for field in fields_from_github_user(user):
            facts.append(
                self.fact(
                    predicate=field["predicate"],
                    value=field["value"],
                    section=field["section"],
                    confidence=0.7,
                    url=profile_url,
                    publisher="GitHub",
                    extra={"handle": login, "via": "github-profile"},
                )
            )
        if user.get("blog"):
            blog = str(user["blog"])
            if not blog.startswith("http"):
                blog = "https://" + blog
            plat = platform_of(blog) or "web"
            facts.append(
                self.fact(
                    predicate="username" if plat != "web" else "web_mention",
                    value=f"{plat}:{blog}" if plat != "web" else blog,
                    section="social" if plat != "web" else "web",
                    confidence=0.7,
                    url=blog,
                    publisher="GitHub profile",
                    extra={"platform": plat, "handle": login, "via": "link-in-bio"},
                )
            )
        if user.get("twitter_username"):
            tw = user["twitter_username"]
            facts.append(
                self.fact(
                    predicate="username",
                    value=f"x:{tw}",
                    section="social",
                    confidence=0.8,
                    url=f"https://x.com/{tw}",
                    publisher="GitHub profile",
                    extra={"platform": "x", "handle": tw, "via": "link-in-bio"},
                )
            )
        return facts

    async def _bluesky_api(self, client, handle: str, sem) -> list[Fact]:
        actor = f"{handle}.bsky.social"
        async with sem:
            r = await client.get(
                "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile",
                params={"actor": actor},
                timeout=10.0,
            )
        if r.status_code != 200:
            return []
        profile = r.json()
        disp = profile.get("handle") or actor
        return [
            self.fact(
                predicate="username",
                value=f"bluesky:{disp}",
                section="social",
                confidence=0.8,
                url=f"https://bsky.app/profile/{disp}",
                publisher="Bluesky",
                raw=profile,
                extra={"platform": "bluesky", "handle": disp},
            )
        ]
