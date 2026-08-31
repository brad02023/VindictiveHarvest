from __future__ import annotations

import socket

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.models import Fact, Seed
from viha.core.normalize import normalize_email
from viha.core.searchutil import is_consumer_mail


class SubdomainCollector(Collector):
    id = "viha.db.subdomains"
    label = "Subdomains / InternetDB"
    blurb = "crt.sh names + free Shodan InternetDB (no paid key)"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        domain = ""
        org = (seed.org or "").strip().lower()
        if "." in org and " " not in org:
            domain = org
        email = normalize_email(seed.email)
        if email:
            host = email.split("@", 1)[1]
            if not is_consumer_mail(host):
                domain = domain or host
        if not domain:
            log("Subdomains skipped — need an org domain (not gmail/yahoo)")
            return []

        facts: list[Fact] = []
        log(f"crt.sh wildcards: {domain}")
        names: set[str] = set()
        try:
            rows = await fetch_json(client, "https://crt.sh/", params={"q": f"%.{domain}", "output": "json"})
            if isinstance(rows, list):
                for row in rows[:80]:
                    for part in str(row.get("name_value") or "").split("\n"):
                        part = part.strip().lower().lstrip("*.")
                        if part.endswith(domain):
                            names.add(part)
        except Exception as exc:
            log(f"crt.sh: {exc}")
        for name in sorted(names)[:25]:
            facts.append(
                self.fact(
                    predicate="subdomain",
                    value=name,
                    section="infra",
                    confidence=0.7,
                    url=f"https://crt.sh/?q={domain}",
                    publisher="crt.sh",
                )
            )

        try:
            ip = socket.gethostbyname(domain)
        except OSError as exc:
            log(f"DNS {domain}: {exc}")
            ip = ""
        if ip:
            log(f"InternetDB: {ip}")
            try:
                data = await fetch_json(client, f"https://internetdb.shodan.io/{ip}")
                ports = ",".join(str(p) for p in (data.get("ports") or [])[:12])
                vulns = ",".join((data.get("vulns") or [])[:6])
                cpes = ",".join((data.get("cpes") or [])[:4])
                facts.append(
                    self.fact(
                        predicate="host",
                        value=f"{domain} {ip} ports {ports or '—'}",
                        section="infra",
                        confidence=0.75,
                        url=f"https://internetdb.shodan.io/{ip}",
                        publisher="Shodan InternetDB",
                        raw=data,
                        extra={"vulns": vulns, "cpes": cpes},
                    )
                )
            except Exception as exc:
                log(f"InternetDB: {exc}")
        return facts
