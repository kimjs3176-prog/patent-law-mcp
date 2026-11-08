"""특허 공보·명세서 텍스트 파서 (로컬, 외부 API 불필요)

사용자가 붙여넣은 공보 텍스트(KIPRIS·공보 PDF 복사본) 또는 전자출원 명세서(【청구항 1】 형식)에서
서지사항·초록·청구항을 분해합니다. 찾지 못한 항목은 지어내지 않고 빈 값과 경고로 알려 줍니다.
"""

import json
import re
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from pydantic import Field

from patent_law_mcp.tools.analysis import evaluate_commercialization, summarize_patent
from patent_law_mcp.tools.bundling_and_targeting import find_target_licensees_by_patent
from patent_law_mcp.tools.claim_utils import is_deleted_claim, is_dependent_claim, normalize_ws

DATA_DIR = Path(__file__).parent.parent / "data"
BUNDLED_FILE = DATA_DIR / "bundled_patents.json"

KEY_ALIASES = {
    "sorting_machine": "sorting_machine",
    "선별기": "sorting_machine",
    "과채류": "sorting_machine",
    "non_hardening_rice_cake": "non_hardening_rice_cake",
    "rice_cake": "non_hardening_rice_cake",
    "굳지않는떡": "non_hardening_rice_cake",
    "떡": "non_hardening_rice_cake",
    "black_rice_extract": "black_rice_extract",
    "흑미": "black_rice_extract",
    "smart_greenhouse": "smart_greenhouse",
    "온실": "smart_greenhouse",
    "스마트팜": "smart_greenhouse",
}


def _spaced(word: str) -> str:
    """'요약' -> '요\\s*약' : 공보 PDF 복사본의 자간 공백('요 약', '명 세 서')을 허용합니다."""
    return r"\s*".join(re.escape(ch) for ch in word)


_PAT_NO = r"\d{2}\s*-\s*\d{4}\s*-\s*\d{7}|\d{13}"
_REG_NO = r"\d{2}\s*-\s*\d{7}|\d{9}"

_ABSTRACT_START = rf"【요약】|\[요약\]|\(57\)\s*{_spaced('요약')}|^[ \t]*{_spaced('요약')}[ \t]*$"
_ABSTRACT_END = (
    rf"【대표도】|{_spaced('대표도')}|【청구|【특허청구범위】|{_spaced('특허청구의범위')}|{_spaced('특허청구범위')}"
    rf"|^[ \t]*{_spaced('청구범위')}[ \t]*$|【명세서】|^[ \t]*{_spaced('명세서')}[ \t]*$|【도면|【발명의\s*설명】"
)
_CLAIMS_START = (
    rf"【특허청구범위】|【청구범위】|{_spaced('특허청구의범위')}|{_spaced('특허청구범위')}"
    rf"|^[ \t]*{_spaced('청구범위')}[ \t]*$"
)
_CLAIMS_END = (
    rf"【발명의\s*설명】|【명세서】|^[ \t]*{_spaced('명세서')}[ \t]*$|【도면의\s*간단한\s*설명】|【요약서】|【요약】"
    rf"|【도면】|^[ \t]*{_spaced('기술분야')}[ \t]*$|^[ \t]*{_spaced('발명의설명')}[ \t]*$"
)
_CLAIM_HEADER = re.compile(r"【\s*청구항\s*(\d+)\s*】|^[ \t]*청\s*구\s*항[ \t]*(\d+)[ \t]*(?:[.:：][ \t]*|$)", re.M)


