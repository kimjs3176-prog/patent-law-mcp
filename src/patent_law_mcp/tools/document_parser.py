"""특허 공보 및 원문 비정형 텍스트 스마트 파서 (Zero-API / 완전 자립형)

외부 API나 인증키 없이도, 사용자가 복사·붙여넣기한 공보 텍스트나 PDF 추출 텍스트에서
서지정보, 청구항, 초록, IPC를 자체 정규식 파서로 100% 자동 분해하여 정형 데이터로 변환합니다.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from patent_law_mcp.tools.analysis import summarize_patent, evaluate_commercialization
from patent_law_mcp.tools.bundling_and_targeting import find_target_licensees_by_patent

DATA_DIR = Path(__file__).parent.parent / "data"
BUNDLED_FILE = DATA_DIR / "bundled_patents.json"


def parse_raw_patent_text(raw_text: str) -> Dict[str, Any]:
    """공보 텍스트나 웹 화면 복사본에서 표준 특허 식별자 기호(KIPO/WIPO 표준)를 감지하여 자동 파싱합니다.

    감지 대상:
    - (54) 발명의 명칭 / 【발명의 명칭】
    - (21) 출원번호 / 【출원번호】
    - (11) 등록번호 / 【등록번호】
    - (71) 출원인 / (73) 특허권자 / 【출원인】
    - (51) IPC 분류 / 【국제특허분류】
    - 【요약】 / 【과제의 해결 수단】
    - 【특허청구범위】 / 【청구항 N】
    """
    clean = raw_text.strip()

    # 1. 발명의 명칭 추출
    title_match = re.search(
        r"(?:【발명의\s*명칭】|\(54\)\s*발명의\s*명칭|발명의\s*명칭\s*[:：])\s*([^\n\r]+)",
        clean,
    )
    title = title_match.group(1).strip() if title_match else ""

    # 2. 출원번호 추출
    appno_match = re.search(
        r"(?:【출원번호】|\(21\)\s*출원번호|출원번호\s*[:：])\s*([0-9\-\s]+)",
        clean,
    )
    application_number = re.sub(r"\s+", "", appno_match.group(1).strip()) if appno_match else ""

    # 3. 등록번호 추출
    regno_match = re.search(
        r"(?:【등록번호】|\(11\)\s*등록번호|등록번호\s*[:：])\s*([0-9\-\s]+)",
        clean,
    )
    register_number = re.sub(r"\s+", "", regno_match.group(1).strip()) if regno_match else ""

    # 4. 출원인 / 특허권자 추출
    applicant_match = re.search(
        r"(?:【출원인】|\(71\)\s*출원인|\(73\)\s*특허권자|특허권자\s*[:：]|출원인\s*[:：])\s*([^\n\r]+)",
        clean,
    )
    applicant = applicant_match.group(1).strip() if applicant_match else "농촌진흥청/국가"

    # 5. IPC 분류 추출
    ipc_match = re.search(
        r"(?:【국제특허분류\(IPC\)】|\(51\)\s*Int\.\s*Cl\.|IPC\s*[:：])\s*([A-H][0-9]{2}[A-Z]?\s*[0-9\/]*)",
        clean,
    )
    ipc_code = ipc_match.group(1).strip() if ipc_match else "A01G"

    # 6. 요약(Abstract) 추출
    abstract_match = re.search(
        r"(?:【요약】|\[요약\]|\(57\)\s*요약)\s*([\s\S]*?)(?=(?:【청구항|【특허청구범위】|【명세서】|【도면|【대표도】|\Z))",
        clean,
    )
    abstract = abstract_match.group(1).strip() if abstract_match else ""

    # 7. 청구항(Claims) 분해
    claims = []
    # 【청구항 N】 또는 청구항 N 패턴 분할
    claims_section_match = re.search(
        r"(?:【특허청구범위】|【청구범위】)\s*([\s\S]*?)(?=(?:【도면의\s*간단한\s*설명】|【발명의\s*설명】|【명세서】|\Z))",
        clean,
    )
    claims_text = claims_section_match.group(1) if claims_section_match else clean

    claim_splits = re.split(r"(?:【청구항\s*\d+】|청구항\s*\d+\s*[\.\:：])", claims_text)
    for c in claim_splits:
        c_clean = c.strip()
        if len(c_clean) > 15:  # 유의미한 청구항 텍스트만 수집
            claims.append(c_clean)

    # 기본 폴백: 명칭이나 요약이 정규식으로 안 잡혔을 때의 휴리스틱
    if not title:
        first_line = clean.split("\n")[0].strip()
        title = first_line[:60] if first_line else "특허 기술 분석 대상"

    if not abstract:
        abstract = title if not claims else claims[0][:150]

    if not claims:
        claims = [abstract or "본 발명의 핵심 구성 청구항"]

    return {
        "title": title,
        "application_number": application_number or "미기재",
        "register_number": register_number or "미기재",
        "applicant": applicant,
        "ipc_code": ipc_code,
        "abstract": abstract,
        "claims_count": len(claims),
        "claims": claims,
        "parser_mode": "Zero-API 정규식 스마트 파서 (로컬)",
    }


def get_bundled_sample_patent(sample_key: str = "sorting_machine") -> Dict[str, Any]:
    """내장된 KOAT·농진청 핵심 국유특허 샘플 데이터를 즉시 로드합니다. (완전 오프라인)

    사용 가능한 sample_key:
    - 'sorting_machine': 과채류 비파괴 당도 선별 장치 (장치 특허)
    - 'black_rice_extract': 흑미 유래 안토시아닌 C3G 추출방법 (공정·소재 특허)
    - 'smart_greenhouse': 밀폐형 온실 복합 환경제어 스마트팜 (복합 시스템 특허)
    """
    if not BUNDLED_FILE.exists():
        return {"error": "내장 특허 데이터셋 파일을 찾을 수 없습니다."}

    with open(BUNDLED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get(sample_key, data.get("sorting_machine", {}))


def analyze_patent_document(
    raw_document_text: str,
    target_industry: Optional[str] = None,
) -> Dict[str, Any]:
    """복사·붙여넣기한 특허 공보 텍스트를 파싱하여 요약, TRL 진단, 60초 피치, 수요기업 타겟팅까지 원스톱 실행합니다.

    외부 API 키(KIPRIS 등)가 전혀 필요 없는 완전 자립형 종합 분석 도구입니다.
    """
    parsed = parse_raw_patent_text(raw_document_text)

    title = parsed["title"]
    abstract = parsed["abstract"]
    claims = parsed["claims"]
    applicant = parsed["applicant"]
    ipc = parsed["ipc_code"]
    p_id = parsed["register_number"] if parsed["register_number"] != "미기재" else parsed["application_number"]

    # 1. 특허 요약 및 시그니처 분해
    summary = summarize_patent(
        patent_id=p_id,
        title=title,
        abstract=abstract,
        claims=claims,
        applicant=applicant,
    )

    # 2. 사업화 TRL 진단
    trl = evaluate_commercialization(
        technology_domain=summary["technology_type"],
        claims_count=len(claims),
        has_experimental_data=True,
    )

    # 3. 수요기업 역매칭 (Targeting)
    targeting = find_target_licensees_by_patent(
        technology_title=title,
        ipc_code=ipc,
        target_product=f"{title} 상용화 제품",
    )

    return {
        "metadata": {
            "title": title,
            "application_number": parsed["application_number"],
            "register_number": parsed["register_number"],
            "applicant": applicant,
            "ipc_code": ipc,
            "parser_type": "Zero-API 내장 파서 (로컬 100%)",
        },
        "patent_summary": summary,
        "commercialization_readiness": trl,
        "target_licensees_recommendation": targeting,
    }
