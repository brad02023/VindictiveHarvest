from viha.collectors.people import discovered_people_urls, people_index_link_facts, people_index_urls
from viha.collectors.texas import _public_record_links
from viha.core.models import Case, Fact, Seed, Source
from viha.core.recipes import recipe_links


def test_people_index_phone_url_skips_bare_name():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    urls = people_index_urls(seed)
    joined = " ".join(u for _, u in urls)
    assert "202-555-0100" in joined
    assert "fastpeoplesearch.com/name/ada-public" not in joined
    assert all("intelius.com/reverse-phone-lookup" in u or "fastpeoplesearch.com/" in u for _, u in urls)


def test_people_index_name_city_when_place_known():
    seed = Seed(full_name="Ada Example Public", city="Austin", state="TX")
    urls = {u for _, u in people_index_urls(seed)}
    assert any("fastpeoplesearch.com/name/ada-public_austin-tx" in u for u in urls)


def test_people_index_link_facts_are_visible_identity_rows():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    facts = people_index_link_facts(seed)
    assert facts
    assert len(facts) >= 2
    assert all(f.predicate == "people_index" for f in facts)
    assert all(f.section == "identity" for f in facts)
    assert all(f.source.url.startswith("http") for f in facts)
    assert not any(f.extra.get("lookup") for f in facts)
    urls = {f.source.url for f in facts}
    assert any("fastpeoplesearch.com" in u for u in urls)
    assert any("intelius.com/reverse-phone-lookup" in u for u in urls)


def test_tx_210_includes_guadalupe_and_bexar_cad():
    seed = Seed(full_name="Ada Example Public", phone="210 555 0100")
    labels = [l for l, _, _ in _public_record_links(seed)]
    assert any("Bexar" in l for l in labels)
    assert any("Guadalupe CAD" in l for l in labels)


def test_recipes_include_bing_fps_and_guadalupe():
    seed = Seed(full_name="Ada Example Public", phone="210 555 0100", email="ada@example.com", state="TX")
    labels = [l for l, _, _ in recipe_links(seed)]
    assert any("Bing" in l for l in labels)
    assert any("FastPeopleSearch" in l for l in labels)
    assert any("Guadalupe CAD" in l for l in labels)


def test_discovered_people_urls_prefer_profile_and_spokeo():
    case = Case(seed=Seed(full_name="Ada Example Public", phone="202 555 0100"))
    case.add_fact(
        Fact(
            predicate="web_mention",
            value="Owner Ada E Public, Age 25 in Austin, TX",
            section="web",
            confidence=0.5,
            source=Source(publisher="Bing", url="https://www.spokeo.com/Ada-Example-Public"),
        )
    )
    case.add_fact(
        Fact(
            predicate="people_index",
            value="FastPeopleSearch profile",
            section="identity",
            confidence=0.55,
            source=Source(
                publisher="FastPeopleSearch",
                url="https://www.fastpeoplesearch.com/ada-example-public_id_G999",
            ),
            extra={"profile_url": "https://www.fastpeoplesearch.com/ada-example-public_id_G999"},
        )
    )
    urls = discovered_people_urls(case)
    assert urls[0].endswith("_id_G999")
    assert any("spokeo.com" in u for u in urls)
