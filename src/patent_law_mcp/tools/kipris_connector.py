"""KIPRISPlus 실시간 연동 및 출원번호 기반 자동 파싱 도구

KIPRIS Plus Open API(또는 공보 XML)를 연동하여 출원번호 입력만으로
서지사항, 등록청구항, 권리상태, 초록을 자동 수집하고 특허분석 파이프라인에 직결합니다.
"""

import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from patent_law_mcp.tools.analysis import summarize_patent, evaluate_commercialization

KIPRIS_API_BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"


def clean_appno(appno: str) -> str:
    """출원번호에서 하이픈 등 특수기호를 제거하고 13자리 숫자만 정제합니다."""
    return re.sub(r"\D", "", appno)


def get_service_key(provided_key: Optional[str] = None) -> Optional[str]:
    """환경변수 또는 인자로 전달된 KIPRIS Plus 인증키를 확인합니다."""
    if provided_key:
        return provided_key
    return os.environ.get("KIPRIS_API_KEY")


def parse_kipris_xml_response(raw_xml: str) -> Dict[str, Any]:
    """KIPRIS Plus XML 응답을 파싱하여 정형화된 특허 메타데이터 딕셔너리로 변환합니다."""
    try:
        root = ET.fromstring(raw_xml)
    except Exception as e:
        raise ValueError(f"XML 파싱 실패: {str(e)}")

    item = root.find(".//item")
    if item is None:
        err_msg = ""
        for tag in [".//resultMsg", ".//errMsg", ".//header/resultMsg"]:
            node = root.find(tag)
            if node is not None and node.text:
                err_msg = node.text.strip()
                break
        raise RuntimeError(f"KIPRIS API 결과 오류: {err_msg or '데이터를 찾을 수 없습니다.'}")

    b = item.find("biblioSummaryInfoArray/biblioSummaryInfo")
    if b is None:
        b = item

    def get_text(node: Optional[ET.Element], path: str) -> str:
        if node is None:
            return ""
        n = node.find(path)
        return (n.text or "").strip() if n is not None and n.text else ""

    title = get_text(b, "inventionTitle") or get_text(item, "inventionTitle")
    app_no = get_text(b, "applicationNumber") or get_text(item, "applicationNumber")
    app_date = get_text(b, "applicationDate") or get_text(item, "applicationDate")
    reg_no = get_text(b, "registerNumber") or get_text(item, "registerNumber")
    reg_date = get_text(b, "registerDate") or get_text(item, "registerDate")
    reg_status = get_text(b, "registerStatus") or get_text(item, "registerStatus") or "등록"
    ipc_code = get_text(b, "ipcNumber") or get_text(item, "ipcNumber")
    applicant = get_text(b, "applicantName") or get_text(item, "applicantName") or "농촌진흥청"
    abstract = get_text(b, "astrtCont") or get_text(item, "astrtCont")

    # 청구항 파싱
    claims = []
    claim_nodes = item.findall(".//claimInfoArray/claimInfo") or item.findall(".//claim")
    for cn in claim_nodes:
        txt = get_text(cn, "claim") or (cn.text or "").strip()
        if txt:
            claims.append(txt)

    if not claims:
        # 단일 claim 태그 대응
        single_claim = get_text(item, ".//claim")
        if single_claim:
            claims.append(single_claim)
        else:
            claims.append(abstract or f"{title}에 관한 독립 청구항")

    return {
        "title": title,
        "application_number": app_no,
        "application_date": app_date,
        "register_number": reg_no,
        "register_date": reg_date,
        "register_status": reg_status,
        "ipc_code": ipc_code,
        "applicant": applicant,
        "abstract": abstract,
        "claims": claims,
    }


