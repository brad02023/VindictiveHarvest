from __future__ import annotations

from viha.collectors.base import Collector
from viha.collectors.courtlistener import CourtListenerCollector
from viha.collectors.edgar import EdgarCollector
from viha.collectors.email_check import EmailCheckCollector
from viha.collectors.employees import EmployeeCollector
from viha.collectors.fec import FecCollector
from viha.collectors.github import GitHubCollector
from viha.collectors.gravatar import GravatarCollector
from viha.collectors.infra import InfraCollector
from viha.collectors.opencorporates import OpenCorporatesCollector
from viha.collectors.opensanctions import OpenSanctionsCollector
from viha.collectors.recipes import RecipeCollector
from viha.collectors.search import WebSearchCollector
from viha.collectors.social import SocialHuntCollector
from viha.collectors.subdomains import SubdomainCollector
from viha.collectors.texas import TexasRecordsCollector
from viha.collectors.wayback import WaybackCollector
from viha.collectors.wikidata import WikidataCollector
from viha.collectors.wmn import WhatsMyNameCollector

COLLECTORS: list[Collector] = [
    RecipeCollector(),
    SocialHuntCollector(),
    WhatsMyNameCollector(),
    EmailCheckCollector(),
    GitHubCollector(),
    GravatarCollector(),
    WebSearchCollector(),
    CourtListenerCollector(),
    EdgarCollector(),
    FecCollector(),
    OpenSanctionsCollector(),
    WikidataCollector(),
    OpenCorporatesCollector(),
    EmployeeCollector(),
    TexasRecordsCollector(),
    WaybackCollector(),
    InfraCollector(),
    SubdomainCollector(),
]


def enabled_collectors(selected: list[str] | None = None) -> list[Collector]:
    if not selected:
        return [c for c in COLLECTORS if c.default_on]
    wanted = set(selected)
    return [c for c in COLLECTORS if c.id in wanted]
