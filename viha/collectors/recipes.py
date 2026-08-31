from __future__ import annotations

from viha.collectors.base import Collector, LogFn
from viha.core.models import Fact, Seed
from viha.core.recipes import recipe_links


class RecipeCollector(Collector):
    id = "viha.db.recipes"
    label = "Search recipes"
    blurb = "IntelTechniques-style public search URLs"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        links = recipe_links(seed)
        log(f"Search recipes: {len(links)} public lookup URLs")
        facts: list[Fact] = []
        for label, url, section in links:
            facts.append(
                self.fact(
                    predicate="recipe",
                    value=label,
                    section="recipes",
                    confidence=0.3,
                    url=url,
                    publisher="Search recipe",
                    extra={"kind": "recipe"},
                    candidate=False,
                    note="Open in a browser - not fetched automatically",
                )
            )
        return facts