def fetch_patent_from_kipris(
    application_number: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """KIPRIS Plus Open API를 호출하여 출원번호 기준 특허 원문 및 서지정보를 실시간 조회합니다.

    Args:
        application_number: 13자리 출원번호 (예: "10-2023-0045123" 또는 "1020230045123")
        api_key: KIPRIS Plus 인증키 (미입력 시 환경변수 KIPRIS_API_KEY 참조)
    """
    clean_no = clean_appno(application_number)
    key = get_service_key(api_key)

    if not key:
        # KIPRIS API 키가 없는 개발/시연 환경을 위한 시뮬레이션 폴백
        return {
            "source": "simulation_fallback (KIPRIS_API_KEY 미설정)",
            "title": "근적외선 분광을 이용한 과채류 비파괴 당도 선별 장치 및 선별 방법",
            "application_number": clean_no or "1020230045123",
            "application_date": "2023-04-12",
            "register_number": "1025894120000",
            "register_date": "2023-11-20",
            "register_status": "등록 (존속중)",
            "ipc_code": "A01D 45/00",
            "applicant": "농촌진흥청 국립원예특작과학원 (국유특허)",
            "abstract": "본 발명은 과채류의 외형 손상 없이 내부 당도를 고속으로 정밀 측정하여 자동 선별하는 비파괴 선별 장치 및 방법에 관한 것이다.",
            "claims": [
                "과채류를 공급받아 이송하는 컨베이어 모듈; 상기 컨베이어 모듈 상부에 배치되어 850nm 파장의 근적외선 광을 조사하는 조명부; 상기 과채류를 투과한 광 스펙트럼을 분석하여 당도를 산출하는 분광 센서부; 및 상기 당도 산출값에 따라 등급별로 과채류를 분류 배출하는 솔레노이드 액추에이터;를 포함하는 과채류 비파괴 당도 선별 장치.",
                "제1항에 있어서, 상기 조명부는 45도 입사각으로 광을 조사하는 것을 특징으로 하는 선별 장치.",
            ],
            "api_guide": "실제 KIPRIS Plus 운영 조회를 위해 환경변수 KIPRIS_API_KEY를 설정하세요.",
        }

    url = KIPRIS_API_BASE + "?" + urllib.parse.urlencode({
        "applicationNumber": clean_no,
        "ServiceKey": key,
    })

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PatentLawMCP/1.0)"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw_xml = resp.read().decode("utf-8", errors="replace")

    parsed = parse_kipris_xml_response(raw_xml)
    parsed["source"] = "KIPRIS Plus 실시간 Open API"
    return parsed


def inspect_and_summarize_by_appno(
    application_number: str,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """출원번호 하나만으로 KIPRIS 서지조회부터 특허고도화 요약, TRL 진단, 60초 피치 대본까지 원스톱 실행합니다.

    실무 워크플로우:
    1. KIPRIS Plus에서 서지정보, 권리상태, 등록청구항 자동 수집
    2. atipsum 및 patent-video-skill 파이프라인으로 시그니처 요약서 생성
    3. TRL 사업화 진단 및 바이어 브리핑 피치 결합 출력
    """
    patent_data = fetch_patent_from_kipris(application_number, api_key)

    title = patent_data["title"]
    abstract = patent_data["abstract"]
    claims = patent_data.get("claims", [])
    applicant = patent_data.get("applicant", "농촌진흥청")
    reg_status = patent_data.get("register_status", "등록")

    # 고도화 요약기 구동
    summary = summarize_patent(
        patent_id=patent_data.get("register_number") or patent_data.get("application_number"),
        title=title,
        abstract=abstract,
        claims=claims,
        applicant=applicant,
    )

    # 사업화 TRL 진단 구동
    trl = evaluate_commercialization(
        technology_domain=summary["technology_type"],
        claims_count=len(claims),
        has_experimental_data=True,
    )

    return {
        "metadata": {
            "source": patent_data.get("source"),
            "application_number": patent_data.get("application_number"),
            "register_number": patent_data.get("register_number"),
            "legal_status": reg_status,
            "ipc_code": patent_data.get("ipc_code"),
            "applicant": applicant,
        },
        "summary": summary,
        "commercialization_trl": trl,
    }
