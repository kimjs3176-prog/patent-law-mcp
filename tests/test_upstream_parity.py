"""업스트림 테스트 케이스를 그대로 옮긴 패리티 테스트.

- patent-summary-wizard/src/test/summaryGrounding.test.ts
- patent-summary-wizard/src/test/trlConsistency.test.ts, trlStage.test.ts, trlReasonStage.test.ts
업스트림 테스트가 바뀌면 이 파일도 같이 고쳐 Python 포팅이 같은 결과를 내는지 확인합니다.
"""

import re

from patent_law_mcp.tools.analysis import evaluate_commercialization, ground_patent_applications
from patent_law_mcp.upstream.application_grounding import ground_applications
from patent_law_mcp.upstream.gazette_holders import holders_from_text
from patent_law_mcp.upstream.summary_grounding import GroundingSource as S
from patent_law_mcp.upstream.summary_grounding import source_figures, strip_unsupported_effect_figures as strip
from patent_law_mcp.upstream.trl_consistency import TrlBand, describe_trl_from_stage, detect_summary_maturity, reconcile_trl
from patent_law_mcp.upstream.video_signature import recommend_video_signature


def summary_of(body, section="발명요약 및 특징"):
    return f"## {section}\n{body}\n\n## 관련시장 동향\n국내 시장은 2023년 6,200억 원에서 연평균 6.8% 성장한다(AI 추정치).\n"


SOURCE = S(abstract="이 장치는 에너지를 절감하는 장치이다.", claims=["1. 에너지 절감용 장치로서 제어부를 포함하는 장치."])


# ---------------------------------------------------------------- summaryGrounding.test.ts
def test_removes_invented_savings_without_asserting_significance():
    r = strip(summary_of("에너지를 30% 절감한다."), SOURCE)
    assert "30%" not in r and "유의미" not in r and "추가 검증" in r


def test_ingredient_concentration_is_not_evidence():
    assert "30%" not in strip(summary_of("비용을 30% 절감한다."), S(claims=["설탕 30%를 포함하는 조성물."]))


def test_preserves_original_metric_and_decimal():
    text = summary_of("에너지 소비량이 2.5% 감소한다.")
    assert strip(text, S(abstract="에너지 소비량이 2.5% 감소한다.")) == text


def test_preserves_original_composition_and_range():
    text = summary_of("팥 99%와 설탕 1%로 구성한다. 회복률 73~100% 향상 개체를 선발한다.")
    assert strip(text, S(claims=["팥 99%와 설탕 1% 조성. 회복률 73 내지 100% 향상 개체."])) == text


def test_checks_technology_field_but_preserves_market():
    r = strip(summary_of("비용을 30% 절감한다.", "기술분야"), SOURCE)
    assert "30%" not in r and "6,200억 원" in r and "6.8%" in r


def test_removes_unsupported_duration_and_multiplier():
    r = strip(summary_of("처리 시간이 3시간 단축된다. 수율이 2배 향상된다."), SOURCE)
    assert "3시간" not in r and "2배" not in r


def test_does_not_invent_high_reliability():
    r = strip(summary_of("99% 이상의 신뢰도로 판정한다."), SOURCE)
    assert "99%" not in r and "높은 신뢰도" not in r


def test_claim_numbers_are_not_evidence():
    assert len(source_figures(S(claims=["30. 에너지 절감용 장치."])).percent) == 0


def test_removes_figures_after_verb():
    assert "30%" not in strip(summary_of("에너지 절감률은 30%이다."), SOURCE)


# ---------------------------------------------------------------- application evidence
CLAIMS = "식품 발효용 조성물로서 유산균을 포함하는 조성물이다."
DESCRIPTION = "상기 조성물은 가축 사료 제조에 사용할 수 있다."


def test_claim_use_marked_true():
    r = ground_applications(f"[[용도|청구항|식품 발효|{CLAIMS}]] 식품에 쓴다.", S(claims=[CLAIMS], description=DESCRIPTION))
    assert r["applications"][0] == {"label": "식품 발효", "claimed_in_claims": True, "source": "claims", "evidence": CLAIMS}


