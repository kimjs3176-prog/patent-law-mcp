"""국가직무발명특허권등(국유특허) 처분·보상·수탁기관 업무 도구

근거: 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 규정(영)·시행규칙, 지식재산처 고시(업무 운영요령).
기준값과 조항 번호는 모두 정책 YAML(policies/kipo_notice_rules.yaml)에서 읽습니다.

- calculate_royalty_estimate: 실시료·매각 예정가격 (시행규칙 제11조)
- calculate_registration_compensation: 등록보상금 (영 제16조)
- plan_national_disposal: 처분 방식·계약기간·입찰 공고·제출 서류 판정 (영 제10조·제11조, 시행규칙 제5조~제9조)
- get_trustee_obligations: 수탁기관 업무 일정·의무 (고시 제15조~제19조, 시행규칙 제12조·제13조, 영 제18조)
- guide_national_dispute: 국유특허 심판·소송 대응 절차 (고시 제21조~제24조)
"""

import calendar
from datetime import date, timedelta
from statistics import mean
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import Field

from patent_law_mcp.policies.policy_manager import PolicyManager, policy_for, policy_manager
from patent_law_mcp.tools.employee_invention_practice import InventorShare, ReductionGround, apply_compensation_reduction


def _national() -> PolicyManager:
    return policy_manager if policy_manager.is_national else policy_for("national")


def _add_years(d: date, years: int) -> date:
    y = d.year + years
    return d.replace(year=y, day=min(d.day, calendar.monthrange(y, d.month)[1]))


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


# ---------------------------------------------------------------- 실시료·매각 예정가격
RoyaltyPurpose = Literal["license", "sale"]


