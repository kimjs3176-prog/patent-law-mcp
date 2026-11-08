"""국가법령정보 공동활용 Open API 조문 조회 (환경변수 LAW_OC 필요)

- search_laws: 법령(target=law)·행정규칙(target=admrul) 목록 검색
- get_law_article: 법령명 + 조문 번호로 현행 조문 원문(항·호 포함) 조회

OC는 open.law.go.kr에서 Open API 사용 신청 후 받은 아이디이며, 신청 시 호출할 서버의 IP·도메인을 등록해야 합니다.
"""

import os
import re
from typing import Annotated, Any, Dict, List, Literal, Optional

import httpx
from pydantic import Field

from patent_law_mcp import net
from patent_law_mcp.config import settings

LAW_API = "https://www.law.go.kr/DRF"
LAW_SITE = "https://www.law.go.kr"


def _oc() -> str:
    return os.environ.get("LAW_OC", "").strip()


def _need_oc() -> Dict[str, Any]:
    return {
        "found": False,
        "error": "법령 조회에는 국가법령정보 공동활용 OC가 필요합니다 (환경변수 LAW_OC).",
        "how_to": "open.law.go.kr에서 회원가입 후 Open API 사용 신청(무료) 시 호출 서버의 IP·도메인을 등록하고, 받은 아이디를 LAW_OC로 설정하십시오.",
    }


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _get_json(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        resp = net.http_get(f"{LAW_API}/{endpoint}", params={"OC": _oc(), "type": "JSON", **params},
                            timeout=settings.request_timeout_seconds)
    except httpx.HTTPError as e:
        raise LookupError(f"법령 API 접속 실패 ({type(e).__name__})")
    if resp.status_code != 200:
        raise LookupError(f"법령 API 응답 오류 (HTTP {resp.status_code})")
    try:
        data = resp.json()
    except ValueError:
        raise LookupError("법령 API 응답을 JSON으로 해석하지 못했습니다.")
    if isinstance(data, dict) and "result" in data and "msg" in data:
        raise LookupError(f"{data['result']} {data['msg']}")
    return data


def _search(query: str, target: str, display: int) -> List[Dict[str, Any]]:
    data = _get_json("lawSearch.do", {"target": target, "query": query, "display": display})
    if target == "law":
        rows = _as_list((data.get("LawSearch") or {}).get("law"))
        return [{
            "name": r.get("법령명한글", ""),
            "kind": r.get("법령구분명", ""),
            "mst": r.get("법령일련번호", ""),
            "law_id": r.get("법령ID", ""),
            "effective_date": r.get("시행일자", ""),
            "promulgation_date": r.get("공포일자", ""),
            "ministry": r.get("소관부처명", ""),
            "link": LAW_SITE + r["법령상세링크"] if r.get("법령상세링크") else "",
        } for r in rows]
    rows = _as_list((data.get("AdmRulSearch") or {}).get("admrul"))
    return [{
        "name": r.get("행정규칙명", ""),
        "kind": r.get("행정규칙종류", ""),
        "id": r.get("행정규칙일련번호", ""),
        "issued_date": r.get("발령일자", ""),
        "effective_date": r.get("시행일자", ""),
        "ministry": r.get("소관부처명", ""),
        "link": LAW_SITE + r["행정규칙상세링크"] if r.get("행정규칙상세링크") else "",
    } for r in rows]


def search_laws(
    query: Annotated[str, Field(min_length=1, max_length=100)],
    kind: Literal["law", "admrul"] = "law",
    page_size: Annotated[int, Field(ge=1, le=50)] = 10,
) -> Dict[str, Any]:
    """국가법령정보센터에서 법령 또는 행정규칙(고시·훈령·예규)을 검색합니다.

    Args:
        query: 법령명 검색어 (예: "특허법", "직무발명", "기술의 이전")
        kind: "law"(법률·대통령령·부령) 또는 "admrul"(행정규칙: 고시 등)
        page_size: 결과 건수
    """
    if not _oc():
        return _need_oc()
    try:
        rows = _search(query, kind, page_size)
    except LookupError as e:
        return {"found": False, "error": str(e)}
    return {"found": bool(rows), "source": "국가법령정보 공동활용 Open API", "query": query, "kind": kind, "results": rows}


def article_code(article: str) -> str:
    """'제15조의2' / '15의2' / '100' -> JO 6자리 ('001502', '010000')"""
    m = re.fullmatch(r"\s*(?:제)?\s*(\d{1,4})\s*(?:조)?\s*(?:의\s*(\d{1,2}))?\s*", article)
    if not m:
        raise ValueError(f"조문 번호 형식이 아닙니다: '{article}' (예: '제100조', '15의2')")
    return f"{int(m.group(1)):04d}{int(m.group(2) or 0):02d}"


def _format_article(unit: Dict[str, Any]) -> str:
    lines = [str(unit.get("조문내용", "")).strip()]
    for para in _as_list(unit.get("항")):
        if isinstance(para, dict):
            if para.get("항내용"):
                lines.append(str(para["항내용"]).strip())
            for item in _as_list(para.get("호")):
                if isinstance(item, dict) and item.get("호내용"):
                    lines.append("  " + str(item["호내용"]).strip())
                    for sub in _as_list(item.get("목")):
                        if isinstance(sub, dict) and sub.get("목내용"):
                            lines.append("    " + str(sub["목내용"]).strip())
    return "\n".join(l for l in lines if l)


def get_law_article(
    law_name: Annotated[str, Field(min_length=1, max_length=100)],
    article: Annotated[str, Field(min_length=1, max_length=20)],
) -> Dict[str, Any]:
    """법령명과 조문 번호로 현행 조문 원문(항·호·목 포함)과 시행일을 조회합니다.

    Args:
        law_name: 법령명 (예: "특허법", "발명진흥법", "기술의 이전 및 사업화 촉진에 관한 법률")
        article: 조문 번호 (예: "제100조", "15의2", "88")
    """
    if not _oc():
        return _need_oc()
    jo = article_code(article)
    try:
        candidates = _search(law_name, "law", 20)
        if not candidates:
            return {"found": False, "error": f"'{law_name}'에 해당하는 법령을 찾지 못했습니다."}
        compact = re.sub(r"\s+", "", law_name)
        law = next((c for c in candidates if re.sub(r"\s+", "", c["name"]) == compact), candidates[0])
        data = _get_json("lawService.do", {"target": "law", "MST": law["mst"], "JO": jo})
    except LookupError as e:
        return {"found": False, "error": str(e)}

    body = data.get("법령") or {}
    info = body.get("기본정보") or {}
    units = [u for u in _as_list((body.get("조문") or {}).get("조문단위")) if isinstance(u, dict) and u.get("조문여부", "조문") == "조문"]
    want_no, want_branch = int(jo[:4]), int(jo[4:])
    unit = next((u for u in units if int(u.get("조문번호") or 0) == want_no and int(u.get("조문가지번호") or 0) == want_branch), None)
    label = f"제{want_no}조" + (f"의{want_branch}" if want_branch else "")
    if not unit:
        return {"found": False, "error": f"{law['name']}에서 {label}를 찾지 못했습니다.", "law": law}

    return {
        "found": True,
        "source": "국가법령정보 공동활용 Open API",
        "law_name": info.get("법령명_한글") or law["name"],
        "article": label,
        "article_title": unit.get("조문제목", ""),
        "text": _format_article(unit),
        "effective_date": info.get("시행일자") or law["effective_date"],
        "article_effective_date": unit.get("조문시행일자", ""),
        "link": law["link"],
        "other_matches": [c["name"] for c in candidates if c is not law][:5],
    }