def _first(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return normalize_ws(m.group(1)) if m else ""


def _format_app_no(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    return f"{d[:2]}-{d[2:6]}-{d[6:]}" if len(d) == 13 else raw


def _format_reg_no(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    return f"{d[:2]}-{d[2:]}" if len(d) == 9 else raw


def _extract_claims(text: str) -> List[Dict[str, Any]]:
    start = re.search(_CLAIMS_START, text, re.M)
    region = text[start.end():] if start else text
    headers = list(_CLAIM_HEADER.finditer(region))
    if not headers:
        return []

    end = re.search(_CLAIMS_END, region[headers[-1].end():], re.M)
    region_end = headers[-1].end() + end.start() if end else len(region)

    claims = []
    for i, h in enumerate(headers):
        body_end = headers[i + 1].start() if i + 1 < len(headers) else region_end
        body = normalize_ws(region[h.end():body_end])
        if body:
            claims.append({"number": int(h.group(1) or h.group(2)), "text": body})
    return claims


def parse_raw_patent_text(raw_text: Annotated[str, Field(min_length=20)]) -> Dict[str, Any]:
    """공보 텍스트나 명세서에서 발명의 명칭·출원/등록/공개번호·출원인(특허권자)·IPC·초록·청구항을 분해합니다.

    지원 형식: 등록/공개특허공보 복사본("(54) 발명의 명칭", "(57) 요 약", "청구항 1"),
    전자출원 명세서("【발명의 명칭】", "【청구항 1】"). 찾지 못한 항목은 빈 값으로 두고 warnings에 기록합니다.
    """
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    warnings: List[str] = []

    title = _first(r"(?:【발명의\s*명칭】|\(54\)\s*발명의\s*명칭|발명의\s*명칭)\s*[:：]?\s*([^\n]+)", text)
    application_number = _first(rf"(?:【출원번호】|\(21\)\s*출원번호|출원번호)\s*[:：]?\s*({_PAT_NO})", text)
    register_number = _first(rf"(?:【등록번호】|\(11\)\s*등록번호|등록번호)\s*[:：]?\s*({_REG_NO})(?!\d)", text)
    publication_number = _first(rf"(?:\(11\)\s*공개번호|공개번호)\s*[:：]?\s*({_PAT_NO})", text)

    applicant = _first(r"【(?:출원인|특허권자)】[\s\S]{0,40}?【명칭】\s*([^\n]+)", text) or _first(
        r"(?:\(73\)\s*특허권자|\(71\)\s*출원인|【특허권자】|【출원인】|특허권자|출원인)\s*[:：]?\s*([^\n]+)", text
    )

    ipc_match = re.search(
        r"(?:【국제특허분류[^】]*】|\(51\)|국제특허분류|Int\.\s*Cl|IPC)[\s\S]{0,200}?([A-H]\d{2}[A-Z])\s*(\d{1,4}\s*/\s*\d{2,6})",
        text,
    )
    ipc_code = f"{ipc_match.group(1)} {re.sub(r'\s', '', ipc_match.group(2))}" if ipc_match else ""

    abstract_match = re.search(rf"(?:{_ABSTRACT_START})\s*([\s\S]*?)(?=(?:{_ABSTRACT_END})|\Z)", text, re.M)
    abstract = normalize_ws(abstract_match.group(1)) if abstract_match else ""

    claim_items = _extract_claims(text)
    claims = [c["text"] for c in claim_items]

    for value, label in [
        (title, "발명의 명칭"),
        (applicant, "출원인/특허권자"),
        (ipc_code, "IPC"),
        (abstract, "초록"),
    ]:
        if not value:
            warnings.append(f"{label}을(를) 찾지 못했습니다.")
    if not (application_number or register_number or publication_number):
        warnings.append("출원·등록·공개번호를 찾지 못했습니다.")
    if not claims:
        warnings.append("청구항을 찾지 못했습니다. '청구항 1' 또는 '【청구항 1】' 머리말이 포함되어 있는지 확인하십시오.")

    return {
        "title": title,
        "application_number": _format_app_no(application_number) if application_number else "",
        "register_number": _format_reg_no(register_number) if register_number else "",
        "publication_number": _format_app_no(publication_number) if publication_number else "",
        "applicant": applicant,
        "ipc_code": ipc_code,
        "abstract": abstract,
        "claims_count": len(claims),
        "claim_numbers": [c["number"] for c in claim_items],
        "independent_claim_numbers": [
            c["number"] for c in claim_items if not is_deleted_claim(c["text"]) and not is_dependent_claim(c["text"])
        ],
        "claims": claims,
        "warnings": warnings,
        "parser_mode": "로컬 정규식 파서",
    }


def _load_samples() -> Dict[str, Any]:
    with open(BUNDLED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}, data.get("_notice", "")


def get_bundled_sample_patent(sample_key: str = "sorting_machine") -> Dict[str, Any]:
    """도구 시연·테스트용 가상 샘플 특허를 불러옵니다. (실존 특허가 아닙니다)

    사용 가능한 sample_key (별칭):
    - 'non_hardening_rice_cake' ('떡', '굳지않는떡'): 식품 제조방법 예시
    - 'sorting_machine' ('선별기', '과채류'): 장치·방법 예시
    - 'black_rice_extract' ('흑미'): 추출 공정 예시
    - 'smart_greenhouse' ('온실', '스마트팜'): 복합 시스템 예시
    """
    if not BUNDLED_FILE.exists():
        return {"found": False, "error": "내장 샘플 데이터 파일을 찾을 수 없습니다."}

    samples, notice = _load_samples()
    clean_key = re.sub(r"\s+", "", sample_key.strip().lower())
    canonical_key = KEY_ALIASES.get(clean_key, clean_key)

    if canonical_key not in samples:
        return {
            "found": False,
            "error": f"'{sample_key}'에 해당하는 샘플이 없습니다. 실제 특허 조회는 fetch_patent_smart를 사용하십시오.",
            "available_samples": sorted(samples),
        }

    return {"found": True, "sample_key": canonical_key, **samples[canonical_key], "notice": notice}


def analyze_patent_document(
    raw_document_text: Annotated[str, Field(min_length=20)],
    target_industry: Optional[str] = None,
) -> Dict[str, Any]:
    """붙여넣은 공보 텍스트를 파싱한 뒤 요약 초안과 수요기업 탐색 참고자료를 함께 만듭니다. (외부 API 불필요)

    Args:
        raw_document_text: 공보 또는 명세서 텍스트
        target_industry: 목표 산업·제품 (수요기업 탐색에 반영, 선택)
    """
    parsed = parse_raw_patent_text(raw_document_text)
    metadata = {
        "title": parsed["title"],
        "application_number": parsed["application_number"],
        "register_number": parsed["register_number"],
        "publication_number": parsed["publication_number"],
        "applicant": parsed["applicant"],
        "ipc_code": parsed["ipc_code"],
        "parser_type": parsed["parser_mode"],
    }

    if not parsed["claims"]:
        return {
            "metadata": metadata,
            "error": "청구항을 찾지 못해 분석을 중단했습니다.",
            "warnings": parsed["warnings"],
        }

    p_id = parsed["register_number"] or parsed["application_number"] or parsed["publication_number"] or "번호 미기재"
    summary = summarize_patent(
        patent_id=p_id,
        title=parsed["title"],
        abstract=parsed["abstract"],
        claims=parsed["claims"],
        applicant=parsed["applicant"] or None,
    )

    return {
        "metadata": metadata,
        "warnings": parsed["warnings"],
        "patent_summary": summary,
        "commercialization_readiness": evaluate_commercialization(summary["technology_type"]),
        "target_licensees_recommendation": find_target_licensees_by_patent(
            technology_title=parsed["title"] or summary["claimed_subject_matter"],
            ipc_code=parsed["ipc_code"] or None,
            target_product=target_industry,
        ),
    }
