import asyncio
import os
import shutil
import time

import pytest
import yaml

from patent_law_mcp.policies.policy_manager import DEFAULT_POLICY_FILE, PolicyError, PolicyManager, validate_policy
from patent_law_mcp.server import mcp


def test_bundled_policy_is_valid():
    assert validate_policy(yaml.safe_load(DEFAULT_POLICY_FILE.read_text(encoding="utf-8"))) == []


def test_missing_key_fails_loudly(tmp_path):
    policy = yaml.safe_load(DEFAULT_POLICY_FILE.read_text(encoding="utf-8"))
    del policy["exclusive_licensing"]["minimum_royalty_amount"]
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump(policy, allow_unicode=True), encoding="utf-8")
    with pytest.raises(PolicyError, match="minimum_royalty_amount"):
        PolicyManager(path).policy


def test_policy_reloads_when_file_changes(tmp_path):
    path = tmp_path / "p.yaml"
    shutil.copy(DEFAULT_POLICY_FILE, path)
    pm = PolicyManager(path)
    assert pm.section("exclusive_licensing")["minimum_royalty_amount"] == 3_000_000
    text = path.read_text(encoding="utf-8").replace("minimum_royalty_amount: 3000000", "minimum_royalty_amount: 5000000")
    time.sleep(0.01)
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(time.time_ns(), time.time_ns() + 1_000_000))
    assert pm.section("exclusive_licensing")["minimum_royalty_amount"] == 5_000_000


def test_env_override(tmp_path, monkeypatch):
    path = tmp_path / "custom.yaml"
    shutil.copy(DEFAULT_POLICY_FILE, path)
    monkeypatch.setenv("PATENT_LAW_MCP_POLICY_FILE", str(path))
    assert PolicyManager().path == path


EXPECTED_TOOLS = {
    "fetch_patent_smart", "inspect_and_summarize_by_appno", "parse_raw_patent_text", "analyze_patent_document",
    "get_bundled_sample_patent", "summarize_patent", "ground_summary_figures", "evaluate_commercialization",
    "design_licensing_terms", "review_licensing_contract", "process_invention_disclosure",
    "calculate_disposal_compensation", "evaluate_unutilized_free_license", "evaluate_exclusive_renewal",
    "get_policy_table", "verify_tech_transfer_scope_match", "bundle_patents_for_transfer",
    "find_target_licensees_by_patent", "ground_patent_applications", "search_patents", "search_laws", "get_law_article", "calculate_patent_deadline", "calculate_patent_term", "calculate_annuity_schedule", "check_patent_rights_status",
}


def test_registered_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED_TOOLS <= names
    assert not {"find_patents_by_business_need", "recommend_similar_patents", "recommend_free_transfer_patents"} & names
    fetch = next(t for t in tools if t.name == "fetch_patent_smart")
    assert "api_key" not in fetch.inputSchema["properties"]


def test_mcp_rejects_invalid_enum():
    with pytest.raises(Exception, match="license_type"):
        asyncio.run(mcp.call_tool("design_licensing_terms", {"patent_id": "x", "license_type": "전용실시"}))


# ---------------------------------------------------------------- 프로파일
from patent_law_mcp.policies.policy_manager import PROFILE_FILES  # noqa: E402
from patent_law_mcp.tools.contract_practice import design_licensing_terms, review_licensing_contract  # noqa: E402
from patent_law_mcp.tools.employee_invention_practice import (  # noqa: E402
    calculate_disposal_compensation,
    evaluate_unutilized_free_license,
    process_invention_disclosure,
)


@pytest.mark.parametrize("name", list(PROFILE_FILES))
def test_all_profiles_valid(name):
    assert validate_policy(yaml.safe_load(PROFILE_FILES[name].read_text(encoding="utf-8"))) == []


def test_public_research_requires_institution_ratio():
    shares = [{"name": "A", "share_rate": 1.0}]
    with pytest.raises(ValueError, match="payout_ratio"):
        calculate_disposal_compensation(10_000_000, shares, profile="public_research")
    r = calculate_disposal_compensation(10_000_000, shares, payout_ratio=0.6, profile="public_research")
    assert r["total_compensation_krw"] == 6_000_000 and r["payout_ratio_source"] == "호출 시 입력"
    assert r["legal_audit_basis"]["profile"] == "public_research"


def test_controlling_shareholder_gets_no_tax_free():
    r = calculate_disposal_compensation(
        10_000_000, [{"name": "대표", "share_rate": 1.0, "is_controlling_shareholder": True}], payout_ratio=0.5, profile="private_company"
    )
    row = r["payment_table"][0]
    assert row["tax_free_krw"] == 0 and row["taxable_krw"] == 5_000_000


def test_non_national_contract_has_no_minimum_royalty_or_bidding():
    r = design_licensing_terms("x", "exclusive", "sme", profile="public_research")
    assert r["financial_terms"]["lump_sum_fee_krw"] == 7_500_000
    assert not any("경쟁입찰" in p for p in r["required_procedures"])
    assert "최소실시료" not in " ".join(c["clause"] for c in r["mandatory_practice_clauses"])
    review = review_licensing_contract("계약기간은 3년, 실시지역은 대한민국.", profile="private_company")
    assert not any("최소실시료" in c["item"] for c in review["checklist"])


def test_institution_disclosure_follows_amended_succession_rule():
    # 발명진흥법 제13조(2024.2.6. 개정): 예약승계 규정이 있으면 자동 승계, 승계하지 않을 때만 4개월 내 통지
    auto = process_invention_disclosure("발명", ["A"], profile="private_company")
    assert "발명 완성 때부터 사용자에게 승계" in auto["succession_rule"]
    assert any("승계하지 않을 경우에만 4개월" in step for step in auto["administrative_steps"])
    manual = process_invention_disclosure("발명", ["A"], profile="public_research", has_advance_succession_rule=False)
    assert "승계를 포기한 것으로 봅니다" in manual["succession_rule"]


def test_env_profile_switch_keeps_national_only_tools_national(monkeypatch):
    monkeypatch.setenv("PATENT_LAW_MCP_PROFILE", "public_research")
    assert evaluate_unutilized_free_license(5)["eligible_for_free_license"] is True
    assert design_licensing_terms("x", "exclusive")["legal_audit_basis"]["profile"] == "public_research"
