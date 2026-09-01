from viha.core.searchutil import (
    is_consumer_mail,
    is_fetchable_result,
    is_people_broker_url,
    unwrap_search_url,
    wayback_identity,
    wayback_latest,
)


def test_unwrap_ddg_uddg():
    href = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.com%2Fphone%2F1-202-555-0100%2F"
        "&rut=abc"
    )
    assert unwrap_search_url(href) == "https://www.example.com/phone/1-202-555-0100/"


def test_unwrap_bing_ck():
    href = (
        "https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u=a1aHR0cHM6Ly93d3cuaW50ZWxpdXMuY29tL3JldmVyc2UtcGhvbmUtbG9va3VwLzIwMi01NTUtMDEwMA"
    )
    assert unwrap_search_url(href) == "https://www.intelius.com/reverse-phone-lookup/202-555-0100"


def test_consumer_mail():
    assert is_consumer_mail("gmail.com")
    assert is_consumer_mail("Gmail.Com")
    assert not is_consumer_mail("acme-widgets.example")


def test_fetchable_people_index_not_google():
    assert is_fetchable_result("https://www.fastpeoplesearch.com/ada-example-public_id_G123")
    assert is_fetchable_result("https://www.intelius.com/reverse-phone-lookup/202-555-0100")
    assert is_fetchable_result("https://www.spokeo.com/Ada-Example-Public")
    assert is_people_broker_url("https://www.spokeo.com/Ada-Example-Public")
    assert not is_fetchable_result("https://www.google.com/search?q=ada")
    assert not is_fetchable_result("https://www.facebook.com/login")
    assert wayback_latest("https://example.com/x").startswith("https://web.archive.org/web/2/")
    assert "id_" in wayback_identity("20240101000000", "https://example.com/x")
