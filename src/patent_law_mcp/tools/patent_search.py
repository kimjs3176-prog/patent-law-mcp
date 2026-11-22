"""한국 특허 검색 — KIPRIS Plus 공식 API(인증키), 키가 없으면 Google Patents 검색

검색 결과를 가공·재정렬하지 않고 출처가 준 순서와 값 그대로 돌려줍니다.
- KIPRIS 키워드 검색: getWordSearch (word, year, patent, utility)
- KIPRIS 출원인 지정 검색: getAdvancedSearch (inventionTitle, applicant)
- 인증키가 없을 때: Google Patents 공개 검색(비공식, 한국 문헌만). 접속이 막히면 결과를 만들지 않고 이유와 대안을 돌려줌
"""

import html as _html
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Annotated, Any, Dict, List, Optional

import httpx
from pydantic import Field

from patent_law_mcp import cache, net
from patent_law_mcp.config import settings
from patent_law_mcp.tools.kipris_connector import _digits, _format_app, _format_reg, _text

KIPRIS_SEARCH_BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"
GOOGLE_QUERY_URL = "https://patents.google.com/xhr/query"
NO_KEY_HELP = (
    "kipris.or.kr에서 검색해 찾은 등록·공개번호로 fetch_patent_smart를 쓰거나 공보 원문을 analyze_patent_document에 붙여 넣을 수 있습니다. "
    "본인 KIPRIS Plus 인증키가 있으면 원격 커넥터의 요청 헤더 x-api-key에, 로컬 실행이면 환경변수 KIPRIS_API_KEY에 넣으십시오."
)

_FIELDS = {
    "inventionTitle": "title",
    "applicantName": "applicant",
    "registerStatus": "register_status",
    "applicationDate": "application_date",
    "openDate": "open_date",
    "publicationDate": "publication_date",
    "registerDate": "register_date",
    "ipcNumber": "ipc",
    "astrtCont": "abstract",
}


def _parse_items(raw: bytes) -> Dict[str, Any]:
    root = ET.fromstring(raw)
    if _text(root, ".//successYN") == "N" or root.find(".//items") is None and root.find(".//item") is None:
        msg = _text(root, ".//resultMsg") or "검색 결과 형식을 해석하지 못했습니다."
        raise LookupError(f"{msg} (resultCode {_text(root, './/resultCode') or '?'})")
    items = []
    for item in root.findall(".//item"):
        row: Dict[str, Any] = {v: _text(item, k) for k, v in _FIELDS.items()}
        app = _digits(_text(item, "applicationNumber"))
        reg = _digits(_text(item, "registerNumber"))
        opn = _digits(_text(item, "openNumber"))
        row["application_number"] = _format_app(app) if app else ""
        row["register_number"] = _format_reg(reg) if reg else ""
        row["open_number"] = _format_app(opn) if len(opn) >= 13 else ""
        items.append(row)
    total = _text(root, ".//totalCount")
    return {"total_count": int(total) if total.isdigit() else None, "items": items}


def _clean(value: Any) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def _google_numbers(pub: str) -> Dict[str, str]:
    """Google 문헌번호 → 한국 번호.

    등록: KR101070281B1(10 + 7자리) → 10-1070281, 실용 등록 KR200xxxxxxY1 → 20-xxxxxxx
    공개: KR20100060603A(연도 4 + 7자리) → 10-2010-0060603, 실용 공개 …U → 20-…
    """
    m = re.fullmatch(r"KR(\d+)([A-Z]\d?)", pub or "")
    if not m:
        return {"register_number": "", "open_number": ""}
    digits, kind = m.groups()
    if kind.startswith(("B", "Y")) and len(digits) == 9 and digits[:2] in ("10", "20"):
        return {"register_number": f"{digits[:2]}-{digits[2:]}", "open_number": ""}
    if kind.startswith(("A", "U")) and len(digits) == 11:
        return {"register_number": "", "open_number": f"{'10' if kind.startswith('A') else '20'}-{digits[:4]}-{digits[4:]}"}
    return {"register_number": "", "open_number": ""}


