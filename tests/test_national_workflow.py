"""국가직무발명특허권 업무 도구 — 시행규칙·규정·고시 원문 수치 대조 테스트"""

from datetime import date

import pytest

from patent_law_mcp.tools.deadlines import check_portfolio_annuities
from patent_law_mcp.tools.employee_invention_practice import process_invention_disclosure
from patent_law_mcp.tools.national_disposal import (
    calculate_registration_compensation,
    calculate_royalty_estimate,
    get_trustee_obligations,
    guide_national_dispute,
    plan_national_disposal,
)


# ---------------------------------------------------------------- 실시료 예정가격 (시행규칙 제11조)
def test_royalty_formula_uses_average_factory_price():
    # 총판매예정수량 (1,000+2,000+3,000) × 평균 공장도가격 (10,000+12,000+14,000)/3 × 점유율 0.5 × 기본율 3%
    r = calculate_royalty_estimate([10_000, 12_000, 14_000], 0.5, [1_000, 2_000, 3_000])
    assert r["inputs"]["unit_price_krw"] == 12_000
    assert r["estimated_price_krw"] == 6_000 * 12_000 * 0.5 * 0.03 == 1_080_000
    assert r["unit_royalty_krw"] == 180
    assert "시행규칙 제11조" in r["basis"]


def test_royalty_unit_only_when_quantity_unknown():
    r = calculate_royalty_estimate([50_000], 0.2)
    assert r["estimated_price_krw"] is None and r["unit_royalty_krw"] == 300
    assert "제5항 단서" in r["basis"]


def test_royalty_base_rate_range_and_sme_relicense():
    with pytest.raises(ValueError, match="2% 이상 4% 이하"):
        calculate_royalty_estimate([10_000], 1.0, [100], base_rate=0.05)
    assert calculate_royalty_estimate([10_000], 1.0, [100], base_rate=0.04)["estimated_price_krw"] == 40_000
    sme = calculate_royalty_estimate([10_000], 1.0, [100], sme_relicense_after_free_license=True)
    assert sme["inputs"]["base_rate"] == 0.02 and "고시 제7조" in sme["inputs"]["base_rate_basis"]


def test_royalty_year_mismatch_and_exclusive_minimum():
    with pytest.raises(ValueError, match="연도 수"):
        calculate_royalty_estimate([1, 2], 0.5, [1, 2, 3])
    r = calculate_royalty_estimate([10_000], 0.5, [1_000], license_type="exclusive")
    assert any("최소실시료 3,000,000원" in w for w in r["warnings"])


def test_sale_price_falls_back_to_comparables():
    r = calculate_royalty_estimate([10_000], 0.5, purpose="sale", comparable_sale_prices_krw=[30_000_000, 10_000_000])
    assert r["comparable_range"] == "10,000,000원 ~ 30,000,000원"
    assert "제1항 제2호" in r["basis"] and "경쟁입찰" in r["procedure"]


# ---------------------------------------------------------------- 등록보상금 (영 제16조)
def test_registration_compensation_split_and_once_only():
    r = calculate_registration_compensation("patent", [{"name": "A", "share_rate": 0.6}, {"name": "B", "share_rate": 0.4}])
    assert r["total_compensation_krw"] == 500_000
    assert [row["compensation_krw"] for row in r["payment_table"]] == [300_000, 200_000]
    assert calculate_registration_compensation("design", [{"name": "A", "share_rate": 1.0}])["total_compensation_krw"] == 200_000
    again = calculate_registration_compensation("patent", [{"name": "A", "share_rate": 1.0}], already_paid_for_same_invention=True)
    assert again["payable"] is False and "한 번만" in again["reason"]


# ---------------------------------------------------------------- 처분 방식 (영 제10조·제11조, 시행규칙 제6조~제9조)
def test_non_exclusive_is_private_contract_with_documents():
    r = plan_national_disposal("non_exclusive", applicant_type="individual")
    assert r["method"].startswith("수의계약") and r["bid_notice"] is None
    assert r["documents_from_applicant"][0].startswith("수의계약신청서")
    assert any("견적서" in d for d in r["documents_from_applicant"])
    assert "사업자등록증명 (개인)" in r["identity_checks"]["items"]


def test_exclusive_bidding_notice_and_minimum_royalty():
    r = plan_national_disposal("exclusive", bid_date=date(2026, 12, 31))
    assert r["method"].startswith("경쟁입찰")
    assert r["bid_notice"]["notice_deadline"] == "2026-12-01"
    assert any("300만" in s or "3,000,000원" in s for s in r["procedure_steps"])
    assert any("고시 제8조" in d for d in r["documents_from_applicant"])
    ex = plan_national_disposal("exclusive", private_contract_exception=7)
    assert ex["method"].startswith("수의계약") and "유찰" in ex["method"]


