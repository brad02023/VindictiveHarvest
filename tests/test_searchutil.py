from viha.core.searchutil import is_consumer_mail, unwrap_search_url


def test_unwrap_ddg_uddg():
    href = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.example.com%2Fphone%2F1-202-555-0100%2F"
        "&rut=abc"
    )
    assert unwrap_search_url(href) == "https://www.example.com/phone/1-202-555-0100/"


def test_consumer_mail():
    assert is_consumer_mail("gmail.com")
    assert is_consumer_mail("Gmail.Com")
    assert not is_consumer_mail("acme-widgets.example")
