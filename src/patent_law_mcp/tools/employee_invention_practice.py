"""직무발명 및 국유특허 처분·보상 실무 도구

기준값과 근거 조항은 모두 정책 YAML(policies/kipo_notice_rules.yaml)에서 읽습니다.
- process_invention_disclosure: 직무발명 신고 접수 및 심의 안건 초안
- calculate_disposal_compensation: 처분보상금 산출 및 발명자별 비과세·과세 구분
- evaluate_unutilized_free_license: 미활용 국유특허 무상 통상실시 검토
- evaluate_exclusive_renewal: 전용실시계약 갱신 검토
"""

from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from patent_law_mcp.policies.policy_manager import PolicyManager, ProfileName, policy_for, policy_manager
from patent_law_mcp.tools.contract_practice import require_choice


def process_invention_disclosure(
    title: str,
    inventor_names: Annotated[List[str], Field(min_length=1)],
    research_source: str = "국가 R&D 연구과제",
    has_prior_publication: bool = False,
    is_within_official_duties: bool = True,
    profile: Optional[ProfileName] = None,
) -> Dict[str, Any]:
    """직무발명 신고를 접수하고 승계 심의 안건 초안을 만듭니다 (국유특허·공공연구기관·민간 기업 프로파일).

    Args:
        title: 발명의 명칭
        inventor_names: 발명자 이름 목록
        research_source: 연구 재원 (예: "국가 R&D 연구과제")
        has_prior_publication: 출원 전 논문·학회 등으로 공개했는지 여부
        is_within_official_duties: 직무 범위 내 발명인지 여부
        profile: "national", "public_research", "private_company". 비우면 기본 프로파일
    """
    pm = policy_for(profile)
    if not inventor_names or not all(n.strip() for n in inventor_names):
        raise ValueError("발명자를 1명 이상 입력하십시오.")
    if not is_within_official_duties:
        return {
            "status": "자유발명 판정 검토",
            "legal_basis": "발명진흥법 제2조 제2호 (직무발명의 정의)",
            "action_required": "직무 범위 밖 발명이면 승계 대상이 아닙니다. 판단 근거를 기록하고 발명자에게 통지하십시오.",
        }

    authority = pm.metadata.get("competent_authority", "지식재산처")
    art = pm.articles
    novelty = (
        "출원 전 공개 이력이 있어 공지예외 주장(특허법 제30조, 공개일부터 12개월 이내 출원) 필요 여부를 검토하십시오."
        if has_prior_publication
        else "신고 기준 출원 전 공개 이력 없음 (발명자 확인 필요)"
    )
    if not pm.is_national:
        months = pm.section("invention_procedure")["succession_notice_months"]
        return {
            "status": "직무발명 신고 접수",
            "legal_basis": pm.metadata["parent_regulation"],
            "invention_title": title,
            "inventors": inventor_names,
            "rnd_source": research_source,
            "novelty_risk": novelty,
            "administrative_steps": [
                f"1. 발명 완성 사실 통지 접수 ({art['invention_report']})",
                f"2. 통지를 받은 날부터 {months}개월 이내에 승계 여부를 발명자에게 서면 통지 ({art['succession_notice']})",
                f"3. 승계 시 출원 진행, 보상은 {pm.metadata['notice_name']} 기준 ({art['disposal_compensation']})",
            ],
            "legal_audit_basis": pm.audit_block(),
        }

    reg = pm.section("registration_compensation")
    return {
        "status": "국가 승계 심의 대상 접수",
        "legal_basis": pm.metadata["parent_regulation"],
        "invention_title": title,
        "inventors": inventor_names,
        "rnd_source": research_source,
        "novelty_risk": novelty,
        "administrative_steps": [
            "1. 직무발명심의위원회 안건 상정 (직무 해당 여부·국가 승계 여부 의결)",
            f"2. {authority} 국유특허 출원 절차에 따라 출원 의뢰",
            f"3. 등록 시 등록보상금 지급 품의 (특허 {reg['patent']:,}원, {art['registration_compensation']})",
        ],
        "legal_audit_basis": pm.audit_block(),
    }


def _national() -> PolicyManager:
    """국유특허 전용 도구는 기본 매니저가 national이면 그것(사용자 지정 파일 포함)을, 아니면 national 프로파일을 씁니다."""
    return policy_manager if policy_manager.is_national else policy_for("national")


EmploymentStatus = Literal["employed", "retired"]


