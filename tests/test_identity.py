from datetime import date

from viha.core.identity import (
    age_from_dob,
    corroborate_identity,
    extract_associates_from_text,
    extract_identity_from_text,
    fields_from_github_user,
    ingest_mention_facts,
    likely_criminal,
    normalize_dob,
    parse_wikidata_time,
    persona_brief,
)
from viha.core.models import Case, Fact, Seed, Source


def _fact(
    pred: str,
    value: str,
    publisher: str,
    candidate: bool = True,
    section: str = "identity",
    url: str = "",
) -> Fact:
    return Fact(
        predicate=pred,
        value=value,
        section=section,
        confidence=0.5,
        source=Source(publisher=publisher, url=url or f"https://example.com/{publisher}"),
        candidate=candidate,
    )


def test_extract_age_bullet_and_born_month_year():
    seed = Seed(full_name="Ada Example Public")
    items = extract_identity_from_text("Ada Example Public Age 26 • Austin, TX Born July 2000", seed)
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["age"] == "26"
    assert preds["location"] == "Austin, TX"
    assert preds["dob"] == "2000-07"


def test_extract_intelius_owner_age_title():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    title = "(202) 555-0100 Phone number Owner Ada E Public, Age 25 in San ..."
    items = extract_identity_from_text(title, seed)
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["aka"] == "Ada E Public"
    assert preds["age"] == "25"
    assert "location" not in preds


def test_extract_skips_other_first_name():
    seed = Seed(full_name="Ada Example Public")
    assert extract_identity_from_text("Owner Ida Public, Age 24 in Dallas, TX", seed) == []


def test_extract_owner_age_and_city():
    seed = Seed(full_name="Ada Example Public")
    items = extract_identity_from_text("Owner Ada E Public, Age 25 in San Antonio, TX", seed)
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["age"] == "25"
    assert preds["location"] == "San Antonio, TX"
    assert preds["aka"] == "Ada E Public"


def test_extract_skips_truncated_city():
    seed = Seed(full_name="Ada Example Public")
    items = extract_identity_from_text("Owner Ada E Public, Age 25 in San ...", seed)
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["age"] == "25"
    assert "location" not in preds


def test_extract_dob_and_street():
    seed = Seed(full_name="Ada Example Public")
    items = extract_identity_from_text(
        "Ada Example Public born January 15, 1990 lives at 123 Main Street, Austin, TX",
        seed,
    )
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["dob"] == "1990-01-15"
    assert preds["age"] == age_from_dob("1990-01-15")
    assert "123 Main Street" in preds["address"]


def test_extract_requires_name_tokens():
    seed = Seed(full_name="Ada Example Public")
    assert extract_identity_from_text("Owner Someone Else, Age 40 in Dallas, TX", seed) == []


def test_dob_helpers():
    assert normalize_dob("01/15/1990") == "1990-01-15"
    assert parse_wikidata_time("+1990-01-15T00:00:00Z") == "1990-01-15"
    assert parse_wikidata_time("+1990-00-00T00:00:00Z") == "1990"
    assert age_from_dob("1990-01-15", today=date(2026, 8, 30)) == "36"


def test_likely_criminal():
    assert likely_criminal("United States v. Public")
    assert not likely_criminal("Public v. City of Austin — zoning")


def test_github_profile_fields():
    fields = fields_from_github_user(
        {"location": "San Antonio, TX", "name": "Ada Public", "company": "@Example"}
    )
    preds = {f["predicate"]: f["value"] for f in fields}
    assert preds["location"] == "San Antonio, TX"
    assert preds["aka"] == "Ada Public"
    assert preds["org"] == "Example"


def test_corroborate_location_and_keep_single_address_candidate():
    case = Case(seed=Seed(full_name="Ada Example Public"))
    case.add_fact(_fact("location", "San Antonio, TX", "GitHub"))
    case.add_fact(_fact("location", "San Antonio, TX", "FEC"))
    case.add_fact(_fact("address", "123 Main St", "Indexed people search"))
    corroborate_identity(case)
    locs = [f for f in case.facts if f.predicate == "location"]
    assert all(not f.candidate for f in locs)
    addr = next(f for f in case.facts if f.predicate == "address")
    assert addr.candidate is True