def _parse_google(payload: Dict[str, Any]) -> Dict[str, Any]:
    res = payload.get("results") or {}
    items: List[Dict[str, Any]] = []
    for cluster in res.get("cluster") or []:
        for entry in cluster.get("result") or []:
            pat = entry.get("patent") or {}
            pub = _clean(pat.get("publication_number"))
            if not pub.startswith("KR"):
                continue
            items.append({
                "title": _clean(pat.get("title")),
                "applicant": _clean(pat.get("assignee")),
                "publication_number": pub,
                **_google_numbers(pub),
                "priority_date": _clean(pat.get("priority_date")),
                "filing_date": _clean(pat.get("filing_date")),
                "publication_date": _clean(pat.get("publication_date")),
                "grant_date": _clean(pat.get("grant_date")),
                "snippet": _clean(pat.get("snippet"))[:300],
            })
    total = res.get("total_num_results")
    return {"total_count": total if isinstance(total, int) else None, "items": items}


GOOGLE_PAGE = 10  # Google Patents 기본 쪽 크기. page_size가 이보다 작으면 이 단위로 받아 잘라 쓴다


def _google_fetch_page(q: Dict[str, str]) -> Dict[str, Any]:
    """Google Patents 한 쪽을 받아 해석한다. 실패하면 {'error': ...}."""
    url_param = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in q.items())
    resp = None
    for attempt in range(2):  # 429·503(일시 제한)은 잠시 뒤 한 번만 다시 시도
        try:
            resp = net.http_get(GOOGLE_QUERY_URL, params={"url": url_param, "exp": ""}, timeout=settings.request_timeout_seconds)
        except httpx.HTTPError as e:
            return {"error": f"Google Patents 접속 실패 ({type(e).__name__})"}
        if resp.status_code not in (429, 503) or attempt == 1:
            break
        time.sleep(1.5)
    if resp.status_code != 200:
        return {"error": f"Google Patents 검색이 거부됐습니다 (HTTP {resp.status_code}; 429·503은 자동 접속 제한)"}
    try:
        return _parse_google(json.loads(resp.text))
    except (ValueError, AttributeError, TypeError):
        return {"error": "Google Patents 검색 응답을 해석하지 못했습니다 (화면 구조 변경 가능)."}


def search_google_patents(
    query: str, applicant: Optional[str], year: int, page: int, page_size: int, refresh: bool = False
) -> Dict[str, Any]:
    """Google Patents 공개 검색 (한국 문헌). 공식 API가 아니며 접속 제한이 걸리면 found=False."""
    base = {"q": query, "country": "KR"}
    if applicant:
        base["assignee"] = applicant
    # 날짜 조건(after/before)은 Google 쪽에서 오류가 나 보내지 않고, 받은 결과에서 출원일 연도로 거른다
    cache_key = "google:" + "&".join(f"{k}={v}" for k, v in sorted(base.items())) + f":year={year}:page={page}:size={page_size}"
    if not refresh and (hit := cache.get("search", cache_key, ttl_hours=24)):
        return hit

    # 요청한 쪽(page, page_size)이 Google 쪽 경계와 어긋나도 빠짐·중복 없이 잘라 쓴다
    g_size = page_size if page_size >= GOOGLE_PAGE else GOOGLE_PAGE
    start = (page - 1) * page_size
    first_page, offset = divmod(start, g_size)
    pages_needed = 2 if offset + page_size > g_size else 1
    items: List[Dict[str, Any]] = []
    total = None
    for n in range(pages_needed):
        got = _google_fetch_page({**base, "num": str(min(g_size, 100)), "page": str(first_page + n)})
        if "error" in got:
            if n == 0:
                return {"found": False, "error": got["error"]}
            break  # 둘째 쪽이 막히면 첫 쪽 결과만 쓴다
        total = got["total_count"] if total is None else total
        items += got["items"]
    items = items[offset:offset + page_size]
    if year:
        items = [x for x in items if x["filing_date"].startswith(str(year))]
    result: Dict[str, Any] = {
        "found": bool(items),
        "source": "Google Patents 공개 검색 (비공식, KIPRIS 인증키 없음)",
        "search_mode": "키워드" + (" + 출원인(assignee)" if applicant else "") + (f" + 출원연도 {year} (이 쪽 결과 중 출원일로 거름)" if year else ""),
        "query": query,
        "applicant": applicant,
        "page": page,
        "total_count": None if year else total,
        "results": items,
        "note": (
            "Google Patents가 준 순서·값 그대로입니다. 공식 KIPRIS 결과와 범위·순서가 다를 수 있고 권리 상태는 포함하지 않습니다. "
            "등록·공개번호로 fetch_patent_smart를 호출하면 상세를 번호 검증과 함께 확인할 수 있습니다."
        ),
    }
    if year:
        result["year_filter_note"] = (
            f"출원연도 {year}는 Google 검색 조건이 아니라 이 쪽({page}쪽) 결과 안에서만 거른 것입니다. "
            f"검색 전체 건수(필터 전 {total if total is not None else '미상'}건)의 다른 쪽에 {year}년 출원이 더 있을 수 있으니, "
            "결과가 없거나 적으면 다음 쪽을 보거나 검색어에 연도·출원인을 더하십시오."
        )
    if result["found"]:
        cache.put("search", cache_key, result)
    return result


