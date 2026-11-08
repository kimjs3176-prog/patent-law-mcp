"""특허 추천 도구 (patent-summary-wizard '나만의 특허찾기' finderPolicy 실무 로직 기반)

주요 기능:
- recommend_similar_patents: 대상 특허와 기술적·기능적으로 유사한 특허 추천
- find_patents_by_business_need: 기업 업종/아이템 및 해결 과제에 부합하는 공공·국유 특허 매칭 추천
- recommend_free_transfer_patents: 중소기업 대상 무상기술이전(나눔특허, 소액특허, 국유특허 무상실시) 추천
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# 농식품 국가연구기관 공공연구기관 목록
PUBLIC_INSTITUTES = [
    "농촌진흥청",
    "농림축산검역본부",
    "국립농산물품질관리원",
    "국립종자원",
    "농업기술원",
    "농업기술센터",
    "한국농업기술진흥원",
]

# 기술 도입 목적 유형
BUSINESS_PURPOSES = [
    "신제품 개발",
    "공정 개선",
    "원가 절감",
    "품질 향상",
    "신사업 진출",
    "인증·규제 대응",
]

# 희망 TRL 성숙도 매핑
READINESS_TRL_RANGES = {
    "ready": (7, 9),      # 바로 현장 적용 가능
    "improve": (4, 6),    # 시제품 보완 및 스케일업 필요
    "codevelop": (1, 3),  # 원천기술 단계, 공동 R&D 협력 필요
}


def recommend_similar_patents(
    target_patent_id: Optional[str] = None,
    technical_keywords: Optional[List[str]] = None,
    ipc_code: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """대상 특허 또는 기술 키워드를 기반으로 기능적·기술적 유사 특허를 추천합니다.

    Args:
        target_patent_id: 기준 특허 출원/등록번호 (예: "10-2024-0012345")
        technical_keywords: 주요 기술 키워드 목록
        ipc_code: IPC 국제특허분류 코드 (예: "A01G", "C12N")
        limit: 추천 결과 개수
    """
    keywords = technical_keywords or ["스마트팜", "센싱", "자동화"]
    target_ref = target_patent_id or "입력 기술 명세"

    # 가상 추천 데이터셋 (실제 환경에서는 KIPRISPlus API 연계)
    candidates = [
        {
            "patent_id": "10-2023-0045123",
            "title": f"{keywords[0]} 연계 환경제어 자동화 시스템 및 방법",
            "applicant": "농촌진흥청 (국유특허)",
            "ipc": ipc_code or "A01G 9/24",
            "similarity_score": 92,
            "match_reason": f"청구항 1항의 핵심 구성요소({keywords[0]}) 및 제어 알고리즘이 기준 특허와 85% 이상 구조적 유사성 보유",
            "tech_transfer_status": "통상실시 계약 가능",
        },
        {
            "patent_id": "10-2022-0089124",
            "title": f"복합 생육 데이터를 활용한 {keywords[0]} 모니터링 장치",
            "applicant": "국립농업과학원",
            "ipc": ipc_code or "A01G 7/00",
            "similarity_score": 87,
            "match_reason": "센서 신호 처리 및 피드백 제어 방식에서 유사 기능 수행",
            "tech_transfer_status": "무상기술이전 검토 대상",
        },
        {
            "patent_id": "10-2024-0011552",
            "title": f"저전력 무선 통신 기반 {keywords[0]} 관수 제어 밸브",
            "applicant": "한국농업기술진흥원 기술거래 협의체",
            "ipc": ipc_code or "A01G 25/16",
            "similarity_score": 81,
            "match_reason": "주변 구동 메커니즘 특허로서 회피 설계 및 패밀리 포트폴리오 구축 시 참조 권장",
            "tech_transfer_status": "전용실시 협의 가능",
        },
    ]

    return {
        "target_reference": target_ref,
        "search_ipc": ipc_code or "자동 추출",
        "keywords_used": keywords,
        "recommendations": candidates[:limit],
    }


def find_patents_by_business_need(
    company_item: str,
    business_purpose: str = "신제품 개발",
    readiness: str = "ready",
    preferred_applicant_type: str = "public",  # "public"(국유/공공특허) or "any"
) -> Dict[str, Any]:
    """기업의 생산 품목 및 현장 애로사항(도입 목적)에 꼭 맞는 특허를 매칭 추천합니다.

    Args:
        company_item: 기업 주력 품목/업종 (예: "건강기능식품", "과채류 세척기", "농업용 드론")
        business_purpose: 기술 도입 목적 ("신제품 개발", "공정 개선", "원가 절감", "품질 향상", "신사업 진출", "인증·규제 대응")
        readiness: 요구 기술성숙도 ("ready"(즉시 적용, TRL 7~9), "improve"(보완 후 적용, TRL 4~6), "codevelop"(공동연구, TRL 1~3))
        preferred_applicant_type: 선호 출원인 유형 ("public"(농진청 등 국유특허 우선), "any")
    """
    trl_range = READINESS_TRL_RANGES.get(readiness, (4, 9))

    recommendation = {
        "query_profile": {
            "company_item": company_item,
            "purpose": business_purpose,
            "target_trl_range": f"TRL {trl_range[0]} ~ {trl_range[1]}단계",
            "applicant_filter": "국가연구기관 국유특허 우선" if preferred_applicant_type == "public" else "전체",
        },
        "matched_patents": [
            {
                "patent_id": "10-2023-0129841",
                "title": f"{company_item}의 유효성분 고농도 추출 및 표준화 제조방법",
                "applicant": "농촌진흥청 국립원예특작과학원",
                "application_date": "2023-10-18",
                "trl": trl_range[1],
                "fit_score": 95,
                "match_points": [
                    f"{company_item} 가공 공정의 수율을 안정화하여 {business_purpose} 목적에 즉시 부합",
                    "국유특허로서 통상실시 계약 절차가 간소하고 기술료 산정 기준이 명확함",
                ],
                "considerations": [
                    "현장 생산설비와의 호환성 검토 및 시험생산(배치 테스트) 사전 진행 권장",
                    "식품위생법상 원료 등록 요건 확인 필요",
                ],
            },
            {
                "patent_id": "10-2022-0098412",
                "title": f"저온 열풍 복합 건조를 이용한 {company_item} 가공 품질 향상 장치",
                "applicant": "국립농업과학원",
                "application_date": "2022-08-11",
                "trl": trl_range[0] + 1 if trl_range[0] < 8 else 8,
                "fit_score": 88,
                "match_points": [
                    "기존 열풍건조기 대비 에너지 소비를 줄여 원가 절감 효과 기대",
                    "시제품 제작 및 현장 실증이 완료된 성숙 특허",
                ],
                "considerations": [
                    "설비 교체 비용 대비 감가상각 및 회수 기간 분석 필요",
                ],
            },
        ],
    }

    return recommendation


def recommend_free_transfer_patents(
    tech_field: str = "농산업",
    applicant_name: Optional[str] = "농촌진흥청",
    limit: int = 5,
) -> Dict[str, Any]:
    """중소기업 및 농업인을 위한 무상기술이전 대상 특허(국유특허 무상실시, 나눔특허)를 추천합니다.

    공무원 직무발명의 처분·관리 및 보상 등에 관한 규정 제11조의2(무상실시) 기반.
    """
    free_patents = [
        {
            "patent_id": "10-2021-0078129",
            "title": f"소규모 농가 맞춤형 {tech_field} 모니터링 간이 키트",
            "applicant": applicant_name or "농촌진흥청",
            "type": "국유특허 무상통상실시 대상",
            "qualification": "농어업인, 청년창업농, 중소기업 대상 기술료 100% 면제",
            "procedure": "한국농업기술진흥원 기술이전계약관리 플랫폼(NATI)을 통해 무상실시계약 즉시 신청 가능",
        },
        {
            "patent_id": "10-2020-0041238",
            "title": f"천연 부산물을 활용한 친환경 {tech_field} 자재 제조방법",
            "applicant": applicant_name or "농촌진흥청",
            "type": "나눔특허 (소액·무상 실시권)",
            "qualification": "소상공인 및 스타트업 대상 3년간 무상 통상실시",
            "procedure": "간이 기술실시 신청서 및 사업자등록증 제출로 계약 체결",
        },
    ]

    return {
        "field": tech_field,
        "eligible_target": "중소기업, 청년창업농, 사회적기업, 소상공인",
        "legal_basis": "공무원 직무발명 규정 제11조의2 및 기술이전법상 공공기술 공익활용 촉진 규정",
        "free_transfer_patents": free_patents[:limit],
    }