def test_contract_term_extensions():
    base = plan_national_disposal("non_exclusive", contract_start_date=date(2026, 1, 1))
    assert base["contract_term"]["latest_end_date"] == "2029-01-01"
    prep = plan_national_disposal("non_exclusive", contract_start_date=date(2026, 1, 1), preparation_years=2)
    assert prep["contract_term"]["latest_end_date"] == "2031-01-01"
    near = plan_national_disposal("non_exclusive", contract_start_date=date(2026, 1, 1), patent_expiry_date=date(2029, 10, 1))
    assert near["contract_term"]["latest_end_date"] == "2029-10-01"
    capped = plan_national_disposal("exclusive", contract_start_date=date(2026, 1, 1), patent_expiry_date=date(2028, 6, 1))
    assert capped["contract_term"]["latest_end_date"] == "2028-06-01"


def test_free_ground_and_trustee_scope():
    r = plan_national_disposal("non_exclusive", free_ground=3)
    assert "무상" in r["consideration"] and any("별지 제3호서식" in d for d in r["documents_from_applicant"])
    farmer = plan_national_disposal("non_exclusive", free_ground=1)
    assert any("무상실시를 하려는 사유서" in d for d in farmer["documents_from_applicant"])
    with pytest.raises(ValueError, match="고시 제16조"):
        plan_national_disposal("sale", handled_by="trustee")
    t = plan_national_disposal("non_exclusive", handled_by="trustee")
    assert any("지식재산처장 승인" in s for s in t["procedure_steps"])


# ---------------------------------------------------------------- 수탁기관 (고시 제15조~제19조)
def test_trustee_calendar():
    r = get_trustee_obligations(
        as_of=date(2026, 11, 22),
        contract_end_dates=[date(2026, 6, 30), date(2027, 3, 31)],
        organization_change_date=date(2026, 11, 10),
        disposal_income_krw=10_000_000,
    )
    assert r["quarterly_reports"][0] == {"quarter": "2026년 4분기", "report_due": "2027-01-15", "what": "처분·관리 실적보고서 + 처분·관리 대장 통지"}
    assert r["current_status"].startswith("2026년 3분기 실적보고 기한 2026-10-15")
    assert r["change_notice_due"]["deadline"] == "2026-12-10"
    assert r["settlement_due"]["expired_contracts"] == ["2026-06-30"]
    assert r["contribution_compensation"]["upper_bound_krw"] == 1_500_000
    assert any("금전·물품" in p for p in r["prohibitions"])


def test_dispute_guide():
    trial = guide_national_dispute("trial", trial_lost=True)
    assert any("30일 이내" in s for s in trial["steps"]) and trial["basis"].startswith("고시 제21조")
    assert "국가를 당사자로 하는 소송" in guide_national_dispute("litigation")["steps"][0]


# ---------------------------------------------------------------- 신고 (시행규칙 제2조, 고시 제26조)
def test_national_disclosure_documents_and_applicant_name():
    r = process_invention_disclosure("발명", ["A"], profile="national")
    assert r["required_documents"][0].startswith("직무발명신고서")
    assert "1차 소속기관" in r["applicant_name_rule"]
    assert any("등록요청서" in s for s in r["administrative_steps"])


# ---------------------------------------------------------------- 연차료 일괄 점검
def test_portfolio_annuities_sorted_by_risk():
    r = check_portfolio_annuities(
        [
            {"patent_id": "OK", "registration_date": date(2024, 6, 1), "application_date": date(2022, 1, 1)},
            {"patent_id": "SOON", "registration_date": date(2023, 12, 20), "application_date": date(2021, 1, 1)},
            {"patent_id": "LATE", "registration_date": date(2023, 8, 1), "application_date": date(2021, 1, 1)},
        ],
        as_of=date(2026, 11, 22),
    )
    cats = {p["patent_id"]: p["category"] for p in r["patents"]}
    assert cats == {"OK": "정상", "SOON": "임박", "LATE": "추가납부기간"}
    assert [p["patent_id"] for p in r["patents"]] == ["LATE", "SOON", "OK"]


# ---------------------------------------------------------------- 감액기준 (고시 별표 1)
def test_reduction_table_from_annex1():
    one = [{"name": "A", "share_rate": 1.0}]
    r = calculate_registration_compensation("patent", one, reduction_ground="confidentiality_breach")
    assert r["total_compensation_krw"] == 250_000 and r["reduction"]["before_reduction_krw"] == 500_000
    none = calculate_registration_compensation("patent", one, reduction_ground="unauthorized_filing_after_report")
    assert none["total_compensation_krw"] == 0 and none["payable"] is False
    half = calculate_registration_compensation("patent", one, reduction_ground="unreported_own_filing")
    assert half["total_compensation_krw"] == 250_000
    assert calculate_registration_compensation("patent", one, reduction_ground="unreported_own_filing", withhold_all=True)["total_compensation_krw"] == 0


