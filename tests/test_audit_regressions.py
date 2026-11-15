"""Regression cases found during the November 2026 repository review."""

import copy
import sqlite3
from unittest.mock import Mock

import pytest
import yaml

from patent_law_mcp import cache
from patent_law_mcp.policies.policy_manager import DEFAULT_POLICY_FILE, PolicyError, PolicyManager, validate_policy
from patent_law_mcp.tools import kipris_connector, law_lookup
from patent_law_mcp.tools.claims_practice import verify_tech_transfer_scope_match
from patent_law_mcp.tools.deadlines import check_patent_rights_status


def test_negated_element_never_matches():
    result = verify_tech_transfer_scope_match("센서와 모터를 포함하는 장치.", "센서는 있음. 모터는 없음.")
    element = result["verified_elements"][0]
    assert element["negated_keywords"] == ["모터"]
    assert not element["is_matched"]
    assert result["matched_elements"] == "0/1"


def test_partial_keywords_do_not_assert_complete_scope():
    result = verify_tech_transfer_scope_match("센서와 모터를 포함하는 장치.", "센서를 장착한 제품입니다.")
    assert "모든 구성요소가 제품 설명에서 확인" not in result["licensing_necessity_evaluation"]
    assert "확정한 결과가 아니" in result["licensing_necessity_evaluation"]


@pytest.mark.parametrize("identifier,country", [("WO2020123456A1", "WO"), ("US10000000B2", "US"), ("EP1000000B1", None)])
def test_foreign_rights_do_not_use_korean_calculators(monkeypatch, identifier, country):
    from patent_law_mcp.tools import deadlines
    patent = {"found": True, "application_date": "2020-01-01", "register_date": "2021-01-01"}
    if country:
        patent["country"] = country
    monkeypatch.setattr(kipris_connector, "fetch_patent_smart", lambda *args: patent)
    term, annuity = Mock(), Mock()
    monkeypatch.setattr(deadlines, "calculate_patent_term", term)
    monkeypatch.setattr(deadlines, "calculate_annuity_schedule", annuity)
    result = check_patent_rights_status(identifier, paid_through_year=3)
    assert "error" in result["term"] and "error" in result["annuity"]
    assert result["country"] != "KR"
    term.assert_not_called()
    annuity.assert_not_called()


def test_law_name_mismatch_does_not_fetch_or_cache_other_law(monkeypatch):
    monkeypatch.setenv("LAW_OC", "test")
    candidates = [{"name": "특허법 시행령", "mst": "123"}]
    monkeypatch.setattr(law_lookup, "_search", lambda *args: candidates)
    fetch, put = Mock(), Mock()
    monkeypatch.setattr(law_lookup, "_get_json", fetch)
    monkeypatch.setattr(cache, "put", put)
    result = law_lookup.get_law_article("특허법 오타", "1")
    assert result["found"] is False and result["candidates"] == candidates
    fetch.assert_not_called()
    put.assert_not_called()


@pytest.mark.parametrize("wrapped", [False, True])
def test_article_preserves_items_with_or_without_paragraph(wrapped):
    items = {"호": [{"호내용": "1. 조건", "목": {"목내용": "가. 예외"}}]}
    unit = {"조문내용": "제1조"}
    unit.update({"항": {"항내용": "① 내용", **items}} if wrapped else items)
    text = law_lookup._format_article(unit)
    assert "1. 조건" in text and "가. 예외" in text
    assert text.index("1. 조건") < text.index("가. 예외")


def test_unwritable_cache_does_not_fail_successful_lookup(tmp_path, monkeypatch):
    parent = tmp_path / "file"
    parent.write_text("not a directory")
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", str(parent / "cache.db"))
    cache.put("patent", "id", {"found": True})
    assert cache.get("patent", "id") is None


@pytest.mark.parametrize("payload", ["broken json", "[]", "null"])
def test_corrupt_cache_is_a_miss(tmp_path, monkeypatch, payload):
    path = tmp_path / "cache.db"
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", str(path))
    cache.put("patent", "id", {"found": True})
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE cache SET value = ?", (payload,))
    assert cache.get("patent", "id") is None


@pytest.mark.parametrize("ttl", ["bad", "nan", "inf", "-1"])
def test_invalid_cache_ttl_is_a_miss(tmp_path, monkeypatch, ttl):
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", str(tmp_path / "cache.db"))
    cache.put("patent", "id", {"found": True})
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE_TTL_HOURS", ttl)
    assert cache.get("patent", "id") is None


@pytest.mark.parametrize("section", ["metadata", "contract_practice"])
@pytest.mark.parametrize("value", ["invalid", [1], 42, None])
def test_invalid_policy_sections_raise_policy_error(tmp_path, section, value):
    policy = copy.deepcopy(yaml.safe_load(DEFAULT_POLICY_FILE.read_text()))
    policy[section] = value
    assert validate_policy(policy)
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(policy, allow_unicode=True))
    with pytest.raises(PolicyError, match=section):
        PolicyManager(path).load()
