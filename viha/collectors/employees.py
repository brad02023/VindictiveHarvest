from __future__ import annotations

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.settings import load_settings


class EmployeeCollector(Collector):
    id = "viha.db.employees"
    label = "Org people"
    blurb = "GitHub org members for a company/domain seed (free API)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        org = (seed.org or "").strip()
        if not org:
            log("Org people skipped — set Company / org")
            return []
        slug = org.split(".")[0].replace(" ", "").lower()
        headers = {"Accept": "application/vnd.github+json"}
        token = (load_settings().get("github_token") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        log(f"GitHub org members: {slug}")
        try:
            rows = await fetch_json(client, f"https://api.github.com/orgs/{slug}/members", headers=headers)
        except Exception as exc:
            log(f"GitHub org: {exc}")
            return []
        if not isinstance(rows, list):
            return []
        facts: list[Fact] = []
        for user in rows[:20]:
            login = user.get("login") or ""
            facts.append(
                self.fact(
                    predicate="username",
                    value=f"github:{login}",
                    section="social",
                    confidence=0.55,
                    url=user.get("html_url") or f"https://github.com/{login}",
                    publisher="GitHub org",
                    extra={"platform": "github", "handle": login, "org": slug},
                    candidate=True,
                )
            )
        return facts
