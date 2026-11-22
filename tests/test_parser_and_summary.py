from patent_law_mcp.tools.grounding import ground_summary_figures
from patent_law_mcp.tools.claim_utils import detect_technology_type, split_claim_elements
from patent_law_mcp.tools.document_parser import get_bundled_sample_patent, parse_raw_patent_text
from conftest import fixture_text
import pytest


def test_gazette_b1_format():
    r = parse_raw_patent_text(fixture_text("gazette_b1.txt"))
    assert r["title"] == "굳지 않는 떡의 제조방법"
    assert r["application_number"] == "10-2010-0062402"
    assert r["register_number"] == "10-1070281"
    assert r["applicant"] == "대한민국(농촌진흥청장)"
    assert r["holder_kind"] == "특허권자 (등록공보)"
    assert r["ipc_code"] == "A23L 7/10"
    assert r["abstract"].startswith("본 발명은 전분의 노화")
    assert r["claim_numbers"] == [1, 2, 3]
    assert r["independent_claim_numbers"] == [1]
    assert r["claims"][1].startswith("제1항에 있어서")
    assert "명 세 서" not in r["claims"][-1]
    assert r["warnings"] == []


def test_electronic_spec_format():
    r = parse_raw_patent_text(fixture_text("spec_format.txt"))
    assert r["title"] == "흑미 추출물의 제조방법"
    assert r["claims_count"] == 2
    assert r["independent_claim_numbers"] == [1]
    assert r["abstract"] == "본 발명은 흑미 추출물의 제조방법에 관한 것이다."


def test_parser_does_not_invent_missing_fields():
    r = parse_raw_patent_text("이 텍스트에는 서지사항도 청구항도 없습니다. 그냥 메모입니다.")
    assert r["applicant"] == "" and r["ipc_code"] == "" and r["claims"] == []
    assert any("청구항" in w for w in r["warnings"])


def test_samples_are_marked_fictional_and_unknown_keys_fail():
    s = get_bundled_sample_patent("떡")
    assert s["found"] and s["is_fictional_sample"]
    assert s["register_number"].startswith("SAMPLE-")
    r = get_bundled_sample_patent("10-9999999")
    assert r["found"] is False and "sorting_machine" in r["available_samples"]


def test_technology_type():
    assert detect_technology_type("과채류 선별 장치 및 선별 방법").startswith("물건·방법 복합")
    assert detect_technology_type("흑미 유래 기능성 추출물의 제조방법").startswith("공정")
    assert detect_technology_type("밀폐형 온실용 LED 광원 및 환경제어 시스템").startswith("장치")


def test_claim_elements_exclude_preamble():
    elements, subject = split_claim_elements("컨베이어 모듈; 조명부; 및 분광 센서부;를 포함하는 선별 장치.")
    assert elements == ["컨베이어 모듈", "조명부", "분광 센서부"]
    assert subject == "선별 장치"


def test_ground_summary_figures():
    # 업스트림 규칙: 근거 없는 수치가 있는 문장은 통째로 '추가 검증 필요' 문장으로 바꾸고, 근거 있는 문장은 그대로 둔다
    r = ground_summary_figures("에너지를 30% 절감한다. 수율이 2배 향상된다.", "본 발명은 수율을 2배 향상시킨다.")
    assert r["removed_figures"] == ["30%"]
    assert "에너지 관련 효과는 원문에 정량 근거가 없어 추가 검증이 필요하다." in r["sanitized_text"]
    assert "수율이 2배 향상된다." in r["sanitized_text"]
    assert r["scope"] == "전체 텍스트"


def test_gazette_holder_address_lines_are_dropped():
    text = fixture_text("gazette_b1.txt").replace(
        "     대한민국(농촌진흥청장)\n", "     대한민국(관리부서:농촌진흥청장)\n     전라북도 전주시 덕진구 농생명로 300\n"
    )
    assert parse_raw_patent_text(text)["applicants"] == ["대한민국(관리부서:농촌진흥청장)"]


def test_characterizing_clause_is_element_not_subject():
    # 실제 등록특허(KR101070281B1) 형식: "~를 포함하고, (특징부)하는 것을 특징으로 하는 X"
    claim = ("건조부; 열풍주입부; 및 조절부;를 포함하고, 상기 조절부는 상호 교대로 운전을 하면서 "
             "건조 슬러지가 혼합되는 것을 특징으로 하는 유기성 슬러지의 고정상식 건조장치.")
    elements, subject = split_claim_elements(claim)
    assert subject == "유기성 슬러지의 고정상식 건조장치"
    assert elements[:3] == ["건조부", "열풍주입부", "조절부"]
    assert elements[3].startswith("[특징부] 상기 조절부는 상호 교대로")