def test_corroborate_keeps_broker_only_age_candidate():
    case = Case(seed=Seed(full_name="Ada Example Public"))
    case.add_fact(_fact("age", "26", "Indexed people search"))
    case.add_fact(_fact("age", "26", "FastPeopleSearch"))
    corroborate_identity(case)
    ages = [f for f in case.facts if f.predicate == "age"]
    assert all(f.candidate for f in ages)


def test_persona_brief_prefers_confirmed():
    case = Case(seed=Seed(full_name="Ada Example Public"))
    case.add_fact(_fact("age", "25", "Indexed people search", candidate=True))
    case.add_fact(_fact("age", "36", "Wikidata", candidate=False))
    case.add_fact(_fact("docket", "USA v. Public", "CourtListener", section="legal"))
    brief = persona_brief(case)
    assert brief["age"].value == "36"
    assert brief["charges"]
    assert "Age 36" in brief["summary"]
    assert "Age 36 · candidate" not in brief["summary"]


def test_persona_brief_shows_candidate_age_and_places():
    case = Case(seed=Seed(full_name="Ada Example Public"))
    case.add_fact(_fact("age", "26", "Indexed people search"))
    case.add_fact(_fact("dob", "2000-07", "FastPeopleSearch"))
    case.add_fact(_fact("location", "Austin, TX", "Indexed people search"))
    case.add_fact(_fact("address", "123 Main Street, Austin, TX", "Indexed people search"))
    brief = persona_brief(case)
    assert brief["age"].value == "26"
    assert brief["dob"].value == "2000-07"
    places = [f.value for f in brief["locations"]]
    assert any("Austin" in p for p in places)
    assert any("Main Street" in p for p in places)
    assert any("Main Street" in f.value for f in brief["property"])
    assert "26" in brief["summary"]


def test_extract_associates_keeps_relative_email():
    seed = Seed(full_name="Ada Example Public", email="ada@example.com", phone="202 555 0100")
    items = extract_associates_from_text(
        "Ada Example Public Related To: Jane Neighbor, Ada Example Public "
        "email jane.neighbor@example.net also (512) 555-0199",
        seed,
    )
    preds = {(i["predicate"], i["value"]) for i in items}
    assert ("email", "jane.neighbor@example.net") in preds
    assert ("phone", "(512) 555-0199") in preds
    assert ("associate", "Jane Neighbor") in preds
    assert not any(v == "ada@example.com" for _, v in preds)


def test_extract_phone_in_url_without_name_in_title():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    blob = "Age 26 • Austin, TX Born July 2000 https://www.fastpeoplesearch.com/202-555-0100"
    preds = {i["predicate"]: i["value"] for i in extract_identity_from_text(blob, seed)}
    assert preds["age"] == "26"
    assert preds["location"] == "Austin, TX"
    assert preds["dob"] == "2000-07"


def test_extract_job_and_current_location():
    seed = Seed(full_name="Ada Example Public")
    blob = "Ada Example Public Current Location: Austin, TX Possible Job / Occupation: Retail associate"
    preds = {i["predicate"]: i["value"] for i in extract_identity_from_text(blob, seed)}
    assert preds["location"] == "Austin, TX"
    assert preds["job"] == "Retail associate"


def test_extract_three_token_name_matches_first_last():
    seed = Seed(full_name="Ada Micheal Public")
    items = extract_identity_from_text("Owner Ada M Public, Age 25 in Austin, TX", seed)
    preds = {i["predicate"]: i["value"] for i in items}
    assert preds["age"] == "25"
    assert preds["location"] == "Austin, TX"


def test_ingest_mentions_fills_brief_from_web_title():
    seed = Seed(full_name="Ada Example Public", phone="202 555 0100")
    case = Case(seed=seed)
    case.add_fact(
        Fact(
            predicate="web_mention",
            value="Owner Ada E Public, Age 25 in Austin, TX Related To: Jane Neighbor",
            section="web",
            confidence=0.4,
            source=Source(
                publisher="Bing",
                url="https://www.intelius.com/reverse-phone-lookup/202-555-0100",
            ),
            extra={"snippet": "Ada E Public is 25 years old. Possible Job / Occupation: Retail associate"},
            candidate=True,
        )
    )
    assert ingest_mention_facts(case) >= 1
    brief = persona_brief(case)
    assert brief["age"].value == "25"
    assert any("Austin" in f.value for f in brief["locations"])
    assert brief["job"].value == "Retail associate"
    assert any(f.value == "Jane Neighbor" for f in brief["relatives"])
