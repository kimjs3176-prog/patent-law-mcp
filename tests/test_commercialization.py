"""기술사업화 평가 (patent-summary-wizard analyze-commercialization 포팅) 테스트"""

from datetime import date

from patent_law_mcp.tools.commercialization import ChecklistHit as H
from patent_law_mcp.tools.commercialization import evaluate_patent_commercialization as ev
from patent_law_mcp.upstream import commercialization_score as cs

AS_OF = date(2026, 11, 22)


def test_without_items_returns_rubric():
    r = ev("x")
    assert r["mode"] == "평가 기준 안내"
    assert {c["id"] for c in r["checklist"]["technology"]} >= {"T-A1", "T-C4"}
    assert len(r["checklist"]["market"]) == 8 and len(r["checklist"]["business"]) == 8
    assert "TRL 9" in r["trl_rules"]


def test_trl_required_and_unknown_id_rejected():
    assert ev("x", checked_items=[])["mode"] == "입력 필요"
    r = ev("x", checked_items=[H(id="Z9", evidence="근거")], trl=4)
    assert r["mode"] == "입력 오류" and "Z9" in r["error"]


def test_checklist_sum_clamp_and_total():
    items = [H(id=i, evidence="원문 근거") for i in ("T-A1", "T-A2", "T-A3", "T-B1", "T-B2", "T-C1", "T-C2")]
    r = ev("x", checked_items=items, trl=5, as_of=AS_OF)
    assert r["scores"]["technology"]["checklist_score"] == 95  # 60+36 → 상한 95
    neg = [H(id=i, evidence="원문 근거") for i in ("T-A4", "T-B4", "T-C3")]
    assert ev("x", checked_items=neg, trl=3, as_of=AS_OF)["scores"]["technology"]["score"] == 55  # 60-15 → 하한 55
    s = r["scores"]
    assert r["total_score"] == cs.total_score(s["technology"]["score"], s["market"]["score"], s["business"]["score"])


def test_same_input_same_output():
    kw = dict(checked_items=[H(id="M2", evidence="떡 제품"), H(id="B1", evidence="기존 설비")], trl=8, ipc_codes=["A23L 7/10"],
              filing_date="2010-06-30", registration_number="10-1070281", as_of=AS_OF)
    assert ev("a", **kw)["report_markdown"] == ev("a", **kw)["report_markdown"]


def test_vray_blend_matches_upstream_formula():
    v = cs.vray_business_index(trl=8, as_of=AS_OF, filing_date="2010-06-30", registration_number="10-1070281", ipc_count=1, abstract_len=40)
    # 성숙도 0.75, 유효성 0.95-0.05=0.90, 잔존 3.6년/15=0.24, 폭 1/3
    assert v["parts"]["maturity"] == 0.75 and v["parts"]["validity"] == 0.9
    assert v["index"] == cs._js_round(55 + 40 * (0.75 * 0.35 + 0.9 * 0.25 + v["parts"]["remaining_years"] / 15 * 0.2 + (1 / 3) * 0.2))
    assert cs.blend_business(70, v["index"]) == cs._js_round(70 * 0.6 + v["index"] * 0.4)
    unknown = cs.vray_business_index(trl=3, as_of=AS_OF)
    assert unknown["parts"]["remaining_years"] == 20 and unknown["registered"] is False and unknown["parts"]["validity"] == 0.65


def test_js_round_half_up():
    assert cs._js_round(70.5) == 71 and cs._js_round(72.5) == 73  # Python round()는 72


def test_ipc_auto_items_override_selection():
    r = ev("x", checked_items=[H(id="M1", evidence="식품")], trl=4, ipc_codes=["G01N 33/02"], as_of=AS_OF)
    assert all(h["id"] != "M1" for h in r["checklist_breakdown"]["market"])
    assert any("M1" in n for n in r["notes"])
    r = ev("x", checked_items=[], trl=4, ipc_codes=["A23L 7/10", "C12N 1/20"], as_of=AS_OF)
    ids = {h["id"] for axis in r["checklist_breakdown"].values() for h in axis}
    assert {"T-B3", "M1"} <= ids


def test_trl_reconciled_with_summary_stage():
    summary = "## 상용화전망\n본 발명은 유효 마커 발굴 및 실험실 검증을 완료하고 표준화 프로토콜을 정립하였다. 단기적으로는 기술이전을 추진한다.\n"
    r = ev("x", checked_items=[], trl=6, summary_text=summary, as_of=AS_OF)
    assert r["trl"]["level"] == 4 and r["trl"]["adjusted_by_summary"] and "'실험실' 단계" in r["trl"]["reason"]


def test_strong_wording_raises_score_and_conclusion_appended():
    reason = "독립항의 결합 구성이 탁월하고 실험 데이터로 뒷받침된다. 재현 실험이 더해지면 근거가 견고해진다."
    r = ev("x", checked_items=[H(id="T-A1", evidence="결합 구성")], trl=4, technology_reason=reason, as_of=AS_OF)
    assert r["scores"]["technology"]["score"] == 80 and r["consistency_adjustments"]
    assert r["reasons"]["technology"].endswith("우수한 수준으로 평가된다.")


def test_overclaim_softened_and_mentions_stripped():
    reason = "차별성이 매우 높다 TRL 4 수준이며 존속기간이 짧다. 비교예 보완이 필요하다."
    out = cs.strip_duration_mentions(cs.strip_score_mentions(cs.strip_trl_mentions(cs.soften_if_overclaim(65, reason))))
    assert "TRL" not in out and "존속기간" not in out and "매우 높" not in out


def test_fallback_texts_when_reasons_missing():
    r = ev("x", checked_items=[], trl=2, as_of=AS_OF)
    assert r["reasons"]["market"] == cs.make_market_fallback(r["scores"]["market"]["score"])
    assert "TRL 2" in r["trl"]["reason"]
    for part in ("| **종합** |", "### 채점 근거", "### 사업성 보정 (V-RAY"):
        assert part in r["report_markdown"]
