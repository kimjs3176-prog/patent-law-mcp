"""업스트림 테스트 케이스를 그대로 옮긴 패리티 테스트.

- patent-summary-wizard/src/test/summaryGrounding.test.ts
- patent-summary-wizard/src/test/trlConsistency.test.ts, trlStage.test.ts, trlReasonStage.test.ts
업스트림 테스트가 바뀌면 이 파일도 같이 고쳐 Python 포팅이 같은 결과를 내는지 확인합니다.
"""

import re

from patent_law_mcp.upstream.gazette_holders import holders_from_text
from patent_law_mcp.upstream.summary_grounding import GroundingSource as S
from patent_law_mcp.upstream.summary_grounding import source_figures, strip_unsupported_effect_figures as strip


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


# ---------------------------------------------------------------- trlConsistency / trlStage / trlReasonStage
def sec(body):
    return f"## 기술분야\n농업용 미생물 제제 기술이다.\n\n## 상용화전망\n{body}\n"


MARKER = "## 상용화전망\n본 발명은 유효 마커 발굴 및 실험실 검증을 완료하고 표준화 프로토콜을 정립하였다. 단기적으로는 기술이전을 추진한다.\n"


# ---------------------------------------------------------------- patent-video-skill
def test_gazette_holders_drop_address_lines():
    text = "(73) 특허권자\n대한민국(관리부서:농촌진흥청장)\n전라북도 전주시 덕진구 농생명로 300\n(72) 발명자\n홍길동"
    assert holders_from_text(text) == (["대한민국(관리부서:농촌진흥청장)"], "73")
    assert holders_from_text("(71) 출원인\n주식회사 가나다 서울특별시 강남구 테헤란로 1\n(72) 발명자") == (["주식회사 가나다"], "71")


