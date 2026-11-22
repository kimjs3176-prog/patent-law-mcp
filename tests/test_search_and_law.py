import pytest

from patent_law_mcp.tools.law_lookup import article_code, get_law_article, search_laws
from patent_law_mcp.tools.patent_search import search_patents
from conftest import fixture_bytes, fixture_text


GOOGLE_JSON = """{"results": {"total_num_results": 2, "cluster": [{"result": [
  {"patent": {"title": "굳지 않는 <b>떡</b>의 제조방법", "assignee": "대한민국(농촌진흥청장)",
              "publication_number": "KR101070281B1", "filing_date": "2010-06-30", "grant_date": "2011-09-28",
              "priority_date": "2010-06-30", "publication_date": "2011-10-06", "snippet": "전분의 &quot;노화&quot;를 늦추는"}},
  {"patent": {"title": "떡 성형 장치", "assignee": "주식회사 예시", "publication_number": "KR20100060603A",
              "filing_date": "2008-11-28", "publication_date": "2010-06-07"}},
  {"patent": {"title": "Rice cake", "publication_number": "US1234567B2"}}
]}]}}"""


def test_search_without_key_falls_back_to_google(fake_http):
    fake_http.routes["patents.google.com/xhr/query"] = (200, GOOGLE_JSON)
    r = search_patents("떡", applicant="농촌진흥청", page_size=10)
    assert r["found"] is True and r["source"].startswith("Google Patents")
    first, second = r["results"]  # 한국 문헌만
    assert first["title"] == "굳지 않는 떡의 제조방법" and first["register_number"] == "10-1070281"
    assert first["snippet"] == '전분의 "노화"를 늦추는'
    assert second["open_number"] == "10-2010-0060603" and second["register_number"] == ""
    url_param = fake_http.calls[0][1]["url"]
    assert "country=KR" in url_param and "assignee=" in url_param and "after=" not in url_param
    only_2010 = search_patents("떡", year=2010, refresh=True)
    assert [x["publication_number"] for x in only_2010["results"]] == ["KR101070281B1"]


def test_search_without_key_reports_google_block_without_inventing(fake_http):
    fake_http.routes["patents.google.com/xhr/query"] = (503, "<html>Sorry...</html>")
    r = search_patents("떡")
    assert r["found"] is False and "results" not in r
    assert "503" in r["error"] and "x-api-key" in r["how_to"] and "KIPRIS_API_KEY" in r["how_to"]


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


def _google_page(start, n=10):
    rows = ",".join(
        '{"patent": {"title": "특허 %d", "publication_number": "KR10%07dB1", "filing_date": "%d-01-01"}}' % (i, 1000000 + i, 2010 if i % 2 else 2011)
        for i in range(start, start + n)
    )
    return '{"results": {"total_num_results": 100, "cluster": [{"result": [%s]}]}}' % rows


def test_google_paging_has_no_gaps_with_small_page_size(fake_http, monkeypatch):
    # 리뷰 1: page_size가 10보다 작아도 쪽을 넘길 때 빠지는 결과가 없어야 한다
    pages = {}

    def handler(url, **kw):
        import httpx
        page = int(kw["params"]["url"].split("page=")[1].split("&")[0])
        pages[page] = pages.get(page, 0) + 1
        return httpx.Response(200, text=_google_page(page * 10), request=httpx.Request("GET", url))

    from patent_law_mcp import net
    monkeypatch.setattr(net, "http_get", handler)
    titles = []
    for p in (1, 2, 3):
        titles += [x["title"] for x in search_patents("떡", page=p, page_size=4)["results"]]
    assert titles == [f"특허 {i}" for i in range(12)]  # 0..11 연속, 빠짐·중복 없음
    assert set(pages) == {0, 1}  # 3쪽(8~11)은 Google 0·1쪽에 걸쳐 받음


def test_google_refresh_bypasses_cache(fake_http, monkeypatch, tmp_path):
    # 리뷰 2: refresh=True면 Google 결과도 캐시를 무시한다
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", str(tmp_path / "c.sqlite3"))
    fake_http.routes["patents.google.com/xhr/query"] = (200, GOOGLE_JSON)
    search_patents("떡")
    search_patents("떡")
    assert len(fake_http.calls) == 1
    search_patents("떡", refresh=True)
    assert len(fake_http.calls) == 2


def test_google_year_filter_is_honest(fake_http):
    # 리뷰 3: 연도 거름은 받은 쪽 안에서만 — 전체 건수를 그대로 내지 않고 다른 쪽에 더 있을 수 있다고 알린다
    fake_http.routes["patents.google.com/xhr/query"] = (200, GOOGLE_JSON)
    r = search_patents("떡", year=2010)
    assert r["total_count"] is None and "다른 쪽" in r["year_filter_note"]


def test_kipris_failure_falls_back_to_google(fake_http, monkeypatch):
    # 리뷰 4: 본인 키 한도 초과 등으로 KIPRIS가 거부해도 Google로 대신 검색한다
    monkeypatch.setenv("KIPRIS_API_KEY", "quota-exceeded")
    fake_http.routes["getWordSearch"] = (200, "<response><header><resultCode>22</resultCode><resultMsg>LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS</resultMsg></header></response>")
    fake_http.routes["patents.google.com/xhr/query"] = (200, GOOGLE_JSON)
    r = search_patents("떡")
    assert r["found"] is True and "KIPRIS 실패로 대체" in r["source"] and "EXCEEDS" in r["kipris_error"]
