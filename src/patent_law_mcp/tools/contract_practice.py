"""특허 기술이전 계약 실무 도구 (지식재산처고시 제2025-4호 및 국유특허 업무편람 반영)

주요 실무 기능:
- design_licensing_terms: 실시권 유형(전용/통상), 고시 기준 최소실시료(300만원/60일 이내), 선급·경상기술료율 산출
- review_licensing_contract: 계약서 초안 조항 검토 및 지식재산처 승인·감사 대비 리스크 체크리스트
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
    """공공/국유 특허 기술실시계약의 실무 표준 조건(지식재산처 고시 기준 최소실시료, 실시범위, 필수 특약)을 산출합니다.

    지식재산처고시 제2025-4호 제9조 (전용실시 최소실시료 300만원 이상 60일 이내 납부) 반영.
    """
    is_exclusive = license_type == "exclusive"

    # 기업 규모별 기술료율 실무 기준
    royalty_rates = {
        "farmer": {"lump_sum": 0, "running_rate": 0.0, "desc": "무상실시 대상 (지식재산처고시 제3조)"},
        "sme": {"lump_sum": 3_000_000, "running_rate": 0.015, "desc": "중소기업 우대 요율 (경상기술료율 1.5%~2.0%)"},
        "middle": {"lump_sum": 10_000_000, "running_rate": 0.025, "desc": "중견기업 기준 요율 (경상기술료율 2.5%)"},
        "large": {"lump_sum": 30_000_000, "running_rate": 0.040, "desc": "대기업 기준 요율 (경상기술료율 4.0%)"},
    }

    rate_info = royalty_rates.get(company_scale, royalty_rates["sme"])
    base_lump_sum = rate_info["lump_sum"] * (2.5 if is_exclusive else 1.0)
    running_rate = rate_info["running_rate"] * (1.5 if is_exclusive else 1.0)

    # 전용실시인 경우 지식재산처 고시 제9조 최소실시료 보장
    if is_exclusive and base_lump_sum < 3_000_000:
        base_lump_sum = 3_000_000

    # 필수 실무 특약 조항 (지식재산처 업무편람 표준서식 기준)
    mandatory_clauses = [
        {
            "clause": "전용실시 최소실시료 납부 의무 (지식재산처고시 제9조)",
            "detail": "전용실시권자는 실시료의 일부로서 300만 원 이상의 금액을 계약체결일로부터 60일 이내에 국고에 납부하여야 함",
            "practical_importance": "지식재산처 행정규칙 강행규정으로 미이행 시 계약 자동 해지 사유",
        },
        {
            "clause": "불실시 특약 (Due Diligence Clause)",
            "detail": "계약 체결일로부터 2년 이내에 정당한 사유 없이 제품 생산 또는 판매에 착수하지 아니한 경우 통보 후 즉시 해지 가능",
            "practical_importance": "특혜 시비 방지 및 잠자는 특허(Sleeping Patent) 방지",
        },
        {
            "clause": "재실시권(Sub-license) 제한",
            "detail": "실시권자는 지식재산처장(또는 수탁기관장)의 사전 서면 승인 없이 제3자에게 재실시권을 설정하거나 양도할 수 없음",
            "practical_importance": "기술 브로커의 중간 차익 편취 차단",
        },
        {
            "clause": "매출액 보고 및 장부 실사권 (Audit Rights)",
            "detail": "매 사업연도 종료 후 60일 이내에 공인회계사 확인 매출 보고서를 제출하며, 발명기관 및 수탁기관은 현장 회계장부 열람을 요구할 수 있음",
            "practical_importance": "경상기술료 누락 방지 및 감사원 감사 대비 필수",
        },
        {
            "clause": "전용실시 갱신 요건 사전 고지 (지식재산처고시 제10조)",
            "detail": "계약 갱신을 원할 경우 만료 30일 전까지 투자금 미회수 또는 인허가 시험 진행 등 법정 5대 사유 증빙을 갖추어 갱신 신청 필수",
            "practical_importance": "실시권자의 안정적인 사업화 기간 확보",
        },
    ]

    return {
        "patent_id": patent_id,
        "regulatory_framework": "지식재산처고시 제2025-4호 및 국유특허 처분관리 업무편람",
        "license_structure": {
            "type": "전용실시권 (Exclusive License)" if is_exclusive else "통상실시권 (Non-exclusive License)",
            "contract_period": f"{contract_period_years}년 (만료 30일 전 갱신 신청 가능)",
            "territory": target_territory,
            "field_of_use": "전 산업 분야 또는 지정 제품군 제조·판매",
        },
        "financial_terms": {
            "lump_sum_fee": f"{int(base_lump_sum):,}원 (계약 체결 후 60일 이내 납부)",
            "minimum_royalty_rule": "전용실시 최소실시료 300만원 충족 (제9조)",
            "running_royalty_rate": f"해당 제품 순매출액의 {running_rate * 100:.1f}%",
            "discount_policy": rate_info["desc"],
        },
        "mandatory_practice_clauses": mandatory_clauses,
        "registration_practice": (
            "전용실시권은 지식재산처 등록을 필하여야 효력이 발생하므로(특허법 제101조) 등록비용 부담 주체(실시권자)를 명시하십시오."
            if is_exclusive
            else "통상실시권은 등록 없이도 당사자 간 계약으로 유효합니다."
        ),
    }


def review_licensing_contract(
    contract_clauses: List[Dict[str, str]],
    is_public_patent: bool = True,
) -> Dict[str, Any]:
    """기술실시계약서 초안의 독소 조항, 필수 조항 누락 및 감사 리스크를 점검합니다."""
    check_results = []
    missing_critical_clauses = []

    joined_text = "\n".join([f"{c.get('title', '')}: {c.get('content', '')}" for c in contract_clauses])

    # 1. 전용실시 최소실시료(300만원/60일 이내) 점검
    if "전용" in joined_text:
        if "300" not in joined_text and "60일" not in joined_text:
            missing_critical_clauses.append("지식재산처고시 제9조에 따른 '최소실시료(300만 원 이상) 계약일로부터 60일 이내 납부' 규정이 누락되었습니다.")
        else:
            check_results.append("✅ 전용실시 최소실시료 납부 규정 확인 (고시 제9조)")

    # 2. 불실시 해지권 점검
    if "불실시" not in joined_text and "취소" not in joined_text and "해지" not in joined_text:
        missing_critical_clauses.append("불실시(2년 내 상용화 미착수)에 따른 발명기관의 일방 해지권 조항이 누락되었습니다.")
    else:
        check_results.append("✅ 불실시 해지 관련 조항 확인")

    # 3. 장부 열람권 점검
    if "경상" in joined_text or "매출" in joined_text:
        if "열람" not in joined_text and "실사" not in joined_text and "감사" not in joined_text:
            missing_critical_clauses.append("경상기술료 정산 검증을 위한 '회계장부 실사권'이 명시되지 않아 매출 축소 보고 시 제재가 어렵습니다.")
        else:
            check_results.append("✅ 회계장부 실사권 조항 확인")

    return {
        "audit_risk_level": "높음 (수정 권고)" if missing_critical_clauses else "안전 (체결 가능)",
        "verified_clauses": check_results,
        "critical_missing_or_toxic_risks": missing_critical_clauses,
        "practical_advice": (
            "지식재산처 업무편람에 따른 표준서식을 준수해야 지식재산처 계약 승인 및 감사원 감사 지적을 예방할 수 있습니다."
        ),
    }
