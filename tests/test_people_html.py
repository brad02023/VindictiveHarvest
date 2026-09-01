from viha.core.models import Seed
from viha.core.people_html import facts_from_people_html, parse_people_index_html, publisher_from_url

FPS_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Ada Example Public Age 26 • Austin, TX</title>
<link rel="canonical" href="https://www.fastpeoplesearch.com/ada-example-public_id_G123">
</head>
<body>
<h1>Ada Example Public</h1>
Age 26 • Austin, TX
Born July 2000
<h2>Current Address:</h2>
<a href="/address/123-main-street-austin-tx-78701">123 Main Street, Austin, TX 78701</a>
<h2>Past Addresses:</h2>
<a href="/address/500-commerce-street-dallas-tx">500 Commerce Street, Dallas, TX 75201</a>
previously lived in Lakewood, WA
<h2>Email addresses</h2>
<a href="mailto:jane.neighbor@example.net">jane.neighbor@example.net</a>
<h2>Related To:</h2>
<a href="/name/jane-neighbor">Jane Neighbor</a>
Phone Numbers
(512) 555-0199
(202) 555-0100
</body>
</html>
"""


def test_publisher_from_url():
    assert publisher_from_url("https://www.fastpeoplesearch.com/x") == "FastPeopleSearch"


def test_parse_saved_fastpeoplesearch_html():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100", email="ada@example.com")
    page = parse_people_index_html(FPS_HTML, seed)
    assert page.publisher == "FastPeopleSearch"
    assert page.url.endswith("_id_G123")
    assert page.phone_match is True
    preds = {(i["predicate"], i["value"]) for i in page.items}
    assert ("age", "26") in preds
    assert ("dob", "2000-07") in preds
    assert any(p == "address" and "Main Street" in v for p, v in preds)
    assert any(p == "address" and "Commerce Street" in v for p, v in preds)
    assert ("email", "jane.neighbor@example.net") in preds
    assert ("associate", "Jane Neighbor") in preds
    assert ("phone", "(512) 555-0199") in preds
    past = next(i for i in page.items if i["predicate"] == "address" and "Commerce" in i["value"])
    assert past["extra"].get("past") is True


FPS_LISTING = """
<html><head><title>Who Owns The Phone Number (202)555-0100</title></head>
<body>
1 FREE public record found. The current owner of the phone number 202-555-0100 is
<a href="/ada-example-public_id_G999">Ada Example Public</a>
Age 26
Current Location: Austin, TX
Past Addresses: Austin, TX Dallas, TX
Relatives:
<a href="/jane-neighbor_id_G111">Jane Neighbor</a>
<a href="/ada-example-public_id_G999">VIEW FREE DETAILS</a>
</body></html>
"""

FPS_DETAIL = """
<html><head>
<title>Ada Example Public Age 26 • Austin, TX</title>
<link rel="canonical" href="https://www.fastpeoplesearch.com/ada-example-public_id_G999">
<script type="application/ld+json">
{"@type":"Person","name":"Ada Example Public","birthDate":"2000-07",
 "additionalName":["Ada E Public"],
 "jobTitle":"Retail associate",
 "worksFor":{"@type":"Organization","name":"Example Mart"},
 "homeLocation":{"@type":"Place","address":{"@type":"PostalAddress",
   "streetAddress":"123 Main Street","addressLocality":"Austin","addressRegion":"TX","postalCode":"78701"}},
 "telephone":["(202) 555-0100","(512) 555-0199"],
 "relatedTo":[{"@type":"Person","name":"Jane Neighbor"},{"@type":"Person","name":"Ada Example Public"}]}
</script>
<script type="application/ld+json">
{"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What is the email address for Ada Example Public?",
  "acceptedAnswer":{"@type":"Answer","text":"jane.neighbor@example.net"}}]}
</script>
</head>
<body>
<h1 id="details-header">Ada Example Public in Austin, TX</h1>
<h2 id="age-header">Age 26</h2>
<div id="current_address_section"><a href="/address/123-main-street-austin-tx">123 Main Street, Austin, TX 78701</a></div>
Possible Job / Occupation: Retail associate at Example Mart
</body></html>
"""


def test_listing_extracts_relatives_and_detail_url():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    page = parse_people_index_html(FPS_LISTING, seed, "https://www.fastpeoplesearch.com/202-555-0100")
    preds = {(i["predicate"], i["value"]) for i in page.items}
    assert ("age", "26") in preds
    assert ("associate", "Jane Neighbor") in preds
    details = [i for i in page.items if i["predicate"] == "people_index"]
    assert details
    assert any("_id_G999" in (i["extra"].get("profile_url") or i["value"]) for i in details)
    from viha.core.people_html import detail_profile_urls

    urls = detail_profile_urls(FPS_LISTING, seed, "https://www.fastpeoplesearch.com/202-555-0100")
    assert any("_id_G999" in u for u in urls)
    assert not any("_id_G111" in u for u in urls)


def test_detail_jsonld_job_relatives_email_address():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100", email="ada@example.com")
    page = parse_people_index_html(FPS_DETAIL, seed)
    preds = {i["predicate"]: i["value"] for i in page.items}
    assert preds.get("age") == "26"
    assert preds.get("job") == "Retail associate"
    assert preds.get("org") == "Example Mart"
    assert any(i["predicate"] == "associate" and i["value"] == "Jane Neighbor" for i in page.items)
    assert not any(i["predicate"] == "associate" and "Ada Example" in i["value"] for i in page.items)
    assert any("Main Street" in i["value"] for i in page.items if i["predicate"] == "address")
    assert any(i["predicate"] == "email" and "jane.neighbor" in i["value"] for i in page.items)


def test_facts_from_people_html_are_hits():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    facts = facts_from_people_html(FPS_HTML, seed, imported=True)
    assert facts
    assert any(f.predicate == "age" and f.value == "26" for f in facts)
    assert all(f.extra.get("imported") for f in facts if f.predicate == "age")


def test_title_can_supply_name_when_seed_blank():
    page = parse_people_index_html(FPS_HTML, Seed(phone="202 555 0100"))
    assert any(i["predicate"] == "age" for i in page.items)