class InventorShare(BaseModel):
    name: str = Field(..., min_length=1, description="발명자 이름")
    share_rate: float = Field(..., gt=0, le=1, description="기여 지분 (0~1 소수, 예: 0.7)")
    employment_status: EmploymentStatus = Field("employed", description="수령 시점 신분: employed(재직) / retired(퇴직)")
    tax_free_used_this_year_krw: int = Field(0, ge=0, description="올해 이미 비과세 적용받은 직무발명보상금 (원)")
    marginal_income_tax_rate: Optional[float] = Field(
        None, ge=0, le=0.45, description="재직자 세액 추정용 한계 소득세율 (예: 0.24). 없으면 근로소득 세액은 추정하지 않음"
    )
    is_controlling_shareholder: bool = Field(False, description="지배주주 등 특수관계인 여부 (해당하면 비과세 제외)")


def calculate_disposal_compensation(
    contract_income_krw: Annotated[int, Field(ge=0)],
    inventor_shares: Annotated[List[InventorShare], Field(min_length=1)],
    direct_expenses_krw: Annotated[int, Field(ge=0)] = 0,
    payout_ratio: Annotated[Optional[float], Field(gt=0, le=1)] = None,
    deduct_direct_expenses: Optional[bool] = None,
    profile: Optional[ProfileName] = None,
) -> Dict[str, Any]:
    """기술료(처분·실시) 수입으로 발명자 보상금을 산출하고 발명자별 비과세·과세 금액을 나눕니다.

    지분(share_rate)은 0~1 소수로 입력하며 합계가 1이어야 합니다.
    세금: 재직 중 수령분은 근로소득(다른 급여와 합산 과세), 퇴직 후 수령분은 기타소득으로 구분하고,
    비과세 한도는 연간 합산 기준이므로 올해 이미 받은 비과세 금액을 빼고 적용합니다.

    Args:
        contract_income_krw: 처분수입금 (기술료 수입, 원)
        inventor_shares: 발명자별 지분·신분 정보
        direct_expenses_krw: 공제할 직접비용 (원, 정책상 공제 대상일 때만 반영)
        payout_ratio: 보상 비율 0~1 (비우면 프로파일 값, 프로파일 값이 없으면 필수)
        deduct_direct_expenses: 직접비용 공제 여부 (비우면 프로파일 값)
        profile: "national"(국유특허 처분보상금), "public_research", "private_company". 비우면 기본 프로파일
    """
    shares = [s if isinstance(s, InventorShare) else InventorShare.model_validate(s) for s in inventor_shares]
    if not shares:
        raise ValueError("발명자를 1명 이상 입력하십시오.")
    if contract_income_krw < 0 or direct_expenses_krw < 0:
        raise ValueError("수입금과 비용은 0 이상이어야 합니다.")
    total_share = sum(s.share_rate for s in shares)
    if abs(total_share - 1.0) > 0.001:
        raise ValueError(
            f"지분 합계가 100%가 아닙니다 (현재 {total_share * 100:.1f}%). 지분은 0~1 사이 소수로 입력하십시오 (예: 0.7, 0.3)."
        )

    pm = policy_for(profile)
    comp = pm.section("disposal_compensation")
    tax = pm.section("income_tax")
    art = pm.articles
    limit = tax["tax_free_limit_annual"]
    ratio = payout_ratio if payout_ratio is not None else comp["payout_ratio"]
    if ratio is None:
        raise ValueError(f"{pm.metadata['notice_name']}의 보상 비율을 payout_ratio로 입력하십시오 (예: 0.5). 정책 YAML에 넣어 두면 생략할 수 있습니다.")
    if not 0 < ratio <= 1:
        raise ValueError("payout_ratio는 0 초과 1 이하여야 합니다.")
    deduct = comp["deduct_direct_expenses"] if deduct_direct_expenses is None else deduct_direct_expenses

    if deduct:
        base = max(0, contract_income_krw - direct_expenses_krw)
        base_note = f"처분수입금 {contract_income_krw:,}원 − 직접비용 {direct_expenses_krw:,}원"
    else:
        base = contract_income_krw
        base_note = f"처분수입금 {contract_income_krw:,}원 (정책상 비용 공제 안 함)"
    pool = int(base * ratio)

    # 원 단위 내림 후 남는 금액은 지분이 가장 큰 발명자에게 더해 합계를 맞춘다
    payouts = [int(pool * s.share_rate) for s in shares]
    payouts[max(range(len(shares)), key=lambda i: shares[i].share_rate)] += pool - sum(payouts)

    table = []
    for s, payout in zip(shares, payouts):
        remaining_free = 0 if s.is_controlling_shareholder else max(0, limit - s.tax_free_used_this_year_krw)
        tax_free = min(payout, remaining_free)
        taxable = payout - tax_free
        row: Dict[str, Any] = {
            "inventor_name": s.name,
            "share_rate": f"{s.share_rate * 100:.1f}%",
            "gross_compensation_krw": payout,
            "tax_free_krw": tax_free,
            "taxable_krw": taxable,
        }
        if s.employment_status == "employed":
            row["income_type"] = "근로소득 (재직 중 수령)"
            if taxable and s.marginal_income_tax_rate is not None:
                income_tax = taxable * s.marginal_income_tax_rate
                row["estimated_tax_krw"] = int(round(income_tax * (1 + tax["local_income_tax_ratio"])))
                row["tax_note"] = f"한계세율 {s.marginal_income_tax_rate:.0%} + 지방소득세로 추정. 실제 세액은 급여 원천징수·연말정산에서 확정"
            else:
                row["estimated_tax_krw"] = None
                row["tax_note"] = "과세분은 다른 근로소득과 합산해 원천징수·연말정산 (세액 추정은 marginal_income_tax_rate 입력 시)" if taxable else "전액 비과세"
        else:
            row["income_type"] = "기타소득 (퇴직 후 수령)"
            row["estimated_tax_krw"] = int(round(taxable * tax["retired_withholding_rate"]))
            row["tax_note"] = (
                f"과세분 원천징수 {tax['retired_withholding_rate']:.0%} (소득세+지방소득세). 다른 기타소득과 합산해 종합과세될 수 있음"
                if taxable
                else "전액 비과세"
            )
        if s.is_controlling_shareholder:
            row["tax_note"] = "지배주주 등 특수관계인은 직무발명보상금 비과세 제외. " + row["tax_note"]
        row["net_payout_krw"] = payout - (row["estimated_tax_krw"] or 0)
        table.append(row)

    return {
        "regulatory_basis": art["disposal_compensation"],
        "compensation_base_krw": base,
        "compensation_base_note": base_note,
        "payout_ratio": ratio,
        "payout_ratio_source": "호출 시 입력" if payout_ratio is not None else "정책 YAML",
        "total_compensation_krw": pool,
        "payment_table": table,
        "tax_basis": f"{art['tax_free_limit']} — 직무발명보상금 비과세 한도 연 {limit:,}원 (재직·퇴직 수령분 합산)",
        "administrative_checklist": [
            "처분수입금 세입 조치 증빙 첨부",
            "발명자 전원의 지분 합의서 대조",
            "올해 이미 지급된 직무발명보상금(비과세 적용분) 확인",
            "보상금 감액 사유 해당 여부 점검",
        ],
        "legal_audit_basis": pm.audit_block(),
    }


