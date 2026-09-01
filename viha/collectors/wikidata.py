from __future__ import annotations

from typing import Any

from viha.collectors.base import Collector, LogFn, fetch_json
from viha.core.identity import parse_wikidata_time, wikidata_is_person_hit
from viha.core.models import Fact, Seed


def _snak_time(claims: dict[str, Any], pid: str) -> str:
    for claim in claims.get(pid) or []:
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if isinstance(value, dict) and value.get("time"):
            return parse_wikidata_time(str(value["time"]))
    return ""


def _snak_ids(claims: dict[str, Any], pid: str) -> list[str]:
    out: list[str] = []
    for claim in claims.get(pid) or []:
        value = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        if isinstance(value, dict) and value.get("id"):
            out.append(str(value["id"]))
    return out


class WikidataCollector(Collector):
    id = "viha.db.wikidata"
    label = "Wikidata"
    blurb = "Notable people: IDs, birth date, and places"

    async def reap(self, seed: Seed, client, log: LogFn) -> list[Fact]:
        query = seed.full_name.strip() or seed.org.strip()
        if not query:
            log("Wikidata skipped — need a name or org")
            return []
        log(f"Wikidata search: {query}")
        data = await fetch_json(
            client,
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": query,
                "language": "en",
                "format": "json",
                "limit": 8,
            },
        )
        facts: list[Fact] = []
        best_qid = ""
        for hit in data.get("search") or []:
            label = hit.get("label") or query
            desc = hit.get("description") or ""
            qid = hit.get("id") or ""
            url = hit.get("concepturi") or f"https://www.wikidata.org/wiki/{qid}"
            strong = bool(seed.full_name.strip()) and wikidata_is_person_hit(label, desc, seed)
            facts.append(
                self.fact(
                    predicate="wikidata",
                    value=f"{label} — {desc}".strip(" —"),
                    section="identity",
                    confidence=0.62 if strong else 0.4,
                    url=url,
                    publisher="Wikidata",
                    raw=hit,
                    candidate=not strong,
                )
            )
            if strong and not best_qid:
                best_qid = qid
        if best_qid:
            facts.extend(await self._claims(client, log, best_qid))
        if not facts:
            log("Wikidata: no notable-entity hits")
        return facts

    async def _claims(self, client, log: LogFn, qid: str) -> list[Fact]:
        try:
            data = await fetch_json(
                client,
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": qid,
                    "props": "claims|labels|descriptions",
                    "languages": "en",
                    "format": "json",
                },
            )
        except Exception as exc:
            log(f"Wikidata claims skipped: {exc}")
            return []
        ent = ((data.get("entities") or {}).get(qid)) or {}
        claims = ent.get("claims") or {}
        url = f"https://www.wikidata.org/wiki/{qid}"
        facts: list[Fact] = []
        dob = _snak_time(claims, "P569")
        if dob:
            facts.append(
                self.fact(
                    predicate="dob",
                    value=dob,
                    section="identity",
                    confidence=0.78,
                    url=url,
                    publisher="Wikidata",
                    extra={"qid": qid, "pid": "P569"},
                    candidate=False,
                )
            )
        born_ids = _snak_ids(claims, "P19")
        residences = _snak_ids(claims, "P551")
        labels = await self._labels(client, born_ids + residences)
        if born_ids and labels.get(born_ids[0]):
            facts.append(
                self.fact(
                    predicate="location",
                    value=f"{labels[born_ids[0]]} (born)",
                    section="identity",
                    confidence=0.7,
                    url=url,
                    publisher="Wikidata",
                    extra={"qid": qid, "pid": "P19"},
                    candidate=False,
                )
            )
        if residences and labels.get(residences[0]):
            facts.append(
                self.fact(
                    predicate="location",
                    value=labels[residences[0]],
                    section="identity",
                    confidence=0.72,
                    url=url,
                    publisher="Wikidata",
                    extra={"qid": qid, "pid": "P551"},
                    candidate=False,
                )
            )
        if facts:
            log(f"Wikidata claims: {qid} ({len(facts)} identity fields)")
        return facts

    async def _labels(self, client, qids: list[str]) -> dict[str, str]:
        ids = [q for q in dict.fromkeys(qids) if q]
        if not ids:
            return {}
        try:
            data = await fetch_json(
                client,
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": "|".join(ids[:8]),
                    "props": "labels",
                    "languages": "en",
                    "format": "json",
                },
            )
        except Exception:
            return {}
        out: dict[str, str] = {}
        for qid, ent in (data.get("entities") or {}).items():
            label = ((ent.get("labels") or {}).get("en") or {}).get("value") or ""
            if label:
                out[qid] = label
        return out