def calculate_royalty_estimate(
    annual_factory_prices_krw: Annotated[List[Annotated[int, Field(gt=0)]], Field(min_length=1, max_length=30)],
    share_rate: Annotated[float, Field(gt=0, le=1)],
    annual_sales_quantities: Annotated[Optional[List[Annotated[int, Field(ge=0)]]], Field(max_length=30)] = None,
    base_rate: Annotated[Optional[float], Field(gt=0, le=0.1)] = None,
    purpose: RoyaltyPurpose = "license",
    license_type: Literal["non_exclusive", "exclusive"] = "non_exclusive",
    sme_relicense_after_free_license: bool = False,
    comparable_sale_prices_krw: Annotated[Optional[List[Annotated[int, Field(gt=0)]]], Field(max_length=20)] = None,
) -> Dict[str, Any]:
    """국유특허 실시료 예정가격(또는 매각 예정가격)을 시행규칙 제11조 산식으로 계산합니다.

    실시료 예정가격 = 총판매예정수량 × 제품의 판매단가 × 점유율 × 기본율
    - 총판매예정수량: 실시기간 중 매 연도별 판매예정수량의 합
    - 판매단가: 실시기간 중 매 연도별 공장도가격의 평균
    - 점유율: 단위 제품 생산에 해당 특허가 이용되는 비율
    - 기본율: 3% (실용적 가치·산업상 이용가능성을 고려해 2~4%)
    판매예정수량을 예측할 수 없으면 제품 단위당 실시료(판매단가 × 점유율 × 기본율)만 계산합니다.

    Args:
        annual_factory_prices_krw: 실시기간 중 연도별 공장도가격 (원, 연도 순서). 1개만 주면 전 기간 동일 가격으로 봄
        share_rate: 점유율 0~1 (예: 부품 원가 비중 등 근거로 산정한 0.3)
        annual_sales_quantities: 연도별 판매예정수량 (연도 순서). 비우면 단위당 실시료만 계산
        base_rate: 기본율 (비우면 3%). 2%~4% 범위 밖이면 오류
        purpose: "license"(전용·통상실시 실시료) 또는 "sale"(매각 — 존속기간 전체의 실시료 추정총액 기준)
        license_type: "non_exclusive"(통상실시) 또는 "exclusive"(전용실시, 최소실시료 비교)
        sme_relicense_after_free_license: 무상실시 종료 후 중소기업 재실시 요청이면 True (고시 제7조, 기본율 2%로 낮출 수 있음)
        comparable_sale_prices_krw: 매각에서 실시료 추정총액을 정할 수 없을 때 참고할 유사 특허 매매실례가격 (원)
    """
    pm = _national()
    art = pm.articles
    rule = pm.section("royalty_estimation")
    lo, hi = rule["base_rate_min"], rule["base_rate_max"]
    sme_rate = pm.section("unutilized_free_license")["sme_renewal_base_rate"]
    if not 0 < share_rate <= 1:
        raise ValueError("share_rate(점유율)는 0 초과 1 이하 소수로 입력하십시오 (예: 0.3).")
    if any(p <= 0 for p in annual_factory_prices_krw):
        raise ValueError("공장도가격은 0보다 커야 합니다.")

    if base_rate is None:
        rate = sme_rate if sme_relicense_after_free_license else rule["base_rate"]
        rate_note = (
            f"고시 제7조 중소기업 재실시 기본율 {sme_rate:.0%} ({art['sme_renewal_rate']})"
            if sme_relicense_after_free_license
            else f"기본율 {rule['base_rate']:.0%} ({art['royalty_estimation']} 제3항 제4호)"
        )
    else:
        allowed = lo - 1e-9 <= base_rate <= hi + 1e-9 or (sme_relicense_after_free_license and abs(base_rate - sme_rate) < 1e-9)
        if not allowed:
            raise ValueError(f"기본율은 {lo:.0%} 이상 {hi:.0%} 이하로 정할 수 있습니다 ({art['royalty_estimation']} 제3항 제4호). 입력: {base_rate:.2%}")
        rate = base_rate
        rate_note = f"입력 기본율 {base_rate:.2%} — 실용적 가치·산업상 이용가능성 등 조정 근거를 기록하십시오 ({art['royalty_estimation']} 제3항 제4호 단서)"

    unit_price = mean(annual_factory_prices_krw)
    unit_royalty = unit_price * share_rate * rate
    result: Dict[str, Any] = {
        "purpose": "매각 예정가격" if purpose == "sale" else "실시료 예정가격",
        "inputs": {
            "unit_price_krw": round(unit_price),
            "unit_price_basis": f"연도별 공장도가격 {len(annual_factory_prices_krw)}개 평균",
            "share_rate": share_rate,
            "base_rate": rate,
            "base_rate_basis": rate_note,
        },
        "unit_royalty_krw": round(unit_royalty),
        "unit_formula": f"{round(unit_price):,}원 × 점유율 {share_rate:g} × 기본율 {rate:.2%} = {round(unit_royalty):,}원/개",
    }
    warnings: List[str] = []

    if annual_sales_quantities:
        if len(annual_factory_prices_krw) not in (1, len(annual_sales_quantities)):
            raise ValueError("연도별 공장도가격과 판매예정수량의 연도 수가 다릅니다 (가격을 1개만 주면 전 기간 동일 가격으로 계산).")
        total_qty = sum(annual_sales_quantities)
        total = round(total_qty * unit_price * share_rate * rate)
        result.update({
            "total_sales_quantity": total_qty,
            "estimated_price_krw": total,
            "formula": f"총판매예정수량 {total_qty:,}개 × {round(unit_price):,}원 × {share_rate:g} × {rate:.2%} = {total:,}원",
            "basis": f"{art['royalty_estimation']} 제2항·제3항 (예정가격은 실시기간의 총액, 같은 조 제5항 본문)",
            "years_covered": len(annual_sales_quantities),
        })
    else:
        result.update({
            "estimated_price_krw": None,
            "basis": f"{art['royalty_estimation']} 제5항 단서 — 총판매예정수량을 예측할 수 없어 제품 단위당 실시료 예정가격으로 정함",
        })
        if purpose == "license":
            warnings.append("단위당 실시료로 계약하면 매출 보고·정산 조항(판매 수량 확인 방법)을 계약서에 넣으십시오.")

    if purpose == "sale":
        result["sale_price_rule"] = (
            f"매각 예정가격은 존속기간 실시료 추정총액을 기준으로 하고, 이를 정할 수 없으면 유사 특허권등의 매매실례가격을 기준으로 함 "
            f"({art['sale_price_basis']} 제1호·제2호). 연도별 판매예정수량은 남은 존속기간 전체를 입력하십시오."
        )
        if not annual_sales_quantities:
            if comparable_sale_prices_krw:
                result["comparable_sale_prices_krw"] = sorted(comparable_sale_prices_krw)
                result["comparable_range"] = f"{min(comparable_sale_prices_krw):,}원 ~ {max(comparable_sale_prices_krw):,}원"
                result["basis"] = f"{art['sale_price_basis']} 제2호 — 유사 특허권등 매매실례가격 (대표값 선택 근거는 별도 기록)"
            else:
                warnings.append(f"실시료 추정총액도 매매실례가격도 없으면 지식재산처장이 발명기관의 장과 협의하여 정합니다 ({art['royalty_estimation']} 제4항).")
        result["procedure"] = f"매각은 경쟁입찰이 원칙입니다 ({art['exclusive_competitive_bidding']})."

    if purpose == "license" and license_type == "exclusive":
        excl = pm.section("exclusive_licensing")
        minimum = excl["minimum_royalty_amount"]
        result["minimum_royalty"] = (
            f"전용실시권자는 실시료의 일부로 {minimum:,}원 이상을 계약일부터 {excl['payment_deadline_days']}일 이내 납부 ({art['exclusive_minimum_royalty']})"
        )
        total = result.get("estimated_price_krw")
        if total is not None and total < minimum:
            warnings.append(f"산정 총액 {total:,}원이 최소실시료 {minimum:,}원보다 적습니다. 최소실시료 이상으로 정하십시오.")

    result["checklist"] = [
        f"예정가격은 발명기관의 장이 낸 자료를 참작해 결정 ({art['opinion_hearing']}, 시행규칙 제10조 제1항)",
        "필요하면 특허 평가 전문기관의 평가 결과를 고려 (시행규칙 제10조 제2항)",
        "점유율 산정 근거(부품 원가 비중, 청구항 대응 기능 비중 등)를 기록",
    ]
    result["warnings"] = warnings
    result["legal_audit_basis"] = pm.audit_block("실시료", "요율")
    return result