def test_description_only_use_is_downgraded():
    r = ground_applications(f"[[용도|청구항|가축 사료|{DESCRIPTION}]] 사료에 쓴다.", S(claims=[CLAIMS], description=DESCRIPTION))
    assert r["applications"][0]["claimed_in_claims"] is False and r["applications"][0]["source"] == "description"


def test_fabricated_excerpts_rejected():
    assert ground_applications(f"[[용도|청구항|치료|{CLAIMS}]]", S(claims=[CLAIMS]))["applications"] == []
    assert ground_applications("[[용도|청구항|치료|암 치료에 사용하는 새로운 조성물이다.]]", S(claims=[CLAIMS]))["applications"] == []


def test_mcp_application_tool():
    r = ground_patent_applications(
        [{"kind": "청구항", "label": "식품 발효", "evidence": CLAIMS}, {"kind": "청구항", "label": "가축 사료", "evidence": DESCRIPTION}],
        claims=[CLAIMS],
        description=DESCRIPTION,
    )
    assert [a["verdict"] for a in r["applications"]] == ["청구항 명시 용도", "명세서 일반 용도"]


# ---------------------------------------------------------------- trlConsistency / trlStage / trlReasonStage
def sec(body):
    return f"## 기술분야\n농업용 미생물 제제 기술이다.\n\n## 상용화전망\n{body}\n"


def test_lab_statement_lowers_trl():
    r = reconcile_trl(8, "## 상용화전망 본 기술은 현재 실험실 수준의 검증 단계로, 양산 공정은 미확보다.")
    assert r["trl"] == 4 and r["changed"] is True


def test_lab_with_inserted_word():
    s = ("## 상용화 전망\n본 발명의 기술완성도는 특정 침지 온도 및 시간 조건에서 성분 증가를 확인한 실험실 개발 단계이며 "
         "대용량 가공 시 열전달 불균일 문제를 해결하는 스케일업 실증이 요구된다. 단기적으로는 기술이전이 유력하다.")
    r = reconcile_trl(8, s)
    assert r["trl"] == 4 and r["band"].label == "실험실"


def test_mass_production_raises_trl():
    assert reconcile_trl(4, "## 상용화전망 기존 설비로 즉시 구현 가능한 양산 준비 단계다.")["trl"] == 7


def test_beyond_lab_is_pilot():
    assert reconcile_trl(8, "## 상용화전망 실험실 수준을 넘어 파일럿 단계에서 검증되었다.")["trl"] == 6


def test_in_range_unchanged():
    assert reconcile_trl(5, "## 상용화전망 시작품 단계로 현장 검증이 필요하다.")["changed"] is False


def test_order_independent():
    a = sec("본 기술은 실험실 검증과 파일럿 실증을 거쳐 양산 준비 단계에 있다.")
    b = sec("본 기술은 현재 양산 준비 단계에 있으며, 실험실 검증과 파일럿 실증을 거쳤다.")
    assert detect_summary_maturity(a).label == detect_summary_maturity(b).label == "양산준비"
    assert reconcile_trl(4, a)["trl"] == reconcile_trl(4, b)["trl"] == 7


def test_future_stages_not_counted():
    s = sec("현재 실험실 수준의 검증을 완료했으며, 2027년 파일럿 실증을 목표로 하고 양산 준비는 2029년 예정이다.")
    assert detect_summary_maturity(s).label == "실험실"
    assert reconcile_trl(7, s)["trl"] == 4


def test_transition_vs_current():
    assert detect_summary_maturity(sec("파일럿 실증 이후 양산 준비 단계로 전환할 계획이다.")).label == "파일럿·실증"
    assert detect_summary_maturity(sec("시작품 단계로 현장 검증이 필요하다.")).label == "파일럿·실증"


def test_future_path_and_competitors_excluded():
    assert detect_summary_maturity(sec("단기(1~2년) 내 파일럿 실증을 거쳐 중기(3~5년)에는 양산 체계를 구축할 계획이다.")) is None
    assert detect_summary_maturity(sec("현재 실험실 단계이며, 경쟁 기술은 이미 상용 단계에 있다.")).label == "실험실"


