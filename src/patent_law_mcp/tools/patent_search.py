"""KIPRIS Plus 특허 검색 (공식 API, 인증키 필요)

검색 결과를 가공·재정렬하지 않고 KIPRIS가 준 순서와 값 그대로 돌려줍니다.
- 키워드 검색: getWordSearch (word, year, patent, utility)
- 출원인 지정 검색: getAdvancedSearch (inventionTitle, applicant)
"""

import xml.etree.ElementTree as ET
from typing import Annotated, Any, Dict, List, Optional

import httpx
from pydantic import Field

from patent_law_mcp import cache, net
from patent_law_mcp.config import settings
from patent_law_mcp.tools.kipris_connector import _digits, _format_app, _format_reg, _text

KIPRIS_SEARCH_BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice"

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


def search_patents(
    query: Annotated[str, Field(min_length=1, max_length=200)],
    applicant: Optional[str] = None,
    year: Annotated[int, Field(ge=0, le=2100)] = 0,
    include_utility_models: bool = False,
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=100)] = 20,
    refresh: bool = False,
) -> Dict[str, Any]:
    """KIPRIS Plus 공식 API로 한국 특허를 검색합니다 (환경변수 KIPRIS_API_KEY 필요).

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
        return {
            "found": False,
            "error": "특허 검색에는 KIPRIS Plus 인증키가 필요합니다 (환경변수 KIPRIS_API_KEY).",
            "how_to": "plus.kipris.or.kr에서 '특허·실용 공개·등록공보' 서비스 키를 발급받아 MCP 설정의 env에 넣으십시오. 자세한 절차는 저장소 docs/KIPRIS_API_KEY.md를 참고하십시오.",
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
    try:
        resp = net.http_get(f"{KIPRIS_SEARCH_BASE}/{op}", params=params, timeout=settings.request_timeout_seconds)
    except httpx.HTTPError as e:
        return {"found": False, "error": f"KIPRIS 접속 실패 ({type(e).__name__})"}
    if resp.status_code != 200:
        return {"found": False, "error": f"KIPRIS 응답 오류 (HTTP {resp.status_code})"}
    try:
        parsed = _parse_items(resp.content)
    except ET.ParseError:
        return {"found": False, "error": "KIPRIS 응답을 XML로 해석하지 못했습니다."}
    except LookupError as e:
        return {"found": False, "error": f"KIPRIS: {e}"}

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
