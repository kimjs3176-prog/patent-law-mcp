"""특허 기술이전 계약 실무 도구 (전용/통상실시 계약조건 설계 및 실무 리스크 검토)

주요 실무 기능:
- design_licensing_terms: 실시권 유형(전용/통상), 선급·경상기술료율, 실시범위, 불실시 해지특약 표준 설계
- review_licensing_contract: 기술실시계약서 초안 조항 검토 및 공공기술 감사 대비 리스크 체크리스트
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def design_licensing_terms(
    patent_id: str,
    license_type: str = "non_exclusive",  # "non_exclusive"(통상실시) or "exclusive"(전용실시)
    company_scale: str = "sme",  # "sme"(중소기업), "middle"(중견), "large"(대기업), "farmer"(농업인/소상공인)
    target_territory: str = "대한민국",
    contract_period_years: int = 3,
    expected_sales_annual: Optional[int] = None,
) -> Dict[str, Any]:
    """공공/국유 특허 기술실시계약의 실무 표준 조건(기술료 체계, 실시범위, 필수 특약)을 산출합니다.

    Args:
        patent_id: 대상 특허 번호
        license_type: 실시권 유형 ("non_exclusive" 통상실시, "exclusive" 전용실시)
        company_scale: 기업 규모 (중소기업, 중견기업, 대기업, 농업인)
        target_territory: 실시 지역 (원칙: 대한민국 내)
        contract_period_years: 계약 기간 (통상 3~5년)
        expected_sales_annual: 연간 예상 매출액 (원 단위, 경상기술료 추정용)
    """
    is_exclusive = license_type == "exclusive"

    # 기업 규모별 기술료율 실무 기준
    royalty_rates = {
        "farmer": {"lump_sum": 0, "running_rate": 0.0, "desc": "무상실시 대상 (농진청/공무원직무발명 규정)"},
        "sme": {"lump_sum": 3_000_000, "running_rate": 0.015, "desc": "중소기업 우대 요율 (경상기술료율 1.5%)"},
        "middle": {"lump_sum": 10_000_000, "running_rate": 0.025, "desc": "중견기업 기준 요율 (경상기술료율 2.5%)"},
        "large": {"lump_sum": 30_000_000, "running_rate": 0.040, "desc": "대기업 기준 요율 (경상기술료율 4.0%)"},
    }

    rate_info = royalty_rates.get(company_scale, royalty_rates["sme"])
    base_lump_sum = rate_info["lump_sum"] * (2.5 if is_exclusive else 1.0)
    running_rate = rate_info["running_rate"] * (1.5 if is_exclusive else 1.0)

    # 필수 실무 특약 조항
    mandatory_clauses = [
        {
            "clause": "불실시 특약 (Due Diligence Clause)",
            "detail": f"계약 체결일로부터 2년 이내에 정당한 사유 없이 상용화(제품 생산 또는 판매)에 착수하지 아니한 경우 통보 후 계약 즉시 해지 가능",
            "practical_importance": "독점적 전용실시권 부여 후 기술을 사장(Sleeping Patent)시키는 행위를 원천 방지하기 위한 핵심 조항",
        },
        {
            "clause": "재실시권(Sub-license) 제한",
            "detail": "실시권자는 연구기관(특허권자)의 사전 서면 승인 없이 제3자에게 재실시권을 설정하거나 양도할 수 없음",
            "practical_importance": "기술 브로커의 중간 차익 편취 방지",
        },
        {
            "clause": "매출액 보고 및 장부 열람권 (Audit Rights)",
            "detail": "경상기술료 정산을 위해 매 사업연도 종료 후 60일 이내에 공인회계사 확인 매출 보고서를 제출하며, 연구기관은 현장 회계장부 열람을 요구할 수 있음",
            "practical_importance": "경상기술료 누락 방지 및 감사원/상급기관 감사 대비 필수",
        },
        {
            "clause": "개량발명의 귀속 (Grant-Back)",
            "detail": "계약 기간 중 실시권자가 본 특허를 개량하여 완성한 기술은 실시권자의 단독 소유로 하되, 원천특허를 침해하는 범위 내에서는 상호 무상 통상실시권 허여",
            "practical_importance": "특허 분쟁 방지 및 상생 협력",
        },
    ]

    return {
        "patent_id": patent_id,
        "license_structure": {
            "type": "전용실시권 (Exclusive License)" if is_exclusive else "통상실시권 (Non-exclusive License)",
            "contract_period": f"{contract_period_years}년 (만료 시 성과평가 후 갱신 가능)",
            "territory": target_territory,
            "field_of_use": "전 산업 분야 또는 지정 제품군 제조·판매",
        },
        "financial_terms": {
            "lump_sum_fee": f"{int(base_lump_sum):,}원 (계약 체결 후 30일 이내 납부)",
            "running_royalty_rate": f"해당 제품 순매출액의 {running_rate * 100:.1f}%",
            "discount_policy": rate_info["desc"],
        },
        "mandatory_practice_clauses": mandatory_clauses,
        "registration_practice": (
            "전용실시권은 특허청 등록을 필하여야 제3자 대항 효력이 발생하므로 등록비용 부담 주체(통상 실시권자 부담)를 명시하십시오."
            if is_exclusive
            else "통상실시권은 등록 없이도 당사자 간 계약으로 유효하나, 권리 안정성을 위해 특허청 등록을 권장합니다."
        ),
    }


def review_licensing_contract(
    contract_clauses: List[Dict[str, str]],
    is_public_patent: bool = True,
) -> Dict[str, Any]:
    """기술실시계약서 초안의 독소 조항, 필수 조항 누락 및 감사 리스크를 실무적으로 점검합니다.

    Args:
        contract_clauses: 계약서 조항 리스트 (예: [{"title": "제4조 기술료", "content": "..."}, ...])
        is_public_patent: 국유특허 또는 공공연구기관 특허 여부 (감사원 감사 대비)
    """
    check_results = []
    missing_critical_clauses = []

    joined_text = "\n".join([f"{c.get('title', '')}: {c.get('content', '')}" for c in contract_clauses])

    # 1. 불실시 해지권 점검
    if "불실시" not in joined_text and "취소" not in joined_text and "해지" not in joined_text:
        missing_critical_clauses.append("불실시(상용화 미착수)에 따른 연구기관의 일방 해지권 조항이 누락되었습니다.")
    else:
        check_results.append("✅ 불실시 해지 관련 조항 확인")

    # 2. 장부 열람권 점검 (경상기술료 시)
    if "경상" in joined_text or "매출" in joined_text:
        if "열람" not in joined_text and "감사" not in joined_text:
            missing_critical_clauses.append("경상기술료 정산을 위한 '회계장부 열람권 및 실사권'이 명시되지 않아 매출 축소 보고 시 제재가 어렵습니다.")
        else:
            check_results.append("✅ 회계장부 실사권 조항 확인")

    # 3. 보증 면책 조항 점검
    if "보증" in joined_text and "책임" in joined_text:
        check_results.append("✅ 특허 유효성 및 제3자 권리 침해 면책 조항 점검 완료 (공공기관 면책 원칙 부합)")
    else:
        missing_critical_clauses.append("공공특허 계약 필수 조항인 '특허권의 유효성 비보증 및 제3자 특허 침해 면책 조항' 보강이 필요합니다.")

    return {
        "audit_risk_level": "높음 (수정 권고)" if missing_critical_clauses else "안전 (체결 가능)",
        "verified_clauses": check_results,
        "critical_missing_or_toxic_risks": missing_critical_clauses,
        "practical_advice": (
            "공공기술 이전 계약은 사후 감사원 및 기관 내부 감사에서 '특혜 제공 시비'나 '기술료 미환수'가 가장 빈번한 지적 사항입니다. "
            "반드시 정형화된 공공연구기관 표준계약서 서식을 준용하십시오."
        ),
    }
