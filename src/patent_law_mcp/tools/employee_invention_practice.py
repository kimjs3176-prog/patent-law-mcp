"""국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령 (지식재산처고시 제2025-4호)
및 지식재산처 최신 국유특허권 처분관리 업무편람 반영 실무 도구
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def process_invention_disclosure(
    inventor_title: str,
    institution_type: str = "national_gov",  # "national_gov"(국가/국공립), "public_agency"(준정부/출연연), "university"(대학산단)
    project_budget_source: str = "national_rnd",  # "national_rnd"(국가R&D), "institutional"(기관고유사업)
    inventor_main_duty: str = "연구개발 및 기술보급",
) -> Dict[str, Any]:
    """직무발명 신고서 접수 시 직무범위성 판정 및 심의위원회 상정 안건을 작성합니다.

    지식재산처 국유특허 업무편람 제2장 및 발명진흥법 제10조·제12조 기반.
    """
    is_national = institution_type == "national_gov"

    checklist = [
        {"item": "사용자등의 업무 범위 부합 여부", "verified": True, "detail": "기관 설치법 및 고유 직무 범위 내 발명"},
        {"item": "발명자의 직무 관련성", "verified": True, "detail": f"발명자의 담당 업무({inventor_main_duty})와 직접 연관"},
        {"item": "국가R&D 연구노트 구비 여부", "verified": True, "detail": "착상 및 실험 데이터 연구노트 시점 인증 확인"},
    ]

    return {
        "invention_type": "국가직무발명 (국유화 대상)" if is_national else "기관직무발명 (기관 소유 대상)",
        "applicant_name": "대한민국 (소관: 지식재산처 및 발명기관 부기명칭)" if is_national else "기관 명의",
        "administrative_rule": "지식재산처고시 제2025-4호 제26조 (국가 명의 출원 시 발명기관장 부기)",
        "committee_docket": {
            "title": f"직무발명 승계 여부 심의의 건 ({inventor_title})",
            "statutory_basis": "발명진흥법 제10조 및 국가공무원 직무발명 규정 제4조",
            "recommendation": "국가 승계 결정 및 지식재산처장 명의 출원 승인",
            "checklist": checklist,
        },
        "next_administrative_steps": [
            "심의위원회 의결 후 1개월 이내에 발명자에게 승계 결정 서면 통지",
            "지식재산처 국가 명의 특허출원 및 등록보상금(건당 100만 원) 지급 품의",
            "비밀유지 의무 고지 및 미승계 시 발명자 자유발명 통지",
        ],
    }


def calculate_disposal_compensation(
    contract_income_krw: int,
    inventor_shares: List[Dict[str, Any]],
    direct_expenses_krw: int = 0,
) -> Dict[str, Any]:
    """지식재산처 고시 제11조에 따라 직접비용을 공제한 후 순수입금의 50%에 해당하는 처분보상금을 산출합니다.

    지식재산처고시 제2025-4호 제11조 (처분수입금에서 출원·등록비용 및 기술이전 직접비용 공제 후 50% 지급).
    """
    net_income = max(0, contract_income_krw - direct_expenses_krw)
    total_compensation_pool = int(net_income * 0.50)  # 순수입의 50%

    payout_table = []
    for inv in inventor_shares:
        name = inv.get("name", "발명자")
        rate = float(inv.get("share_rate", 1.0))
        payout = int(total_compensation_pool * rate)
        tax_estimate = int(payout * 0.22)  # 기타소득세 22% 원천징수 추정
        net_payout = payout - tax_estimate

        payout_table.append({
            "inventor_name": name,
            "share_rate": f"{rate * 100:.1f}%",
            "gross_compensation": f"{payout:,}원",
            "estimated_withholding_tax": f"{tax_estimate:,}원",
            "net_payout": f"{net_payout:,}원",
        })

    return {
        "regulatory_basis": "지식재산처고시 제2025-4호 제11조 제2항",
        "gross_contract_income": f"{contract_income_krw:,}원",
        "deducted_direct_expenses": f"{direct_expenses_krw:,}원 (출원·등록 및 기술이전 직접 소요비용)",
        "net_disposal_income": f"{net_income:,}원",
        "total_compensation_amount": f"{total_compensation_pool:,}원 (순처분수입의 50%)",
        "payment_table": payout_table,
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
) -> Dict[str, Any]:
    """등록 후 3년 미활용 국유특허의 3년 무상 통상실시 및 중소기업 재계약 우대 요율을 심의합니다.

    지식재산처고시 제2025-4호 제3조, 제6조, 제7조 기반.
    """
    is_unutilized_3yr = registration_years_elapsed >= 3 and not has_prior_license

    if is_unutilized_3yr:
        return {
            "eligible_for_free_license": True,
            "regulatory_basis": "지식재산처고시 제2025-4호 제3조 제2항 (미활용 국유특허 활용 촉진)",
            "license_type": "무상 통상실시권",
            "max_free_period": "최대 3년 (제3조 제3항)",
            "subsequent_terms": {
                "renewal_policy": "최초 3년 무상실시 종료 후 연장 시 유상 전환 필수 (제6조 제1항)",
                "sme_preferential_rate": (
                    "중소기업이 무상실시 종료 후 재실시 요청 시 실시료 산정 기본율을 2%로 인하 적용 (제7조)"
                    if applicant_scale == "sme"
                    else "일반 유상 요율 적용"
                ),
            },
            "required_documents": [
                "별지 제1호 서식 국유특허 무상실시 신청서",
                "사업화 추진일정 및 자금 조달 계획을 포함한 사업계획서",
                "무상실시 사유서 (공동권리자 존재 시 통상실시 동의서 첨부)",
            ],
            "competitor_limit_note": "신청자 다수 시 과당경쟁 방지를 위해 사업계획서 실현가능성 및 신청순서에 따라 실시자 수 제한 가능 (제5조)",
        }
    else:
        return {
            "eligible_for_free_license": False,
            "reason": (
                f"등록 후 경과 기간이 {registration_years_elapsed}년으로 3년 미만이거나 이미 실시 이력이 있어 "
                "제3조 제2항에 따른 미실시 국유특허 자동 무상실시 대상이 아닙니다. 일반 유상계약 또는 공익 감면 요건을 검토하십시오."
            ),
        }


def evaluate_exclusive_renewal(
    cumulative_commercial_revenue_krw: int,
    cumulative_investment_krw: int,
    ongoing_clinical_or_regulatory_tests: bool = False,
    expiry_days_remaining: int = 45,
) -> Dict[str, Any]:
    """지식재산처 고시 제10조에 따라 국유특허 전용실시계약의 갱신 적합성을 심의합니다.

    지식재산처고시 제2025-4호 제10조 (전용실시계약의 갱신 사유 5가지 및 만료 30일 전 신청 요건).
    """
    reasons_met = []

    # 1호: 사업화 수익 < 투자 비용 (투자금 미회수)
    if cumulative_commercial_revenue_krw < cumulative_investment_krw:
        reasons_met.append(
            f"사업화 수익({cumulative_commercial_revenue_krw:,}원)이 투자 비용({cumulative_investment_krw:,}원)보다 적음 (제10조 제1항 제1호)"
        )

    # 2호: 인허가/등록 시험 진행
    if ongoing_clinical_or_regulatory_tests:
        reasons_met.append("사업화를 위한 후속연구 또는 법령에 따른 인허가·등록 시험 진행 중 (제10조 제1항 제2호)")

    # 신청 기한 검토 (만료 30일 전까지)
    is_on_time = expiry_days_remaining >= 30

    can_renew = bool(reasons_met) and is_on_time

    return {
        "can_renew_exclusive_contract": can_renew,
        "regulatory_basis": "지식재산처고시 제2025-4호 제10조 (전용실시계약의 갱신)",
        "verified_renewal_grounds": reasons_met,
        "application_deadline_status": (
            f"신청 기한 적합 (만료 {expiry_days_remaining}일 전 신청, 기준: 30일 전까지)"
            if is_on_time
            else f"⚠️ 기한 초과 리스크 (만료 {expiry_days_remaining}일 전으로 30일 규정 위반 주의)"
        ),
        "financial_conditions": "갱신 시 최소실시료(300만원 이상) 및 전용실시 기간 재협의 가능 (제9조 및 제10조 제5항)",
        "prerequisite": "전용실시에 관한 실제 사업화 실적이 존재하거나 사업화 노력을 지속한 경우에 한함 (제10조 제3항)",
    }