def test_no_section_no_judgement():
    no_section = "## 기술분야\n본 기술은 양산 준비 단계에 있다.\n\n## 발명요약 및 특징\n실험실 수준의 결과다.\n"
    assert detect_summary_maturity(no_section) is None
    assert reconcile_trl(3, no_section) == {"trl": 3, "changed": False, "band": None}


MARKER = "## 상용화전망\n본 발명은 유효 마커 발굴 및 실험실 검증을 완료하고 표준화 프로토콜을 정립하였다. 단기적으로는 기술이전을 추진한다.\n"


def test_reason_states_summary_stage():
    r = reconcile_trl(6, MARKER)
    assert r["trl"] == 4 and r["changed"] is True
    reason = describe_trl_from_stage(r["trl"], r["band"])
    assert reason == ("요약서 상용화전망이 기술완성도를 '실험실' 단계로 서술하고 있어 TRL 4로 판단되며, "
                      "모사 환경의 통합 실시예가 보강되면 5단계로 진입 가능하다.")
    assert "수치 데이터" not in reason


def test_reason_josa_and_single_trl_number():
    band = TrlBand(5, 6, "파일럿·실증")
    assert "TRL 6으로 판단되며, 실환경 운영 데이터가" in describe_trl_from_stage(6, band)
    assert "TRL 5로 판단되며, 파일럿·시작품 단계의" in describe_trl_from_stage(5, band)
    assert "TRL 3으로 판단되며" in describe_trl_from_stage(3, TrlBand(3, 4, "실험실"))
    for t in range(1, 10):
        assert [int(n) for n in re.findall(r"TRL\s*(\d)", describe_trl_from_stage(t, band))] == [t]


def test_mcp_trl_tool_uses_upstream_rules():
    r = evaluate_commercialization("분자마커", commercialization_outlook=MARKER, proposed_trl=6)
    assert r["estimated_trl"] == "TRL 4" and r["trl_adjusted"] is True
    r = evaluate_commercialization("식품", commercialization_outlook="현재 파일럿 실증 단계에 있다.")
    assert r["estimated_trl"] == "TRL 5~6"


# ---------------------------------------------------------------- patent-video-skill
def test_gazette_holders_drop_address_lines():
    text = "(73) 특허권자\n대한민국(관리부서:농촌진흥청장)\n전라북도 전주시 덕진구 농생명로 300\n(72) 발명자\n홍길동"
    assert holders_from_text(text) == (["대한민국(관리부서:농촌진흥청장)"], "73")
    assert holders_from_text("(71) 출원인\n주식회사 가나다 서울특별시 강남구 테헤란로 1\n(72) 발명자") == (["주식회사 가나다"], "71")


def test_video_signature_types():
    assert recommend_video_signature("벼 품종 판별용 프라이머 세트", ["서열번호 1의 프라이머를 포함하는 키트."])["recommended_type"] == "sequence"
    assert recommend_video_signature("흑미 추출물의 제조방법", ["A 단계; 및 B 단계;를 포함하는 제조방법."])["recommended_type"] == "journey"
    assert recommend_video_signature("밀폐형 온실 환경제어 시스템", ["센서; 제어기; 및 구동부;를 포함하는 시스템."])["recommended_type"] == "loop"
    assert recommend_video_signature("신규 사과 품종", ["사과 품종."])["recommended_type"] == "lineage"
    claims = ["A부; B부; 및 C부;를 포함하는 항원 단백질.", "제1항에 있어서, A부는 X인 항원 단백질.", "제2항에 있어서, X는 Y인 항원 단백질."]
    hint = recommend_video_signature("항원 단백질", claims)
    assert hint["recommended_type"] == "claim"
    assert hint["claim_structure"]["preamble"] == "항원 단백질"
    assert [d["no"] for d in hint["claim_structure"]["deps"]] == [2, 3]
    assert hint["claim_structure"]["deps"][1]["of"] == 2
