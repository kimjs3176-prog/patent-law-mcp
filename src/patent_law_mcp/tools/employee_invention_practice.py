"""직무발명 및 국유특허 처분 실무 도구 (지식재산처고시 제2025-4호 및 국유특허 업무편람 반영)

주요 실무 기능:
- process_invention_disclosure: 직무발명 신고 및 승계 심의 안건 작성
- calculate_disposal_compensation: 직접비용 공제 후 순수입 50% 처분보상금 산출 및 소득세 비과세 한도 적용
- evaluate_unutilized_free_license: 등록 후 3년 미실시 국유특허 무상실시 및 중소기업 재계약 우대 심의
- evaluate_exclusive_renewal: 전용실시 갱신 법정 5대 사유 및 만료 30일 전 신청 요건 심의
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from patent_law_mcp.policies.policy_manager import policy_manager


def process_invention_disclosure(
    title: str,
    inventor_names: List[str],
    research_source: str = "국가 R&D 연구과제",
    has_prior_publication: bool = False,
    is_within_official_duties: bool = True,
) -> Dict[str, Any]:
    """국가공무원 및 공공연구기관 연구원의 직무발명 신고서를 심의 안건으로 접수하고 처분 요건을 검토합니다."""
    if not is_within_official_duties:
        return {
            "status": "자유발명 판정 권고",
            "legal_basis": "발명진흥법 제10조 (직무범위 외 발명)",
            "action_required": "직무발명 승계 불가. 발명자 개인 권리 귀속 통보서 발송",
        }

    return {
        "status": "국가승계(국유특허) 심의 대상 접수 완료",
        "legal_basis": f"{policy_manager.audit_trail_basis} (직무발명의 승계)",
        "invention_title": title,
        "inventors": inventor_names,
        "rnd_source": research_source,
        "novelty_risk": "공지예외주장 출원(특허법 제30조) 필수 검토" if has_prior_publication else "신규성 상실 위험 없음",
        "administrative_steps": [
            "1. 직무발명심의위원회 안건 상정 (직무기여도 및 국가승계 여부 의결)",
            "2. 특허청 국유특허 대리인(전담 변리사) 지정 및 출원 의뢰",
            "3. 출원등록보상금(지식재산특별회계) 지급 품의 진행",
        ],
    }


def calculate_disposal_compensation(
    contract_income_krw: int,
    direct_expenses_krw: int,
    inventor_shares: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """지식재산처 고시 제11조 및 소득세법에 따라 국유특허 처분수입금 중 순수입의 50%를 처분보상금으로 산출합니다."""
    comp_rules = policy_manager.disposal_compensation_rules
    payout_ratio = comp_rules.get("net_income_payout_ratio", 0.50)
    tax_free_limit = comp_rules.get("tax_free_limit_annual", 7_000_000)

    net_income = max(0, contract_income_krw - direct_expenses_krw)
    total_compensation_pool = int(round(net_income * payout_ratio))

    payout_table = []
    for inv in inventor_shares:
        name = inv.get("name", "발명자")
        rate = float(inv.get("share_rate", 1.0))
        payout = int(round(total_compensation_pool * rate))

        # 세무 처리 가이드 (비과세 초과분에 대해 기타소득세 22% 원천징수)
        taxable_amount = max(0, payout - tax_free_limit)
        tax_estimate = int(round(taxable_amount * 0.22))
        net_payout = payout - tax_estimate

        payout_table.append({
            "inventor_name": name,
            "share_rate": f"{rate * 100:.1f}%",
            "gross_compensation": f"{payout:,}원",
            "tax_free_portion": f"{min(payout, tax_free_limit):,}원 (비과세 한도 적용)",
            "estimated_withholding_tax": f"{tax_estimate:,}원 (초과분 기타소득세 22%)",
            "net_payout": f"{net_payout:,}원",
        })

    return {
        "regulatory_basis": f"{policy_manager.audit_trail_basis} 제11조 제2항",
        "gross_contract_income": f"{contract_income_krw:,}원",
        "deducted_direct_expenses": f"{direct_expenses_krw:,}원 (출원·등록 및 기술이전 직접 소요비용)",
        "net_disposal_income": f"{net_income:,}원",
        "total_compensation_amount": f"{total_compensation_pool:,}원 (순처분수입의 {int(payout_ratio*100)}%)",
        "payment_table": payout_table,
        "tax_note": f"소득세법 제12조에 따른 직무발명보상금 비과세 한도(연간 {tax_free_limit:,}원)를 반영한 실무 세액 추정치입니다.",
        "administrative_checklist": [
            "지식재산특별회계 국고 세입 조치 영수증 첨부",
            "발명자 전원 기여율 합의서 대조 확인",
            "별표 1 '보상금등의 감액기준' 해당 여부 점검 (부실출원 등 감액 사유)",
        ],
    }


def evaluate_unutilized_free_license(
    registration_years_elapsed: int,
    applicant_scale: str = "sme",  # "sme", "farmer", "large"
    has_prior_license: bool = False,
    has_joint_patentee: bool = False,  # 민간 공동출원인 존재 여부
) -> Dict[str, Any]:
    """등록 후 3년 미활용 국유특허의 3년 무상 통상실시 및 중소기업 재계약 우대 요율을 심의합니다."""
    free_rules = policy_manager.unutilized_free_rules
    threshold = free_rules.get("unutilized_years_threshold", 3)
    max_years = free_rules.get("max_free_license_years", 3)
    discount_rate = free_rules.get("sme_renewal_discount_rate", 0.02)

    is_unutilized = registration_years_elapsed >= threshold and not has_prior_license

    if is_unutilized:
        joint_owner_guidance = (
            "⚠️ 공동권리자 주의: 본 특허에 민간 기업 등 공동권리자가 존재할 경우, 고시 제4조 제4항에 따라 "
            "반드시 '공동권리자의 통상실시 서면 동의서'를 첨부해야 하며, 민간 지분에 대한 기술료는 별도 협의해야 합니다."
            if has_joint_patentee
            else "단독 소유: 국가 단독 소유 특허로서 지식재산처 단독 처분 가능"
        )

        return {
            "eligible_for_free_license": True,
            "regulatory_basis": f"{policy_manager.audit_trail_basis} 제3조 제2항 (미활용 국유특허 활용 촉진)",
            "license_type": "무상 통상실시권",
            "max_free_period": f"최대 {max_years}년 (제3조 제3항)",
            "joint_patentee_check": joint_owner_guidance,
            "subsequent_terms": {
                "renewal_policy": f"최초 {max_years}년 무상실시 종료 후 연장 시 유상 전환 필수 (제6조 제1항)",
                "sme_preferential_rate": (
                    f"중소기업이 무상실시 종료 후 재실시 요청 시 실시료 산정 기본율을 {int(discount_rate*100)}%로 인하 적용 (제7조)"
                    if applicant_scale == "sme"
                    else "일반 유상 요율 적용"
                ),
            },
            "required_documents": [
                "별지 제1호 서식 국유특허 무상실시 신청서",
                "사업화 추진일정 및 자금 조달 계획을 포함한 사업계획서",
                "무상실시 사유서 (공동권리자 존재 시 통상실시 동의서 필수)",
            ],
            "competitor_limit_note": "신청자 다수 시 과당경쟁 방지를 위해 사업계획서 실현가능성 및 신청순서에 따라 실시자 수 제한 가능 (제5조)",
        }
    else:
        return {
            "eligible_for_free_license": False,
            "reason": (
                f"등록 후 경과 기간이 {registration_years_elapsed}년으로 {threshold}년 미만이거나 이미 실시 이력이 있어 "
                "제3조 제2항에 따른 미실시 국유특허 자동 무상실시 대상이 아닙니다. 일반 유상계약 또는 공익 감면 요건을 검토하십시오."
            ),
        }


def evaluate_exclusive_renewal(
    cumulative_commercial_revenue_krw: int,
    cumulative_investment_krw: int,
    ongoing_clinical_or_regulatory_tests: bool = False,
    expiry_days_remaining: int = 45,
) -> Dict[str, Any]:
    """지식재산처 고시 제10조에 따라 국유특허 전용실시계약의 갱신 적합성을 심의합니다."""
    renewal_rules = policy_manager.exclusive_renewal_rules
    deadline_days = renewal_rules.get("application_deadline_days_before_expiry", 30)

    reasons_met = []

    # 1호: 사업화 수익 < 투자 비용
    if cumulative_commercial_revenue_krw < cumulative_investment_krw:
        reasons_met.append(
            f"사업화 수익({cumulative_commercial_revenue_krw:,}원)이 투자 비용({cumulative_investment_krw:,}원)보다 적음 (제10조 제1항 제1호)"
        )

    # 2호: 인허가/등록 시험 진행
    if ongoing_clinical_or_regulatory_tests:
        reasons_met.append("사업화를 위한 후속연구 또는 법령에 따른 인허가·등록 시험 진행 중 (제10조 제1항 제2호)")

    is_on_time = expiry_days_remaining >= deadline_days
    can_renew = bool(reasons_met) and is_on_time

    return {
        "can_renew_exclusive_contract": can_renew,
        "regulatory_basis": f"{policy_manager.audit_trail_basis} 제10조 (전용실시계약의 갱신)",
        "verified_renewal_grounds": reasons_met,
        "application_deadline_status": (
            f"신청 기한 적합 (만료 {expiry_days_remaining}일 전 신청, 기준: {deadline_days}일 전까지)"
            if is_on_time
            else f"⚠️ 기한 초과 리스크 (만료 {expiry_days_remaining}일 전으로 {deadline_days}일 규정 위반 주의)"
        ),
        "financial_conditions": "갱신 시 최소실시료(300만원 이상) 및 전용실시 기간 재협의 가능 (제9조 및 제10조 제5항)",
        "prerequisite": "전용실시에 관한 실제 사업화 실적이 존재하거나 사업화 노력을 지속한 경우에 한함 (제10조 제3항)",
    }
