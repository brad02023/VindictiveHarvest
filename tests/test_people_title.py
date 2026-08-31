from viha.collectors.search import WebSearchCollector, _extract_people_title
from viha.core.models import Seed


def test_people_title_skips_truncated_city():
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public")
    title = "(202) 555-0100 Phone number Owner Ada E Public, Age 25 in San ..."
    facts = _extract_people_title(c, title, "https://example.com/x", seed)
    preds = {f.predicate: f.value for f in facts}
    assert preds["aka"] == "Ada E Public"
    assert preds["age"] == "25"
    assert "location" not in preds


def test_people_title_keeps_full_city():
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public")
    title = "Owner Ada E Public, Age 25 in San Antonio, TX"
    facts = _extract_people_title(c, title, "https://example.com/x", seed)
    preds = {f.predicate: f.value for f in facts}
    assert preds["location"] == "San Antonio, TX"
