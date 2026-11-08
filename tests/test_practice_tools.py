import pytest

from patent_law_mcp.tools.bundling_and_targeting import bundle_patents_for_transfer, find_target_licensees_by_patent
from patent_law_mcp.tools.claims_practice import verify_tech_transfer_scope_match
from patent_law_mcp.tools.contract_practice import design_licensing_terms, review_licensing_contract
from patent_law_mcp.tools.document_parser import get_bundled_sample_patent
from patent_law_mcp.tools.employee_invention_practice import (
    calculate_disposal_compensation,
    evaluate_exclusive_renewal,
    evaluate_unutilized_free_license,
)

GOOD_CONTRACT = """제2조(계약기간) 계약기간은 3년으로 한다. 실시지역은 대한민국, 실시분야는 식품 제조로 한다.
제3조(최소실시료) 을은 최소실시료로 금 3,000,000원을 계약체결일로부터 60일 이내에 납부한다.
제4조(해지) 을이 계약일부터 2년 이내에 정당한 사유 없이 사업화에 착수하지 아니한 경우 갑은 해지할 수 있다.
제5조(보고) 을은 매 사업연도 종료 후 60일 이내에 매출 보고서를 제출하며, 갑은 장부 열람을 요구할 수 있다.
제6조(재실시) 을은 갑의 사전 서면 승인 없이 재실시권을 설정할 수 없다.
제7조(등록) 전용실시권 등록 비용은 을이 부담한다."""


# ---------------------------------------------------------------- 처분보상금
def test_compensation_rejects_share_total_not_one():
    with pytest.raises(ValueError, match="지분 합계"):
        calculate_disposal_compensation(50_000_000, [{"name": "A", "share_rate": 0.7}, {"name": "B", "share_rate": 0.2}])


def test_compensation_rejects_percent_input():
    with pytest.raises(Exception):
        calculate_disposal_compensation(50_000_000, [{"name": "A", "share_rate": 70}, {"name": "B", "share_rate": 30}])


def test_compensation_totals_and_tax_split():
    r = calculate_disposal_compensation(
        50_000_000,
        [
            {"name": "A", "share_rate": 0.7},
            {"name": "B", "share_rate": 0.3, "employment_status": "retired", "tax_free_used_this_year_krw": 2_000_000},
        ],
        direct_expenses_krw=6_000_000,
    )
    assert r["total_compensation_krw"] == 22_000_000
    a, b = r["payment_table"]
    assert a["gross_compensation_krw"] + b["gross_compensation_krw"] == 22_000_000
    assert a["income_type"].startswith("근로소득") and a["estimated_tax_krw"] is None
    assert b["income_type"].startswith("기타소득")
    assert b["tax_free_krw"] == 5_000_000  # 연 700만 원 - 기수령 200만 원
    assert b["estimated_tax_krw"] == round(1_600_000 * 0.22)


def test_compensation_rounding_keeps_total():
    r = calculate_disposal_compensation(1_000_001, [{"name": n, "share_rate": 1 / 3} for n in "ABC"][:2] + [{"name": "C", "share_rate": 1 - 2 / 3}])
    assert sum(row["gross_compensation_krw"] for row in r["payment_table"]) == r["total_compensation_krw"]


# ---------------------------------------------------------------- 계약 설계·검토
def test_design_rejects_free_text_choices():
    with pytest.raises(ValueError):
        design_licensing_terms("x", license_type="전용실시")
    with pytest.raises(ValueError):
        design_licensing_terms("x", company_scale="중소기업")


def test_non_exclusive_has_no_exclusive_clauses_and_uses_sales():
    r = design_licensing_terms("x", "non_exclusive", "sme", expected_sales_annual=500_000_000)
    clauses = " ".join(c["clause"] for c in r["mandatory_practice_clauses"])
    assert "전용실시" not in clauses and "갱신" not in clauses
    assert r["financial_terms"]["estimated_annual_running_royalty_krw"] == 7_500_000


