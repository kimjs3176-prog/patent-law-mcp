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
    "find_target_licensees_by_patent",
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
