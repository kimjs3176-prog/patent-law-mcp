"""국가법령정보 원문 대조 장치 — 네트워크 없이 가짜 원문으로 점검"""

import json

import pytest

from patent_law_mcp import legal_sources as ls

NOTICE = {"id": "notice", "kind": "admrul", "name": "업무 운영요령", "short": "고시",
          "articles": {"제9조": [{"phrase": "300만원", "policy": "exclusive_licensing.minimum_royalty_amount"}], "제10조": []}}
ART9 = "제9조(최소실시료) ① 전용실시권자는 실시료의 일부로서 300만원 이상의 금액을 계약일로부터 60일 이내에 납부하여야 한다."
ART10 = "제10조(전용실시계약의 갱신) ④ 만료되는 날을 기준으로 30일 전까지 신청해야 한다."


@pytest.fixture
def setup(tmp_path, monkeypatch):
    src = tmp_path / "legal_sources.yaml"
    src.write_text(json.dumps({"sources": [NOTICE]}, ensure_ascii=False), encoding="utf-8")
    base = tmp_path / "legal_baseline.json"
    monkeypatch.setattr(ls, "SOURCES_FILE", src)
    monkeypatch.setattr(ls, "BASELINE_FILE", base)
    monkeypatch.setattr(ls, "load_sources", lambda path=src: ls.yaml.safe_load(src.read_text(encoding="utf-8"))["sources"])
    monkeypatch.setattr(ls, "load_baseline", lambda path=base: json.loads(base.read_text(encoding="utf-8")) if base.exists() else {"verified_on": None, "sources": {}})
    ls.update_baseline(fetch=lambda s: ({"seq": "1", "effective_date": ""}, {"제9조": ART9, "제10조": ART10}), path=base)
    return base


def test_split_articles_handles_branch_numbers_and_addenda():
    text = "제1조(목적) 이 법은...\n제81조의3(회복) ① 2개월 이내\n제82조(삭제)\n 부 칙\n제1조(시행일) 공포한 날"
    arts = ls.split_articles(text)
    assert list(arts) == ["제1조", "제81조의3", "제82조"]
    assert arts["제81조의3"].startswith("제81조의3(회복)")


def test_unchanged(setup):
    r = ls.check_sources(fetch=lambda s: ({"seq": "1", "effective_date": ""}, {"제9조": ART9, "제10조": ART10}))
    assert r["summary"] == "변경 없음" and r["changed"] == []


def test_amount_change_is_reported_with_affected_policy(setup):
    new9 = ART9.replace("300만원", "500만원")
    r = ls.check_sources(fetch=lambda s: ({"seq": "2", "effective_date": ""}, {"제9조": new9, "제10조": ART10}))
    src = r["changed"][0]
    assert src["version_changed"] is True
    types = {f["type"] for f in src["findings"]}
    assert types == {"본문 변경", "기준값 문구 없음"}
    missing = next(f for f in src["findings"] if f["type"] == "기준값 문구 없음")
    assert "exclusive_licensing.minimum_royalty_amount" in missing["detail"]
    report = ls.render_report(r)
    assert "+" in report and "500만원" in report and "기준선을 갱신" in report


def test_version_only_change_and_deleted_article(setup):
    r = ls.check_sources(fetch=lambda s: ({"seq": "3", "effective_date": ""}, {"제9조": ART9, "제10조": ART10}))
    assert r["changed"][0]["findings"] == [] and r["changed"][0]["version_changed"]
    assert "감시 조문 본문은 그대로" in ls.render_report(r)
    gone = ls.check_sources(fetch=lambda s: ({"seq": "1", "effective_date": ""}, {"제9조": ART9}))
    assert gone["changed"][0]["findings"][0]["type"] == "조문 없음"


def test_phrase_match_ignores_inserted_spaces(setup):
    spaced = ART9.replace("300만원", "300만 원")
    r = ls.check_sources(fetch=lambda s: ({"seq": "1", "effective_date": ""}, {"제9조": spaced, "제10조": ART10}))
    assert not any(f["type"] == "기준값 문구 없음" for c in r["changed"] for f in c["findings"])


def test_fetch_error_is_not_silent(setup):
    def boom(s):
        raise ls.LawSourceError("화면 구조 변경")
    r = ls.check_sources(fetch=boom)
    assert r["summary"] == "점검 오류 있음" and "화면 구조 변경" in r["errors"][0]["error"]


def test_update_refuses_when_watched_article_missing(setup):
    with pytest.raises(ls.LawSourceError, match="제10조"):
        ls.update_baseline(fetch=lambda s: ({"seq": "4", "effective_date": ""}, {"제9조": ART9}), path=setup)


def test_resolve_version_parsers():
    law = {"kind": "law", "name": "특허법"}
    v = ls.resolve_version(law, get=lambda u: "var lsiSeq : '279827', efYd : '20251111'")
    assert v == {"seq": "279827", "effective_date": "20251111"}
    adm = {"kind": "admrul", "name": "고시"}
    assert ls.resolve_version(adm, get=lambda u: '<input id="admRulSeq" value="2100000267008" />')["seq"] == "2100000267008"
    with pytest.raises(ls.LawSourceError):
        ls.resolve_version(law, get=lambda u: "<html>점검 중</html>")


def test_bundled_baseline_covers_every_watched_article():
    base = json.loads(ls.BASELINE_FILE.read_text(encoding="utf-8"))
    assert base["verified_on"]
    for s in ls.load_sources():
        arts = base["sources"][s["id"]]["articles"]
        assert set(s["articles"]) <= set(arts), s["id"]
        for art, phrases in s["articles"].items():
            for p in phrases or []:
                assert p["phrase"].replace(" ", "") in arts[art]["text"].replace(" ", ""), (s["id"], art, p["phrase"])


def test_audit_block_shows_verified_on():
    from patent_law_mcp.tools.national_disposal import plan_national_disposal

    assert plan_national_disposal("non_exclusive")["legal_audit_basis"]["source_text_verified_on"]


def test_partial_update_keeps_global_date_at_oldest(setup, monkeypatch):
    # 리뷰 7: --only로 일부만 갱신해도 전체 대조일은 가장 오래된 법령 기준
    base = json.loads(setup.read_text(encoding="utf-8"))
    base["sources"]["other"] = {"name": "다른 법령", "verified_on": "2020-01-01", "articles": {}}
    setup.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    ls.update_baseline(ids=["notice"], fetch=lambda s: ({"seq": "9", "effective_date": ""}, {"제9조": ART9, "제10조": ART10}), path=setup)
    after = json.loads(setup.read_text(encoding="utf-8"))
    assert after["verified_on"] == "2020-01-01" and after["sources"]["notice"]["verified_on"] != "2020-01-01"