ApplicantScale = Literal["farmer", "sme", "middle", "large"]


def evaluate_unutilized_free_license(
    registration_years_elapsed: Annotated[int, Field(ge=0)],
    applicant_scale: ApplicantScale = "sme",
    has_prior_license: bool = False,
    has_joint_patentee: bool = False,
) -> Dict[str, Any]:
    """등록 후 일정 기간 실시되지 않은 국유특허의 무상 통상실시 해당 여부를 검토합니다.

    Args:
        registration_years_elapsed: 등록 후 경과 연수
        applicant_scale: 신청자 규모 ("farmer", "sme", "middle", "large")
        has_prior_license: 그동안 실시(계약) 이력이 있는지 여부
        has_joint_patentee: 민간 공동권리자가 있는지 여부
    """
    require_choice(applicant_scale, ("farmer", "sme", "middle", "large"), "applicant_scale")
    if registration_years_elapsed < 0:
        raise ValueError("registration_years_elapsed는 0 이상이어야 합니다.")

    pm = _national()
    rules = pm.section("unutilized_free_license")
    art = pm.articles
    threshold, max_years = rules["unutilized_years_threshold"], rules["max_free_license_years"]

    if registration_years_elapsed < threshold or has_prior_license:
        reason = (
            f"등록 후 {registration_years_elapsed}년으로 기준({threshold}년)에 못 미칩니다."
            if registration_years_elapsed < threshold
            else "실시(계약) 이력이 있어 미활용 특허 요건에 해당하지 않습니다."
        )
        return {
            "eligible_for_free_license": False,
            "reason": reason,
            "alternatives": f"유상 통상실시 또는 무상 처분 사유({art['free_disposal_grounds']}) 해당 여부를 검토하십시오.",
            "legal_audit_basis": pm.audit_block(),
        }

    cautions = []
    if has_joint_patentee and rules["joint_patentee_written_consent_required"]:
        cautions.append(
            f"민간 공동권리자가 있으므로 공동권리자의 통상실시 서면 동의서가 필요합니다 ({art['joint_patentee_consent']}). "
            "민간 지분의 실시료는 별도 협의하십시오."
        )
    if applicant_scale in ("middle", "large"):
        cautions.append("중견·대기업 신청이 무상실시 대상에 포함되는지는 고시 원문으로 확인하십시오.")

    return {
        "eligible_for_free_license": True,
        "regulatory_basis": f"{art['free_license']} (미활용 국유특허 활용 촉진)",
        "license_type": "무상 통상실시권",
        "max_free_period": f"최대 {max_years}년",
        "ownership_check": "민간 공동권리자 있음" if has_joint_patentee else "국가 단독 소유 (신청 시 등록원부로 확인)",
        "cautions": cautions,
        "subsequent_terms": {
            "after_free_period": f"무상 기간 종료 후 계속 실시하려면 유상 전환 ({art['free_license_paid_conversion']})",
            "sme_preferential_rate": (
                f"중소기업 재계약 시 실시료 기본율 {rules['sme_renewal_base_rate_reduction_pp']}%p 인하 ({art['sme_renewal_rate']})"
                if applicant_scale == "sme"
                else "일반 유상 요율 적용"
            ),
        },
        "required_documents": [
            "국유특허 무상실시 신청서 (고시 별지 서식)",
            "사업화 추진 일정과 자금 조달 계획을 담은 사업계획서",
            "공동권리자가 있으면 통상실시 서면 동의서",
        ],
        "licensee_limit_note": f"신청자가 많으면 사업계획의 실현 가능성 등으로 실시자 수를 제한할 수 있음 ({art['licensee_limit']})",
        "legal_audit_basis": pm.audit_block(),
    }


