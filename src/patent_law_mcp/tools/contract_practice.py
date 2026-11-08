"""특허 기술이전 계약 실무 도구 (지식재산처고시 제2025-4호 및 국유특허 업무편람 반영)

주요 실무 기능:
- design_licensing_terms: 실시권 유형(전용/통상), 고시 기준 최소실시료(300만원/60일 이내), 선급·경상기술료율 산출
- review_licensing_contract: 계약서 초안 조항 검토 및 지식재산처 승인·감사 대비 리스크 체크리스트
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from patent_law_mcp.policies.policy_manager import policy_manager


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
    rules = policy_manager.exclusive_licensing_rules
    min_royalty = rules.get("minimum_royalty_amount", 3_000_000)
    deadline_days = rules.get("payment_deadline_days", 60)
    lump_multiplier = rules.get("exclusive_lump_sum_multiplier", 2.5)
    running_multiplier = rules.get("exclusive_running_multiplier", 1.5)

    # 기업 규모별 기술료율 정책 테이블 참조
    standard_rates = rules.get("standard_rates_by_scale", {
        "farmer": {"lump_sum": 0, "running_rate": 0.0, "description": "무상실시 대상 (고시 제3조)"},
        "sme": {"lump_sum": 3_000_000, "running_rate": 0.015, "description": "중소기업 우대 요율 (경상 1.5%~2.0%)"},
        "middle": {"lump_sum": 10_000_000, "running_rate": 0.025, "description": "중견기업 기준 요율 (경상 2.5%)"},
        "large": {"lump_sum": 30_000_000, "running_rate": 0.040, "description": "대기업 기준 요율 (경상 4.0%)"},
    })

    rate_info = standard_rates.get(company_scale, standard_rates.get("sme", {}))
    base_lump_sum = rate_info.get("lump_sum", 3_000_000) * (lump_multiplier if is_exclusive else 1.0)
    running_rate = rate_info.get("running_rate", 0.015) * (running_multiplier if is_exclusive else 1.0)

    # 전용실시인 경우 지식재산처 고시 제9조 최소실시료 보장
    if is_exclusive and base_lump_sum < min_royalty:
        base_lump_sum = min_royalty

    # 필수 실무 특약 조항 (지식재산처 업무편람 표준서식 기준)
    mandatory_clauses = [
        {
            "clause": f"전용실시 최소실시료 납부 의무 ({policy_manager.audit_trail_basis} 제9조)",
            "detail": f"전용실시권자는 실시료의 일부로서 {min_royalty:,}원 이상의 금액을 계약체결일로부터 {deadline_days}일 이내에 국고에 납부하여야 함",
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
            "clause": f"전용실시 갱신 요건 사전 고지 ({policy_manager.audit_trail_basis} 제10조)",
            "detail": "계약 갱신을 원할 경우 만료 30일 전까지 투자금 미회수 또는 인허가 시험 진행 등 법정 5대 사유 증빙을 갖추어 갱신 신청 필수",
            "practical_importance": "실시권자의 안정적인 사업화 기간 확보",
        },
    ]

    return {
        "patent_id": patent_id,
        "regulatory_framework": policy_manager.metadata.get("notice_name", "지식재산처 국유특허 처분관리 업무편람"),
        "legal_audit_basis": policy_manager.audit_trail_basis,
        "license_structure": {
            "type": "전용실시권 (Exclusive License)" if is_exclusive else "통상실시권 (Non-exclusive License)",
            "contract_period": f"{contract_period_years}년 (만료 30일 전 갱신 신청 가능)",
            "territory": target_territory,
            "field_of_use": "전 산업 분야 또는 지정 제품군 제조·판매",
        },
        "financial_terms": {
            "lump_sum_fee": f"{int(base_lump_sum):,}원 (계약 체결 후 {deadline_days}일 이내 납부)",
            "minimum_royalty_rule": f"전용실시 최소실시료 {min_royalty:,}원 충족 (제9조)" if is_exclusive else "해당 없음",
            "running_royalty_rate": f"해당 제품 순매출액의 {running_rate*100:.1f}%",
            "discount_policy": rate_info.get("description", "기준 요율 적용"),
        },
        "mandatory_practice_clauses": mandatory_clauses,
        "registration_practice": "전용실시권은 지식재산처 등록을 필하여야 효력이 발생하므로(특허법 제101조) 등록비용 부담 주체(실시권자)를 명시하십시오.",
    }


def review_licensing_contract(
    contract_text: str,
    license_type: str = "exclusive",
) -> Dict[str, Any]:
    """기술실시계약서 초안을 검토하여 지식재산처 승인 요건 및 사후 감사 지적 리스크를 분석합니다."""
    is_exclusive = license_type == "exclusive"
    rules = policy_manager.exclusive_licensing_rules
    min_royalty = rules.get("minimum_royalty_amount", 3_000_000)
    deadline_days = rules.get("payment_deadline_days", 60)

    checklist = []

    # 1. 전용실시 최소실시료 점검 (고시 제9조)
    if is_exclusive:
        has_min_royalty = ("300만" in contract_text or "3,000,000" in contract_text or "최소실시료" in contract_text)
        checklist.append({
            "item": f"전용실시 최소실시료({min_royalty:,}원 이상/{deadline_days}일 이내) 명시 여부",
            "status": "PASS" if has_min_royalty else "WARNING",
            "comment": (
                "지식재산처고시 제9조 강행규정 준수 확인"
                if has_min_royalty
                else f"최소실시료 {min_royalty:,}원 및 {deadline_days}일 이내 납부 조항이 누락되었습니다. 고시 위반으로 반려될 수 있습니다."
            ),
        })

    # 2. 불실시 해지 조항 점검
    has_due_diligence = ("불실시" in contract_text or "착수하지" in contract_text or "해지할 수 있다" in contract_text)
    checklist.append({
        "item": "불실시 해지특약(2년 내 미착수 시 해지) 포함 여부",
        "status": "PASS" if has_due_diligence else "WARNING",
        "comment": "잠자는 특허 방지 및 공공기술 활용 촉진을 위한 필수 조항입니다." if has_due_diligence else "불실시 해지권 조항 보완이 필요합니다.",
    })

    # 3. 회계 장부 실사권 점검
    has_audit = ("열람" in contract_text or "실사" in contract_text or "장부" in contract_text or "매출" in contract_text)
    checklist.append({
        "item": "매출액 보고 및 장부 실사권(Audit Rights) 포함 여부",
        "status": "PASS" if has_audit else "WARNING",
        "comment": "경상기술료 정산 투명성 및 감사원 감사 대비 필수 조항입니다." if has_audit else "장부 실사권 조항이 빠지면 사후 감사 시 지적 대상이 됩니다.",
    })

    return {
        "license_type": license_type,
        "legal_audit_basis": policy_manager.audit_trail_basis,
        "compliance_summary": "적합" if all(c["status"] == "PASS" for c in checklist) else "수정 권고",
        "checklist": checklist,
        "recommendation": "경고(WARNING) 항목이 있는 경우 지식재산처 업무편람 표준계약서 조항을 삽입하여 계약을 체결하십시오.",
    }
