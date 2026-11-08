import pytest

from patent_law_mcp.tools.analysis import summarize_patent
from patent_law_mcp.tools.claim_utils import detect_technology_type, is_dependent_claim, split_claim_elements
from patent_law_mcp.tools.claims_practice import verify_tech_transfer_scope_match
from patent_law_mcp.tools.foreign_patents import parse_foreign_number
from patent_law_mcp.tools.kipris_connector import fetch_patent_smart
from conftest import fixture_text


@pytest.mark.parametrize(
    "given,cc,digits,kinds",
    [
        ("US10000000B2", "US", "10000000", ("B2",)),
        ("US 10,000,000", "US", "10000000", ("B2", "B1")),
        ("US 2020/0123456", "US", "20200123456", ("A1",)),
        ("EP 1 000 000", "EP", "1000000", ("B1", "A1", "A2")),
        ("WO 2020/123456", "WO", "2020123456", ("A1", "A2", "A3")),
        ("JP2020123456A", "JP", "2020123456", ("A",)),
    ],
)
def test_parse_foreign(given, cc, digits, kinds):
    n = parse_foreign_number(given)
    assert (n.country, n.digits, n.kinds) == (cc, digits, kinds)


@pytest.mark.parametrize("bad", ["PCT/KR2020/012345", "JP2020123456", "US 123", "XX1234567B1"])
def test_parse_foreign_rejects(bad):
    with pytest.raises(ValueError):
        parse_foreign_number(bad)


def test_us_fetch_tries_kinds_and_verifies(fake_http):
    fake_http.routes["US10000000B2"] = (404, "")
    fake_http.routes["US10000000B1"] = (200, fixture_text("google_us.html"))
    r = fetch_patent_smart("US 10,000,000")
    assert r["found"] and r["country"] == "US" and r["publication_number"] == "US10000000B1"
    assert r["applicant"] == "Acme Corp" and len(r["claims"]) == 2
    assert r["claims"][0].startswith("A fruit sorting apparatus")  # 번호 없는 div.claim으로 감싼 독립항도 읽음
    assert [u for u, _ in fake_http.calls] == [
        "https://patents.google.com/patent/US10000000B2/en",
        "https://patents.google.com/patent/US10000000B1/en",
    ]


def test_foreign_mismatch_is_discarded(fake_http):
    fake_http.routes["US10000001B2"] = (200, fixture_text("google_us.html"))
    fake_http.routes["US10000001B1"] = (404, "")
    r = fetch_patent_smart("US10000001")
    assert r["found"] is False and "요청과 달라" in r["attempts"][0]["result"]


def test_english_claims():
    claim = "1. A fruit sorting apparatus, comprising: a conveyor; a near-infrared light source; and a spectral sensor."
    elements, subject = split_claim_elements(claim)
    assert subject == "fruit sorting apparatus"
    assert elements == ["a conveyor", "a near-infrared light source", "a spectral sensor"]
    assert is_dependent_claim("2. The apparatus of claim 1, wherein X.")
    assert detect_technology_type("Fruit sorting apparatus and method").startswith("물건·방법 복합")


def test_english_scope_negation():
    claim = "A sorting apparatus comprising: a conveyor belt; a light source; and a spectral sensor."
    r = verify_tech_transfer_scope_match(claim, "A manual packing table without a conveyor belt. It has a light source and a spectral sensor.")
    assert r["matched_elements"] == "2/3"
    assert "conveyor" in r["verified_elements"][0]["negated_keywords"]


def test_english_summary_effect():
    r = summarize_patent("US1", "Fruit sorting apparatus", "An apparatus sorts fruit. The apparatus reduces sorting time.",
                         ["A fruit sorting apparatus, comprising: a conveyor; and a sensor."])
    assert r["primary_effect"]["text"] == "The apparatus reduces sorting time."
    assert r["claimed_subject_matter"] == "fruit sorting apparatus"