def test_disposal_compensation_reduction_national_only():
    from patent_law_mcp.tools.employee_invention_practice import calculate_disposal_compensation

    r = calculate_disposal_compensation(10_000_000, [{"name": "A", "share_rate": 1.0}], reduction_ground="confidentiality_breach")
    assert r["total_compensation_krw"] == 2_500_000 and "별표 1" in r["reduction"]["basis"]
    with pytest.raises(ValueError, match="national"):
        calculate_disposal_compensation(10_000_000, [{"name": "A", "share_rate": 1.0}], payout_ratio=0.5,
                                        profile="public_research", reduction_ground="confidentiality_breach")


# ---------------------------------------------------------------- 답변 품질 점검에서 찾은 문제 (회귀 방지)
def test_free_disposal_has_no_quote_or_compensation():
    r = plan_national_disposal("non_exclusive", free_ground=1)
    assert not any("견적서" in d for d in r["documents_from_applicant"])
    assert any("처분보상금(영 제17조)은 없음" in s for s in r["procedure_steps"])
    assert r["legal_audit_basis"]["unverified_items"] == []


def test_free_with_competitive_bidding_is_flagged():
    r = plan_national_disposal("sale", free_ground=2)
    assert any("경쟁입찰로 진행할 수 없습니다" in w for w in r["warnings"])
    assert not any("수의계약신청서에 첨부" in d for d in r["documents_from_applicant"])


def test_expiry_extension_only_when_it_extends():
    r = plan_national_disposal("exclusive", private_contract_exception=7, contract_start_date=date(2026, 12, 1),
                               patent_expiry_date=date(2029, 5, 10))
    ext = r["contract_term"]["extensions"]
    assert not any("제2호" in e for e in ext) and any("2029-05-10" in e for e in ext)


def test_sale_without_quantity_does_not_cite_unit_price_rule():
    r = calculate_royalty_estimate([30_000], 0.1, purpose="sale")
    assert "전용·통상실시에만 적용" in r["basis"]
    assert r["legal_audit_basis"]["unverified_items"] == []


def test_zero_payout_tax_note():
    from patent_law_mcp.tools.employee_invention_practice import calculate_disposal_compensation

    r = calculate_disposal_compensation(1_000_000, [{"name": "A", "share_rate": 1.0}],
                                        reduction_ground="unauthorized_filing_after_report")
    assert r["payment_table"][0]["tax_note"] == "지급액 없음"


# ---------------------------------------------------------------- 2차 답변 품질 점검 (회귀 방지)
def test_state_agency_free_use_is_approval_not_contract():
    r = plan_national_disposal("non_exclusive", free_ground=3, handled_by="trustee")
    assert r["method"].startswith("지식재산처장 승인")
    assert not any("수의계약신청서" in d for d in r["documents_from_applicant"])
    assert any("수탁기관 계약 절차가 아닙니다" in w for w in r["warnings"])


def test_free_trustee_notice_has_no_payment_items():
    r = plan_national_disposal("non_exclusive", free_ground=1, handled_by="trustee")
    notice = next(s for s in r["procedure_steps"] if s.startswith("처분결과 통지"))
    assert "처분보상금의 지급" not in notice and "대금 수납·처분보상금 사항 없음" in notice


def test_contract_review_reports_term_and_deadline():
    from patent_law_mcp.tools.contract_practice import review_licensing_contract

    r = review_licensing_contract("계약기간은 5년으로 한다. 최소실시료로 금 2,000,000원을 계약일부터 90일 이내 납부한다.")
    items = {c["item"].split(" (")[0]: c for c in r["checklist"]}
    fee = next(c for c in r["checklist"] if c["item"].startswith("전용실시 최소실시료"))
    assert "2,000,000원" in fee["comment"] and "90일" in fee["comment"]
    term = next(c for c in r["checklist"] if c["item"].startswith("계약기간 3년 이내"))
    assert term["status"] == "REVIEW" and "5년" in term["comment"]


def test_expired_patent_category_and_disclosure_deadline():
    r = check_portfolio_annuities(
        [{"patent_id": "old", "registration_date": date(2006, 1, 10), "application_date": date(2005, 3, 1), "paid_through_year": 20}],
        as_of=date(2026, 11, 22),
    )
    assert r["patents"][0]["category"] == "존속기간 만료"
    d = process_invention_disclosure("발명", ["A"], profile="national")
    assert "4개월 이내" in d["succession_rule"] and "영 제6조 제1항" in d["succession_rule"]


def test_disposal_comp_flags_regulation_floor():
    from patent_law_mcp.tools.employee_invention_practice import calculate_disposal_compensation

    r = calculate_disposal_compensation(3_000_000, [{"name": "A", "share_rate": 1.0}], direct_expenses_krw=5_000_000)
    assert "1,500,000원 이상" in r["regulation_floor_check"]
    ok = calculate_disposal_compensation(10_000_000, [{"name": "A", "share_rate": 1.0}])
    assert "regulation_floor_check" not in ok