# ---------------------------------------------------------------- 등록보상금
RightType = Literal["patent", "utility_model", "design"]
_RIGHT_LABEL = {"patent": "특허권", "utility_model": "실용신안권", "design": "디자인권"}


def calculate_registration_compensation(
    right_type: RightType,
    inventor_shares: Annotated[List[InventorShare], Field(min_length=1)],
    already_paid_for_same_invention: bool = False,
    number_of_rights: Annotated[int, Field(ge=1, le=100)] = 1,
    reduction_ground: ReductionGround = "none",
    withhold_all: bool = False,
) -> Dict[str, Any]:
    """국가직무발명특허권등 등록보상금 상한을 발명자 지분대로 나눕니다 (영 제16조).

    Args:
        right_type: "patent"(특허권), "utility_model"(실용신안권), "design"(디자인권)
        inventor_shares: 발명자별 지분 (0~1 소수, 합계 1)
        already_paid_for_same_invention: 같은 직무발명에 이미 등록보상금을 받았으면 True (한 번만 지급)
        number_of_rights: 등록된 권리 수 (서로 다른 직무발명의 권리마다 지급)
        reduction_ground: 고시 별표 1 감액 사유 — "none", "unauthorized_filing_after_report"(전액 미지급),
            "unreported_own_filing"(전액 미지급 또는 50%), "confidentiality_breach"(50%)
        withhold_all: unreported_own_filing에서 전액 미지급을 택하면 True
    """
    pm = _national()
    art = pm.articles
    if right_type not in _RIGHT_LABEL:
        raise ValueError(f"right_type은 {', '.join(_RIGHT_LABEL)} 중 하나여야 합니다.")
    shares = [s if isinstance(s, InventorShare) else InventorShare.model_validate(s) for s in inventor_shares]
    total_share = sum(s.share_rate for s in shares)
    if abs(total_share - 1.0) > 0.001:
        raise ValueError(f"지분 합계가 100%가 아닙니다 (현재 {total_share * 100:.1f}%).")
    per_right = pm.section("registration_compensation")[right_type]
    base = {
        "right_type": _RIGHT_LABEL[right_type],
        "regulatory_basis": f"{art['registration_compensation']} 제1항 (각 권리마다 {per_right:,}원 범위에서 예산 등을 고려해 고시로 정함)",
        "legal_audit_basis": pm.audit_block("감액"),
    }
    if already_paid_for_same_invention:
        return {**base, "payable": False, "total_compensation_krw": 0,
                "reason": f"등록보상금은 동일한 직무발명에 대하여 한 번만 지급합니다 ({art['registration_compensation']} 제2항)."}

    pool = per_right * number_of_rights
    reduce_ratio, reduction = apply_compensation_reduction(pm, reduction_ground, withhold_all)
    if reduction:
        reduction["before_reduction_krw"] = pool
        pool = int(pool * reduce_ratio)
    payouts = [int(pool * s.share_rate) for s in shares]
    payouts[max(range(len(shares)), key=lambda i: shares[i].share_rate)] += pool - sum(payouts)
    return {
        **base,
        "payable": pool > 0,
        "amount_is_upper_bound": True,
        "total_compensation_krw": pool,
        **({"reduction": reduction} if reduction else {}),
        "payment_table": [
            {"inventor_name": s.name, "share_rate": f"{s.share_rate * 100:.1f}%", "compensation_krw": p} for s, p in zip(shares, payouts)
        ],
        "checklist": [
            f"감액기준(별표 1) 해당 여부 확인 — 통지 전 자기 명의 출원·이전(전액 미지급), 미신고 출원·이전(전액 미지급 또는 50%), 비밀유지 위반(50%) ({art['compensation_reduction']})",
            "같은 직무발명에 대해 다른 권리(분할·변경 출원 등)로 이미 받았는지 확인",
            f"등록요청 서류(별지 제2호서식 등록요청서, 직무발명 의견서, 등록결정서·등록증 사본, 보상금 지급 서류) 구비 ({art['registration_request']})",
            f"직무발명보상금 비과세 한도 연 {pm.section('income_tax')['tax_free_limit_annual']:,}원 합산 확인 ({art['tax_free_limit']})",
        ],
    }