def test_exclusive_mentions_bidding_and_minimum_royalty():
    r = design_licensing_terms("x", "exclusive", "farmer")
    assert r["financial_terms"]["lump_sum_fee_krw"] == 3_000_000
    assert any("경쟁입찰" in p for p in r["required_procedures"])


def test_review_negations_are_not_pass():
    r = review_licensing_contract("갑은 최소실시료를 면제한다. 을이 불실시하더라도 갑은 해지할 수 없다. 매출 보고 의무는 없다.")
    status = {c["item"].split(" ")[0]: c["status"] for c in r["checklist"]}
    assert status["전용실시"] == "REVIEW" and status["불실시"] == "REVIEW" and status["매출"] == "REVIEW"
    assert not r["compliance_summary"].startswith("자동 점검 항목 이상 없음")


def test_review_good_contract_passes():
    r = review_licensing_contract(GOOD_CONTRACT)
    assert {c["status"] for c in r["checklist"]} == {"PASS"}


def test_review_amount_below_minimum_fails():
    r = review_licensing_contract(GOOD_CONTRACT.replace("3,000,000원", "1,000,000원"))
    assert r["compliance_summary"].startswith("수정 필요")


# ---------------------------------------------------------------- 무상실시·갱신
def test_free_license_large_company_gets_caution():
    r = evaluate_unutilized_free_license(5, "large", has_joint_patentee=True)
    assert r["eligible_for_free_license"] is True
    assert len(r["cautions"]) == 2


def test_free_license_not_eligible_before_threshold():
    assert evaluate_unutilized_free_license(2)["eligible_for_free_license"] is False


def test_renewal_does_not_claim_all_grounds():
    r = evaluate_exclusive_renewal(10, 5, 45)
    assert r["assessment"].startswith("자동 판정 사유 미충족")
    r = evaluate_exclusive_renewal(5, 10, 10)
    assert r["assessment"] == "신청 기한 경과"


# ---------------------------------------------------------------- 권리범위 대조
def test_scope_match_respects_negation():
    claim = get_bundled_sample_patent("sorting_machine")["claims"][0]
    r = verify_tech_transfer_scope_match(claim, "과채류 포장용 골판지 박스. 컨베이어 벨트 없이 수작업으로 포장하며 조명이나 센서부는 없음.")
    assert r["matched_elements"] == "0/4"
    assert "컨베이어" in r["verified_elements"][0]["negated_keywords"]


def test_scope_match_full():
    claim = get_bundled_sample_patent("sorting_machine")["claims"][0]
    spec = ("과채류를 컨베이어 모듈로 이송하면서 상부 조명부가 850nm 근적외선 광을 조사하고, 분광 센서부가 투과 광 스펙트럼으로 "
            "당도를 산출하여 솔레노이드 액추에이터가 등급별로 분류 배출하는 선별기")
    r = verify_tech_transfer_scope_match(claim, spec)
    assert r["matched_elements"] == "4/4"
    assert r["claimed_subject_matter"] == "과채류 비파괴 당도 선별 장치"


# ---------------------------------------------------------------- 번들링·타겟팅
def test_bundle_validation_and_roles():
    with pytest.raises(ValueError):
        bundle_patents_for_transfer("p", [{"patent_id": "1", "title": "선별 장치"}])
    r = bundle_patents_for_transfer("p", [{"patent_id": "1", "title": "선별 장치"}, {"patent_id": "2", "title": "추출물의 제조방법"}])
    assert [b["portfolio_role"] for b in r["bundled_patents"]] == ["장치 특허 (Apparatus)", "공정 특허 (Process)"]
    assert r["bundled_patents"][0]["applicant"] == "미기재"


def test_targeting_has_no_fabricated_figures_and_filters_size():
    r = find_target_licensees_by_patent("떡 제조", "A23L 7/10", preferred_company_size="startup")
    assert len(r["target_buyer_personas"]) == 1
    assert "18개월" not in str(r)
    unknown = find_target_licensees_by_patent("기타", None)
    assert unknown["matched_ksic_codes"] == []