def evaluate_exclusive_renewal(
    cumulative_commercial_revenue_krw: Annotated[int, Field(ge=0)],
    cumulative_investment_krw: Annotated[int, Field(ge=0)],
    expiry_days_remaining: int,
    ongoing_clinical_or_regulatory_tests: bool = False,
) -> Dict[str, Any]:
    """국유특허 전용실시계약의 갱신 가능성을 검토합니다.

    자동 판정하는 갱신 사유는 (1) 사업화 수익이 투자 비용보다 적은 경우, (2) 인허가·등록 시험 진행 중인 경우 두 가지입니다.
    고시의 다른 갱신 사유는 자동 판정하지 않으므로 해당하면 별도로 검토하십시오.

    Args:
        cumulative_commercial_revenue_krw: 누적 사업화 수익 (원)
        cumulative_investment_krw: 누적 투자 비용 (원)
        expiry_days_remaining: 계약 만료까지 남은 일수 (이미 지났으면 음수)
        ongoing_clinical_or_regulatory_tests: 인허가·등록 시험 진행 여부
    """
    if cumulative_commercial_revenue_krw < 0 or cumulative_investment_krw < 0:
        raise ValueError("수익과 투자 비용은 0 이상이어야 합니다.")

    pm = _national()
    art = pm.articles
    deadline = pm.section("exclusive_renewal")["application_deadline_days_before_expiry"]
    min_royalty = pm.section("exclusive_licensing")["minimum_royalty_amount"]

    grounds = []
    if cumulative_commercial_revenue_krw < cumulative_investment_krw:
        grounds.append(
            f"사업화 수익({cumulative_commercial_revenue_krw:,}원)이 투자 비용({cumulative_investment_krw:,}원)보다 적음"
        )
    if ongoing_clinical_or_regulatory_tests:
        grounds.append("사업화를 위한 인허가·등록 시험 진행 중")

    on_time = expiry_days_remaining >= deadline
    if not on_time:
        assessment = "신청 기한 경과"
    elif grounds:
        assessment = "자동 판정 사유 충족"
    else:
        assessment = "자동 판정 사유 미충족 — 고시의 다른 갱신 사유 해당 여부 검토 필요"

    return {
        "assessment": assessment,
        "regulatory_basis": f"{art['exclusive_renewal']} (전용실시계약의 갱신)",
        "verified_renewal_grounds": grounds,
        "unchecked_grounds_note": "수익·투자 비교와 인허가 시험 외의 갱신 사유는 자동 판정하지 않습니다.",
        "application_deadline_status": (
            f"기한 내 (만료 {expiry_days_remaining}일 전, 기준: {deadline}일 전까지 신청)"
            if on_time
            else f"기한 경과 (만료 {expiry_days_remaining}일 전, 기준: {deadline}일 전까지 신청)"
        ),
        "contract_method": f"갱신 재계약은 경쟁입찰 예외로 수의계약 가능 ({art['exclusive_renewal_private_contract']})",
        "financial_conditions": f"갱신 시에도 전용실시 최소실시료({min_royalty:,}원 이상) 기준 적용 ({art['exclusive_minimum_royalty']})",
        "legal_audit_basis": pm.audit_block(),
    }
