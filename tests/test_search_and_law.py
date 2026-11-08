import pytest

from patent_law_mcp.tools.law_lookup import article_code, get_law_article, search_laws
from patent_law_mcp.tools.patent_search import search_patents
from conftest import fixture_bytes, fixture_text


def test_search_requires_key():
    r = search_patents("떡")
    assert r["found"] is False and "KIPRIS_API_KEY" in r["error"]


def test_word_search(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "k")
    fake_http.routes["getWordSearch"] = (200, fixture_bytes("kipris_search.xml"))
    r = search_patents("떡", page_size=20)
    assert r["total_count"] == 2 and r["search_mode"].startswith("키워드")
    first = r["results"][0]
    assert first["application_number"] == "10-2011-0012345"
    assert first["register_number"] == "10-1234567"
    assert first["applicant"] == "대한민국(농촌진흥청장)"
    assert r["results"][1]["register_number"] == ""
    assert fake_http.calls[0][1]["word"] == "떡" and fake_http.calls[0][1]["utility"] == "false"


def test_applicant_search_uses_advanced(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "k")
    fake_http.routes["getAdvancedSearch"] = (200, fixture_bytes("kipris_search.xml"))
    search_patents("떡", applicant="농촌진흥청")
    params = fake_http.calls[0][1]
    assert params["inventionTitle"] == "떡" and params["applicant"] == "농촌진흥청"


def test_search_surfaces_kipris_error(fake_http, monkeypatch):
    monkeypatch.setenv("KIPRIS_API_KEY", "bad")
    fake_http.routes["getWordSearch"] = (200, b"<response><header><successYN>N</successYN><resultCode>30</resultCode>"
                                              b"<resultMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</resultMsg></header></response>")
    r = search_patents("떡")
    assert r["found"] is False and "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in r["error"]


@pytest.mark.parametrize("given,code", [("제100조", "010000"), ("15의2", "001502"), ("제 88 조", "008800"), ("88", "008800")])
def test_article_code(given, code):
    assert article_code(given) == code


def test_law_requires_oc():
    assert "LAW_OC" in get_law_article("특허법", "100")["error"]


def test_get_law_article_picks_exact_law_and_formats(fake_http, monkeypatch):
    monkeypatch.setenv("LAW_OC", "me")
    fake_http.routes["lawSearch.do"] = (200, fixture_text("law_search.json"))
    fake_http.routes["lawService.do"] = (200, fixture_text("law_article.json"))
    r = get_law_article("특허법", "제100조")
    assert r["found"] and r["law_name"] == "특허법" and r["article_title"] == "전용실시권"
    assert "① 특허권자는" in r["text"] and "  2. 상속이나" in r["text"]
    assert "제6장" not in r["text"]
    service_params = fake_http.calls[1][1]
    assert service_params["MST"] == "222" and service_params["JO"] == "010000" and service_params["OC"] == "me"
    assert r["link"] == "https://www.law.go.kr/DRF/lawService.do?MST=222"


def test_law_api_error_message(fake_http, monkeypatch):
    monkeypatch.setenv("LAW_OC", "me")
    fake_http.routes["lawSearch.do"] = (200, '{"result": "사용자 정보 검증에 실패하였습니다.", "msg": "IP를 등록해 주세요."}')
    r = search_laws("특허법")
    assert r["found"] is False and "검증에 실패" in r["error"]


def test_http_client_logs_do_not_expose_query_keys():
    import logging

    from patent_law_mcp import net  # noqa: F401  (import 시 로거 수준 설정)

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