# ---------------------------------------------------------------- 처분 방식·절차 판정
DisposalType = Literal["non_exclusive", "exclusive", "sale"]
Handler = Literal["kipo", "trustee"]


def plan_national_disposal(
    disposal_type: DisposalType,
    free_ground: Annotated[Optional[int], Field(ge=1, le=4)] = None,
    private_contract_exception: Annotated[Optional[int], Field(ge=1, le=7)] = None,
    handled_by: Handler = "kipo",
    contract_start_date: Optional[date] = None,
    patent_expiry_date: Optional[date] = None,
    preparation_years: Annotated[int, Field(ge=0, le=10)] = 0,
    bid_date: Optional[date] = None,
    applicant_type: Literal["corporation", "individual", "no_business_registration"] = "corporation",
) -> Dict[str, Any]:
    """국유특허 처분 방식(유상·무상, 수의계약·경쟁입찰), 계약기간 상한, 입찰 공고 기한, 제출·확인 서류를 판정합니다.

    Args:
        disposal_type: "non_exclusive"(통상실시권 허락), "exclusive"(전용실시권 설정), "sale"(매각)
        free_ground: 무상 처분 사유 번호 1~4 (영 제10조 제2항 각 호). 유상이면 비움
        private_contract_exception: 전용실시·매각을 수의계약으로 하려는 경우 그 사유 번호 1~7 (영 제11조 제2항 단서 각 호)
        handled_by: "kipo"(지식재산처 직접) 또는 "trustee"(수탁기관)
        contract_start_date: 계약(예정)일 — 주면 계약기간 상한일을 계산
        patent_expiry_date: 존속기간 만료일 — 계약일부터 4년 이내 만료면 만료일까지 연장 가능
        preparation_years: 실시 준비기간(년). 1년 이상이면 그 기간만큼 연장 가능
        bid_date: 입찰(예정)일 — 주면 공고 마감일(30일 전)을 계산
        applicant_type: 처분받을 자 "corporation"(법인), "individual"(개인사업자), "no_business_registration"(사업자등록 없음)
    """
    pm = _national()
    art = pm.articles
    proc = pm.section("disposal_procedure")
    excl = pm.section("exclusive_licensing")
    exceptions = excl["private_contract_exceptions"]
    label = {"non_exclusive": "통상실시권 허락", "exclusive": "전용실시권 설정", "sale": "매각"}[disposal_type]
    warnings: List[str] = []
    steps: List[str] = []
    documents: List[str] = []

    if handled_by == "trustee" and disposal_type == "sale":
        raise ValueError(f"수탁기관의 위탁업무는 전용실시권 설정·통상실시권 허락과 홍보 등 관리입니다 ({art['trustee_scope']}). 매각은 지식재산처가 직접 처분합니다.")

    # 유상·무상
    if free_ground is not None:
        ground_text = proc["free_disposal_grounds"][free_ground - 1]
        consideration = f"무상 — {ground_text} ({art['free_disposal_grounds']})"
        if free_ground == 3:
            documents += [
                "무상실시 승인신청서 (시행규칙 별지 제3호서식)",
                "해당 국가직무발명특허권등의 실시에 관한 사업계획서",
                "무상실시를 하려는 사유서",
            ]
            steps.append(f"국가기관의 장이 지식재산처장에게 무상실시 승인 신청 ({art['free_use_by_state_agency']})")
        elif free_ground in (1, 2):
            documents.append("무상실시를 하려는 사유서 (수의계약신청서에 첨부)")
        else:
            warnings.append("제4호(국가시책 추진)는 지식재산처장이 필요하다고 인정해야 합니다. 인정 근거 문서를 확보하십시오.")
        if disposal_type != "non_exclusive":
            warnings.append("무상 사유는 처분 방법(경쟁입찰·수의계약) 요건을 대신하지 않습니다. 전용실시·매각의 수의계약 사유를 따로 확인하십시오.")
    else:
        consideration = f"유상 (원칙, {art['free_disposal_grounds']} 본문) — 예정가격은 calculate_royalty_estimate로 산정 ({art['royalty_estimation']})"

    # 처분 방법
    if disposal_type == "non_exclusive":
        method = f"수의계약 ({art['non_exclusive_private_contract']})"
        if private_contract_exception is not None:
            warnings.append("통상실시권은 원래 수의계약이므로 private_contract_exception은 필요 없습니다.")
    elif private_contract_exception is not None:
        method = f"수의계약 — 예외 사유: {exceptions[private_contract_exception - 1]} ({art['exclusive_competitive_bidding']} 단서)"
    else:
        method = f"경쟁입찰 ({art['exclusive_competitive_bidding']} 본문)"

    competitive = method.startswith("경쟁입찰")
    if competitive:
        steps.append(
            f"입찰일 {proc['bid_notice_days']}일 전까지 명칭·처분 종류·입찰 일시와 장소·참가 자격 등을 공고 — {proc['bid_notice_place']} ({art['bid_notice']})"
        )
        if disposal_type == "exclusive":
            documents.append(f"입찰자의 국유특허권 실시에 관한 사업계획서 ({art['exclusive_bidder_plan']} 제1항)")
            steps.append(f"사업계획서·사업화 가능성·특허 특성·입찰금액·위원회 심의 등을 고려해 전용실시권자 결정 ({art['exclusive_bidder_plan']} 제2항)")
    else:
        documents += [
            "수의계약신청서 (시행규칙 별지 제4호서식)",
            *[d for d in proc["private_contract_documents"] if not d.startswith("무상실시 사유서")],
        ]
        steps.append(f"수의계약신청서를 지식재산처장 또는 수탁기관의 장에게 제출 ({art['private_contract_application']})")

    steps.append(f"예정가격 결정·무상실시 조건 등에 관해 발명기관의 장 및 관계기관의 장 의견 청취 ({art['opinion_hearing']})")
    steps.append(f"계약서 작성 — 필수 기재: {', '.join(proc['contract_required_items'])} ({art['contract_items']} 제2항)")
    if handled_by == "trustee":
        steps.append(f"수탁기관은 기재사항을 갖춘 계약서와 신청서류로 지식재산처장 승인을 받고, 체결 후 완료문서 송부 ({art['trustee_contract_approval']} 제2항)")
        steps.append(f"처분결과 통지 — 계약서 사본 + {', '.join(proc['result_notice_items'])} ({art['disposal_result_notice']})")
    else:
        steps.append("처분 내용과 처분보상금 지급 사항을 발명기관의 장에게 통지 → 발명기관의 장이 발명자에게 통지 (영 제14조 제1항·제2항)")
    if disposal_type == "exclusive":
        steps.append(f"최소실시료 {excl['minimum_royalty_amount']:,}원 이상을 계약일부터 {excl['payment_deadline_days']}일 이내 납부 ({art['exclusive_minimum_royalty']})")
        steps.append(f"전용실시권 설정등록 ({art['exclusive_license_registration']})")

    identity = {
        "corporation": [proc["identity_checks"][0], proc["identity_checks"][2]],
        "individual": [proc["identity_checks"][1], proc["identity_checks"][2]],
        "no_business_registration": [proc["identity_checks"][2], proc["identity_checks"][3]],
    }[applicant_type]

    term: Dict[str, Any] = {"max_years_rule": f"{proc['max_contract_years']}년 이내 ({art['contract_term']} 본문)"}
    if disposal_type == "sale":
        term = {"max_years_rule": "해당 없음 (매각)"}
    elif contract_start_date:
        end = _add_years(contract_start_date, proc["max_contract_years"])
        reasons = []
        if preparation_years >= proc["preparation_extension_min_years"]:
            end = _add_years(end, preparation_years)
            reasons.append(f"준비기간 {preparation_years}년만큼 연장 ({art['contract_term']} 제1호)")
        if patent_expiry_date and patent_expiry_date <= _add_years(contract_start_date, proc["near_expiry_years"]):
            if patent_expiry_date > end:
                end = patent_expiry_date
            reasons.append(f"존속기간이 계약일부터 {proc['near_expiry_years']}년 이내 만료 → 만료 시까지 연장 가능 ({art['contract_term']} 제2호)")
        if patent_expiry_date and end > patent_expiry_date:
            end = patent_expiry_date
            reasons.append("존속기간 만료일을 넘길 수 없으므로 만료일로 제한")
        term.update({"contract_start_date": contract_start_date.isoformat(), "latest_end_date": end.isoformat(), "extensions": reasons})
    if preparation_years and preparation_years < proc["preparation_extension_min_years"]:
        warnings.append(f"준비기간이 {proc['preparation_extension_min_years']}년 미만이면 연장 사유가 아닙니다.")

    bid: Optional[Dict[str, Any]] = None
    if competitive and bid_date:
        bid = {"bid_date": bid_date.isoformat(), "notice_deadline": (bid_date - timedelta(days=proc["bid_notice_days"])).isoformat()}
    elif bid_date and not competitive:
        warnings.append("수의계약이므로 입찰 공고가 필요 없습니다.")

    return {
        "disposal": label,
        "handled_by": "수탁기관" if handled_by == "trustee" else "지식재산처",
        "consideration": consideration,
        "method": method,
        "contract_term": term,
        "bid_notice": bid,
        "procedure_steps": steps,
        "documents_from_applicant": documents,
        "identity_checks": {
            "items": identity,
            "how": "행정정보 공동이용으로 확인하고, 확인할 수 없거나 동의하지 않으면 서류 제출 (시행규칙 제9조 제3항)",
        },
        "private_contract_exceptions": exceptions if disposal_type != "non_exclusive" else [],
        "warnings": warnings,
        "legal_audit_basis": pm.audit_block("무상"),
    }


