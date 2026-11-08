import pytest

from patent_law_mcp.tools.kipris_connector import (
    fetch_patent_smart,
    inspect_and_summarize_by_appno,
    parse_kr_patent_number,
)
from conftest import fixture_bytes, fixture_text


@pytest.mark.parametrize(
    "identifier,kind,display,google_id",
    [
        ("10-1070281", "registration", "10-1070281", "KR101070281B1"),
        ("1070281", "registration", "10-1070281", "KR101070281B1"),
        ("2070281", "registration", "10-2070281", "KR102070281B1"),
        ("제10-1070281호", "registration", "10-1070281", "KR101070281B1"),
        ("KR101070281B1", "registration", "10-1070281", "KR101070281B1"),
        ("10-2010-0062402", "application", "10-2010-0062402", None),
        ("KR20100062402A", "publication", "10-2010-0062402", "KR20100062402A"),
    ],
)
def test_number_parsing(identifier, kind, display, google_id):
    num = parse_kr_patent_number(identifier)
    assert (num.kind, num.display, num.google_id) == (kind, display, google_id)


def test_application_number_is_never_converted_to_publication_id():
    # 이전 버전은 출원번호 10-2010-0062402를 KR20100062402A(무관한 세메스 특허)로 바꿔 조회했다
    assert parse_kr_patent_number("10-2010-0062402").google_id is None
    pub = parse_kr_patent_number("10-2010-0062402", "publication")
    assert pub.google_id == "KR20100062402A"


@pytest.mark.parametrize("bad", ["12345", "20-1234567", "10-1800-0000001", "10-2010-006240"])
def test_invalid_numbers_raise(bad):
    with pytest.raises(ValueError):
        parse_kr_patent_number(bad)


def test_registration_lookup_verified(fake_http):
    fake_http.routes["KR101070281B1"] = (200, fixture_text("google_registration.html"))
    r = fetch_patent_smart("10-1070281")
    assert r["found"] is True
    assert r["register_number"] == "10-1070281"
    assert r["application_number"] == "10-2008-0119257"
    assert r["applicant"] == "주식회사 포스코건설"
    assert len(r["claims"]) == 2 and r["claims"][1].startswith("제1항")
    assert r["cpc_codes"] == ["C02F11/13"]
    assert "공식 법적 상태 아님" in r["register_status"]


def test_mismatched_document_is_discarded(fake_http):
    # 요청은 10-1234567인데 다른 등록번호 문서가 오면 버린다
    fake_http.routes["KR101234567B1"] = (200, fixture_text("google_registration.html"))
    r = fetch_patent_smart("10-1234567")
    assert r["found"] is False
    assert "달라 결과를 버렸습니다" in r["attempts"][0]["result"]


def test_network_failure_never_returns_sample_or_fabricated_data(fake_http):
    r = fetch_patent_smart("10-9999999")  # 응답 경로 없음 -> 접속 실패
    assert r["found"] is False
    assert "title" not in r and "claims" not in r


def test_rate_limit_retries_once_then_reports(fake_http):
    fake_http.routes["KR109999999B1"] = (503, "Sorry")
    r = fetch_patent_smart("10-9999999")
    assert r["found"] is False
    assert len(fake_http.calls) == 2
    assert "HTTP 503" in r["attempts"][0]["result"]


def test_application_number_without_key_reports_instead_of_guessing(fake_http):
    r = fetch_patent_smart("10-2010-0062402")
    assert r["found"] is False
    assert fake_http.calls == []
    assert any("publication" in s for s in r["next_steps"])


def test_publication_lookup(fake_http):
    fake_http.routes["KR20100062402A"] = (200, fixture_text("google_publication.html"))
    r = fetch_patent_smart("10-2010-0062402", "publication")
    assert r["found"] is True
    assert r["publication_number"] == "10-2010-0062402"
    assert r["application_number"] == "10-2008-0121036"


def test_kipris_application_lookup(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "dummy-key")
    fake_http.routes["kipris.or.kr"] = (200, fixture_bytes("kipris_ok.xml"))
    r = fetch_patent_smart("10-2008-0119257")
    assert r["found"] is True
    assert r["source"] == "KIPRIS Plus 공식 Open API"
    assert r["applicant"] == "주식회사 포스코건설"
    assert r["ipc_code"] == "C02F 11/12"
    assert r["register_number"] == "10-1070281"
    assert r["abstract"].startswith("유기성 슬러지")
    assert len(r["claims"]) == 2
    assert fake_http.calls[0][1]["applicationNumber"] == "1020080119257"


def test_kipris_error_message_is_surfaced_without_key(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "secret-value")
    fake_http.routes["kipris.or.kr"] = (200, fixture_bytes("kipris_error.xml"))
    r = fetch_patent_smart("10-2008-0119257")
    assert r["found"] is False
    assert "SERVICE KEY IS NOT REGISTERED" in r["attempts"][0]["result"]
    assert "secret-value" not in str(r)


def test_kipris_other_application_is_discarded(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "dummy-key")
    fake_http.routes["kipris.or.kr"] = (200, fixture_bytes("kipris_ok.xml"))
    r = fetch_patent_smart("10-2011-0000001")
    assert r["found"] is False


def test_inspect_does_not_summarize_unfound_patent(fake_http):
    r = inspect_and_summarize_by_appno("10-9999999")
    assert r["found"] is False and "summary" not in r


def test_inspect_summarizes_verified_patent(fake_http):
    fake_http.routes["KR101070281B1"] = (200, fixture_text("google_registration.html"))
    r = inspect_and_summarize_by_appno("10-1070281")
    assert r["summary"]["title"] == "유기성 슬러지의 고정상식 건조장치"
    assert r["commercialization_trl"]["estimated_trl"] is None
