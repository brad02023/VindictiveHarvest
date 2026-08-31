from viha.collectors.registry import COLLECTORS


def test_collector_ids_unique():
    ids = [c.id for c in COLLECTORS]
    assert len(ids) == len(set(ids))
    assert all(c.id.startswith("viha.db.") for c in COLLECTORS)
    assert all(c.label for c in COLLECTORS)


def test_expected_databases_registered():
    ids = {c.id for c in COLLECTORS}
    for needed in (
        "viha.db.courtlistener",
        "viha.db.edgar",
        "viha.db.opensanctions",
        "viha.db.wikidata",
        "viha.db.opencorp",
        "viha.db.search",
        "viha.db.github",
        "viha.db.gravatar",
        "viha.db.social",
        "viha.db.infra",
        "viha.db.recipes",
        "viha.db.emailcheck",
        "viha.db.wayback",
        "viha.db.fec",
        "viha.db.wmn",
        "viha.db.subdomains",
        "viha.db.texas",
        "viha.db.employees",
    ):
        assert needed in ids