# ---------------------------------------------------------------- 수탁기관 업무
def get_trustee_obligations(
    as_of: Optional[date] = None,
    contract_end_dates: Annotated[Optional[List[date]], Field(max_length=200)] = None,
    organization_change_date: Optional[date] = None,
    disposal_income_krw: Annotated[Optional[int], Field(ge=0)] = None,
) -> Dict[str, Any]:
    """국유특허 수탁기관의 정기 보고·통지 기한과 처분 건별 의무를 정리합니다.

    Args:
        as_of: 기준일 (비우면 오늘) — 다가오는 분기 실적보고 기한을 계산
        contract_end_dates: 관리 중인 실시계약 만료일 목록 — 만료 후 정산 대상 표시
        organization_change_date: 수탁기관·조직 변경일 — 서면 통보 기한(30일) 계산
        disposal_income_krw: 처분수입금 — 기여보상금 상한(15%) 계산
    """
    pm = _national()
    art = pm.articles
    ob = pm.section("trustee_obligations")
    proc = pm.section("disposal_procedure")
    today = as_of or date.today()
    day = ob["quarterly_report_day"]

    reports = []
    for year in (today.year - 1, today.year, today.year + 1):
        for q in range(1, 5):
            quarter_end = date(year, q * 3, calendar.monthrange(year, q * 3)[1])
            due = _add_months(quarter_end.replace(day=1), 1).replace(day=day)
            reports.append({"quarter": f"{year}년 {q}분기", "quarter_end": quarter_end, "due": due})
    upcoming = [r for r in reports if r["due"] >= today][:4]
    last_quarter = max((r for r in reports if r["quarter_end"] < today), key=lambda r: r["quarter_end"])

    result: Dict[str, Any] = {
        "as_of": today.isoformat(),
        "quarterly_reports": [
            {"quarter": r["quarter"], "report_due": r["due"].isoformat(), "what": "처분·관리 실적보고서 + 처분·관리 대장 통지"} for r in upcoming
        ],
        "current_status": (
            f"{last_quarter['quarter']} 실적보고 기한 {last_quarter['due'].isoformat()}"
            + (" — 기한 경과, 제출 여부 확인" if last_quarter["due"] < today else " — 기한 전")
        ),
        "recurring_obligations": [
            f"분기 실적보고서를 다음 달 {day}일까지 지식재산처장에게 제출 ({art['quarterly_report']} 제1항)",
            f"처분·관리 대장 작성·비치, 분기별로 지식재산처장에게 통지 ({art['ledger']}) — 통지일은 규정에 없어 실적보고와 함께 보내는 방식 권장",
            f"실적보고 정확성을 위해 관련 자료를 체계적으로 구축·관리 ({art['quarterly_report']} 제3항)",
        ],
        "per_contract_obligations": [
            f"계약서 필수 기재: {', '.join(proc['contract_required_items'])} ({art['contract_items']} 제2항)",
            f"계약서·신청서류를 갖춰 지식재산처장 승인 후 체결, 체결 완료문서 송부 ({art['trustee_contract_approval']} 제2항)",
            f"처분결과 통지 — 계약서 사본 + {', '.join(proc['result_notice_items'])} ({art['disposal_result_notice']}, 영 제14조 제3항)",
            f"계약기간 만료 후 정산서류를 받아 정산하고 결과를 지식재산처에 송부해 실시료 납부고지서 발부 (계약상 선납분은 만료 전 발부 가능) ({art['trustee_settlement']})",
        ],
        "prohibitions": [
            f"정당한 실시료 외의 금전·물품을 실시자나 관련 제3자로부터 받을 수 없음 ({art['trustee_no_extra_payment']})",
            "법령에 따라 공정하게 처리하고, 공공성·투명성·권리자 보호에 노력 (고시 제15조 제3항·제4항)",
        ],
        "scope": f"위탁업무: 전용실시권 설정·통상실시권 허락, 국유특허 홍보 등 관리 ({art['trustee_scope']}). 매각은 위탁 대상 아님",
    }
    if contract_end_dates:
        ended = sorted(d for d in contract_end_dates if d < today)
        result["settlement_due"] = {
            "expired_contracts": [d.isoformat() for d in ended],
            "upcoming_expiries": sorted(d.isoformat() for d in contract_end_dates if d >= today),
            "action": "만료된 계약은 정산서류를 받아 정산 후 결과 송부" if ended else "만료된 계약 없음",
        }
    if organization_change_date:
        result["change_notice_due"] = {
            "change_date": organization_change_date.isoformat(),
            "deadline": (organization_change_date + timedelta(days=ob["change_notice_days"])).isoformat(),
            "basis": f"변경일부터 {ob['change_notice_days']}일 이내 서면 통보 ({art['trustee_change_notice']})",
        }
    if disposal_income_krw is not None:
        ratio = ob["contribution_compensation_max_ratio"]
        result["contribution_compensation"] = {
            "upper_bound_krw": int(disposal_income_krw * ratio),
            "basis": f"처분수입금의 100분의 {ratio * 100:g} 범위에서 예산 등을 고려해 고시로 정함 ({art['contribution_compensation']}). 실제 지급액은 지식재산처 결정",
        }
    result["legal_audit_basis"] = pm.audit_block("수탁")
    return result