def search_patents(
    query: Annotated[str, Field(min_length=1, max_length=200)],
    applicant: Optional[str] = None,
    year: Annotated[int, Field(ge=0, le=2100)] = 0,
    include_utility_models: bool = False,
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=100)] = 20,
    refresh: bool = False,
) -> Dict[str, Any]:
    """한국 특허를 검색합니다. KIPRIS Plus 인증키가 있으면 공식 API, 없으면 Google Patents 공개 검색(비공식)을 씁니다.

    Args:
        query: 검색어 (출원인을 지정하면 발명의 명칭에서 검색)
        applicant: 출원인명 (예: "농촌진흥청", "대한민국")
        year: 출원연도 (0 = 전체, 키워드 검색에만 적용)
        include_utility_models: 실용신안 포함 여부
        page: 페이지 번호
        page_size: 페이지당 건수 (최대 100)
        refresh: True면 캐시(24시간)를 무시하고 다시 검색
    """
    key = settings.kipris_api_key
    if not key:
        fallback = search_google_patents(query, applicant, year, page, page_size, refresh)
        if fallback.get("found") or "error" not in fallback:
            return fallback
        return {
            "found": False,
            "error": "KIPRIS Plus 인증키가 없어 Google Patents 검색으로 대신하려 했지만 실패했습니다: " + fallback["error"],
            "how_to": NO_KEY_HELP,
            "get_key": "plus.kipris.or.kr → 데이터 신청 → Open API '특허·실용신안 정보검색' 신청 후 발급된 인증키",
        }

    common = {
        "patent": "true",
        "utility": "true" if include_utility_models else "false",
        "pageNo": page,
        "numOfRows": page_size,
        "ServiceKey": key,
    }
    if applicant:
        op, params, mode = "getAdvancedSearch", {"inventionTitle": query, "applicant": applicant, **common}, "출원인 + 발명의 명칭"
    else:
        op, params, mode = "getWordSearch", {"word": query, "year": year, **common}, "키워드 (전체 항목)"

    cache_key = f"{op}:" + "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "ServiceKey")
    if not refresh and (hit := cache.get("search", cache_key, ttl_hours=24)):
        return hit
    kipris_error = None
    try:
        resp = net.http_get(f"{KIPRIS_SEARCH_BASE}/{op}", params=params, timeout=settings.request_timeout_seconds)
        if resp.status_code != 200:
            kipris_error = f"KIPRIS 응답 오류 (HTTP {resp.status_code})"
        else:
            parsed = _parse_items(resp.content)
    except httpx.HTTPError as e:
        kipris_error = f"KIPRIS 접속 실패 ({type(e).__name__})"
    except ET.ParseError:
        kipris_error = "KIPRIS 응답을 XML로 해석하지 못했습니다."
    except LookupError as e:
        kipris_error = f"KIPRIS: {e}"
    if kipris_error:
        # 인증키 한도 초과·키 오류·장애 때도 검색이 끊기지 않도록 Google Patents로 대신한다
        fallback = search_google_patents(query, applicant, year, page, page_size, refresh)
        if fallback.get("found") or "error" not in fallback:
            return {**fallback, "kipris_error": kipris_error,
                    "source": fallback["source"].replace("KIPRIS 인증키 없음", "KIPRIS 실패로 대체")}
        return {"found": False, "error": f"{kipris_error}. Google Patents 대체 검색도 실패: {fallback['error']}", "how_to": NO_KEY_HELP}

    result = {
        "found": bool(parsed["items"]),
        "source": "KIPRIS Plus 공식 Open API",
        "search_mode": mode,
        "query": query,
        "applicant": applicant,
        "page": page,
        "total_count": parsed["total_count"],
        "results": parsed["items"],
        "note": "KIPRIS가 준 순서·값 그대로입니다. 권리 상태는 조회 시점 기준이며 상세는 fetch_patent_smart로 확인하십시오.",
    }
    if result["found"]:
        cache.put("search", cache_key, result)
    return result
