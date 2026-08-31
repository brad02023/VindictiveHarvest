from __future__ import annotations

import json
import socket

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_email
from viha.core.searchutil import is_consumer_mail


class InfraCollector(Collector):
    id = "viha.db.infra"
    label = "DNS / CT / WHOIS"
    blurb = "Domain records, certs, and public WHOIS for an email domain"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        email = normalize_email(seed.email)
        domain = email.split("@", 1)[1] if email else ""
        org_domain = ""
        blob = (seed.org or "").strip().lower()
        if "." in blob and " " not in blob:
            org_domain = blob
        target = org_domain or ("" if is_consumer_mail(domain) else domain)
        if domain and is_consumer_mail(domain) and not org_domain:
            log(f"Infra skipped — {domain} is a consumer mailbox provider")
            return []
        if not target:
            log("Infra skipped — need an email domain or org domain")
            return []

        facts: list[Fact] = []
        log(f"DNS lookup: {target}")
        try:
            answers = sorted({info[4][0] for info in socket.getaddrinfo(target, None)})
            if answers:
                facts.append(
                    self.fact(
                        predicate="dns_a",
                        value=f"{target} → {', '.join(answers[:6])}",
                        section="infra",
                        confidence=0.9,
                        url=f"https://{target}",
                        publisher="DNS",
                        raw=answers,
                    )
                )
        except OSError as exc:
            log(f"DNS: {exc}")

        log(f"crt.sh: {target}")
        try:
            rows = await fetch_json(client, "https://crt.sh/", params={"q": target, "output": "json"})
            names: set[str] = set()
            if isinstance(rows, list):
                for row in rows[:40]:
                    nv = row.get("name_value") or ""
                    for part in str(nv).split("\n"):
                        if part.strip():
                            names.add(part.strip().lower())
            for name in sorted(names)[:15]:
                facts.append(
                    self.fact(
                        predicate="certificate",
                        value=name,
                        section="infra",
                        confidence=0.65,
                        url=f"https://crt.sh/?q={target}",
                        publisher="crt.sh",
                        raw={"name": name},
                    )
                )
        except Exception as exc:
            log(f"crt.sh: {exc}")

        log(f"RDAP: {target}")
        try:
            data = await fetch_json(client, f"https://rdap.org/domain/{target}")
            ldh = data.get("ldhName") or target
            status = ", ".join(data.get("status") or [])
            facts.append(
                self.fact(
                    predicate="whois",
                    value=f"{ldh} · {status}".strip(" ·"),
                    section="infra",
                    confidence=0.8,
                    url=f"https://rdap.org/domain/{target}",
                    publisher="RDAP",
                    raw=json.dumps({k: data.get(k) for k in ("ldhName", "status", "events")})[:2000],
                )
            )
        except Exception as exc:
            log(f"RDAP: {exc}")
        return facts