# ---------------------------------------------------------------- 심판·소송
def guide_national_dispute(
    case_type: Literal["trial", "litigation"],
    trial_lost: bool = False,
) -> Dict[str, Any]:
    """국유특허(국가 명의 등록 산업재산권)에 심판이 청구되거나 특허법원 소송이 생겼을 때의 대응 절차를 안내합니다.

    Args:
        case_type: "trial"(특허심판) 또는 "litigation"(특허법원 전속관할 소송)
        trial_lost: 심결에서 패소했으면 True (소 제기 여부 협의 단계 안내)
    """
    pm = _national()
    art = pm.articles
    if case_type == "trial":
        steps = [
            "특허법·실용신안법·디자인보호법의 심판 규정 준용 (고시 제21조 제1항)",
            "심판청구서 부본이 지식재산처에 송달되면 지식재산처장이 발명기관의 장에게 통보 (같은 조 제2항)",
            "발명기관의 장이 심판당사자를 지정 — 발명자·관계자 의견서 제출 등 심판업무 총괄 대응 (같은 조 제3항)",
            "심판당사자는 대리인을 선임할 수 있고, 선임 즉시 특허심판원에 대리인 선임 신고 (고시 제22조)",
            "대리인 보수는 예산 범위에서 「변호사 보수 규정」(법무부훈령) 준용 (고시 제22조 제2항)",
            "심결문이 송달되면 지식재산처장이 즉시 발명기관의 장에게 통보 (고시 제21조 제4항)",
        ]
        if trial_lost:
            steps.append("패소한 경우 지식재산처장이 발명기관의 장과 협의하여 소 제기 여부 결정 (고시 제21조 제4항) — 소는 심결 등본을 송달받은 날부터 30일 이내(불변기간) 제기 (특허법 제186조 제3항·제4항)")
        basis = art["trial_procedure"]
    else:
        steps = [
            "「국가를 당사자로 하는 소송에 관한 법률」 준용 (고시 제23조 제1항)",
            "소장 부본이 지식재산처에 접수되면 지식재산처장이 발명기관의 장에게 통보, 발명기관의 장이 소송 수행 (같은 조 제2항)",
            "발명기관의 장은 법원 출석·변론·검찰청 보고 등 진행 상황을 지식재산처장에게 알림 (같은 조 제3항)",
            "변호사를 소송대리인으로 선임할 수 있고, 선임 즉시 지식재산처장에게 통보 (고시 제24조 제1항)",
            "대리인 보수는 예산 범위에서 「변호사 보수 규정」 준용 (고시 제24조 제2항)",
        ]
        basis = art["litigation_procedure"]
    return {"case_type": "특허심판" if case_type == "trial" else "특허법원 소송", "basis": basis, "steps": steps,
            "legal_audit_basis": pm.audit_block("심판")}
