from patent_law_mcp.tools.analysis import (
    evaluate_commercialization,
    extract_key_spec_chips,
    ground_summary_figures,
    summarize_patent,
)
from patent_law_mcp.tools.claim_utils import detect_technology_type, split_claim_elements
from patent_law_mcp.tools.document_parser import (
    analyze_patent_document,
    get_bundled_sample_patent,
    parse_raw_patent_text,
)
from conftest import fixture_text


def test_gazette_b1_format():
    r = parse_raw_patent_text(fixture_text("gazette_b1.txt"))
    assert r["title"] == "굳지 않는 떡의 제조방법"
    assert r["application_number"] == "10-2010-0062402"
    assert r["register_number"] == "10-1070281"
    assert r["applicant"] == "대한민국(농촌진흥청장)"
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


def test_analyze_stops_without_claims():
    r = analyze_patent_document("발명의 명칭: 무엇인가\n요약 없음, 청구항 없음, 메모만 있습니다.")
    assert "error" in r and "patent_summary" not in r


def test_samples_are_marked_fictional_and_unknown_keys_fail():
    s = get_bundled_sample_patent("떡")
    assert s["found"] and s["is_fictional_sample"]
    assert s["register_number"].startswith("SAMPLE-")
    r = get_bundled_sample_patent("10-9999999")
    assert r["found"] is False and "sorting_machine" in r["available_samples"]


def test_spec_chips_do_not_read_angles_as_temperature():
    chips = extract_key_spec_chips("상기 조명부는 45도 입사각으로 850nm 광을 조사하며, 60~75℃에서 2~4시간 추출한다.")
    values = {c["key"]: c["value"] for c in chips}
    assert values["온도 조건"] == "60~75℃"
    assert values["파장"] == "850nm"
    assert values["처리 시간"] == "2~4시간"
    assert extract_key_spec_chips("수치가 없는 문장") == []


def test_technology_type():
    assert detect_technology_type("과채류 선별 장치 및 선별 방법").startswith("물건·방법 복합")
    assert detect_technology_type("흑미 유래 기능성 추출물의 제조방법").startswith("공정")
    assert detect_technology_type("밀폐형 온실용 LED 광원 및 환경제어 시스템").startswith("장치")


def test_claim_elements_exclude_preamble():
    elements, subject = split_claim_elements("컨베이어 모듈; 조명부; 및 분광 센서부;를 포함하는 선별 장치.")
    assert elements == ["컨베이어 모듈", "조명부", "분광 센서부"]
    assert subject == "선별 장치"


def test_summary_effect_is_extracted_not_invented():
    s = get_bundled_sample_patent("sorting_machine")
    r = summarize_patent("x", s["title"], s["abstract"], s["claims"], s["description"])
    assert r["primary_effect"]["source"] == "원문 발췌"
    assert r["primary_effect"]["text"] in s["description"]
    assert "grounding_verified" not in r

    no_effect = summarize_patent("x", "장치", "본 발명은 장치에 관한 것이다.", ["A부; 및 B부;를 포함하는 장치."])
    assert no_effect["primary_effect"]["source"] == "미확인"
    assert "수율" not in " ".join(no_effect["elevator_pitch_draft"])


def test_summary_skips_deleted_and_dependent_claims():
    r = summarize_patent("x", "장치", "초록", ["삭제", "제1항에 있어서, C를 더 포함하는 장치.", "A부; 및 B부;를 포함하는 장치."])
    assert r["claims_overview"] == {"total": 3, "deleted": 1, "independent": 1}
    assert r["technical_solution"].startswith("A부")


def test_ground_summary_figures():
    # 업스트림 규칙: 근거 없는 수치가 있는 문장은 통째로 '추가 검증 필요' 문장으로 바꾸고, 근거 있는 문장은 그대로 둔다
    r = ground_summary_figures("에너지를 30% 절감한다. 수율이 2배 향상된다.", "본 발명은 수율을 2배 향상시킨다.")
    assert r["removed_figures"] == ["30%"]
    assert "에너지 관련 효과는 원문에 정량 근거가 없어 추가 검증이 필요하다." in r["sanitized_text"]
    assert "수율이 2배 향상된다." in r["sanitized_text"]
    assert r["scope"] == "전체 텍스트"


def test_trl_requires_evidence():
    assert evaluate_commercialization("식품")["estimated_trl"] is None
    assert evaluate_commercialization("식품", "prototype")["estimated_trl"] == "TRL 5~6"
