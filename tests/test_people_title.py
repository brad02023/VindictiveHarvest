from viha.collectors.search import (
    WebSearchCollector,
    _extract_people_title,
    _people_dork_queries,
    facts_from_result_html,
)
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


def test_people_title_dob_and_street():
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public")
    title = "Ada Example Public, DOB 01/15/1990, 500 Commerce Street, Dallas, TX"
    facts = _extract_people_title(c, title, "https://example.com/x", seed)
    preds = {f.predicate: f.value for f in facts}
    assert preds["dob"] == "1990-01-15"
    assert "Commerce Street" in preds["address"]
    assert all(f.candidate for f in facts)


def test_people_title_phone_url_extracts_age_without_name():
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    blob = "Age 26 • Austin, TX Born July 2000 https://www.intelius.com/reverse-phone-lookup/202-555-0100"
    facts = _extract_people_title(
        c,
        blob,
        "https://www.intelius.com/reverse-phone-lookup/202-555-0100",
        seed,
        "Bing",
        True,
    )
    preds = {f.predicate: f.value for f in facts}
    assert preds["age"] == "26"
    assert preds["location"] == "Austin, TX"
    assert preds["dob"] == "2000-07"


def test_people_title_phone_boosts_confidence():
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    title = "(202) 555-0100 Phone number Owner Ada E Public, Age 25 in San Antonio, TX"
    facts = _extract_people_title(c, title, "https://www.intelius.com/x", seed, "Bing")
    age = next(f for f in facts if f.predicate == "age")
    assert age.candidate is True
    assert age.confidence >= 0.67
    assert age.extra.get("phone_match") is True
    assert age.extra.get("engine") == "Bing"


def test_parse_bing_html_titles_and_unwrap():
    html = """
    <ol id="b_results">
    <li class="b_algo">
      <h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u=a1aHR0cHM6Ly93d3cuaW50ZWxpdXMuY29tL3JldmVyc2UtcGhvbmUtbG9va3VwLzIwMi01NTUtMDEwMA">
        (202) 555-0100 Phone number Owner Ada E Public, Age 25 in San Antonio, TX
      </a></h2>
      <p class="b_lineclamp2">Ada E Public is listed in San Antonio, TX.</p>
    </li>
    <li class="b_algo">
      <h2><a href="https://www.bing.com/images/search?q=x">Images</a></h2>
    </li>
    </ol>
    """
    from viha.collectors.search import parse_bing_html

    rows = parse_bing_html(html)
    assert rows
    url, title, snippet = rows[0]
    assert url == "https://www.intelius.com/reverse-phone-lookup/202-555-0100"
    assert "Ada E Public" in title
    assert "San Antonio" in snippet
    assert all("bing.com/images" not in u for u, _t, _s in rows)


def test_people_dorks_use_site_operator():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    dorks = _people_dork_queries(seed)
    assert any("site:fastpeoplesearch.com" in q and "Ada Example Public" in q for q in dorks)
    assert any("site:intelius.com" in q and "202-555-0100" in q for q in dorks)


def test_facts_from_result_html_parses_people_index_page():
    html = """
    <html><head><title>Ada Example Public Age 26 • Austin, TX</title></head>
    <body>Ada Example Public Age 26 • Austin, TX Born July 2000
    <a href="/address/123-main-street-austin-tx">123 Main Street, Austin, TX</a>
    </body></html>
    """
    c = WebSearchCollector()
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    facts = facts_from_result_html(
        c,
        html,
        "https://www.fastpeoplesearch.com/ada-example-public_id_G123",
        seed,
    )
    preds = {f.predicate: f.value for f in facts}
    assert preds["age"] == "26"
    assert any("Main Street" in f.value for f in facts if f.predicate == "address")
    assert all(f.extra.get("via") == "search-fetch" for f in facts)
