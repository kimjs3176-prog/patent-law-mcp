"""특허 기술사업화 평가 (기술성·시장성·사업성 점수와 TRL, 고정 양식 보고서)

평가 모델은 patent-summary-wizard analyze-commercialization을 옮긴 것입니다 (upstream/commercialization_score.py).
Claude는 원문을 읽고 체크리스트 항목 중 충족하는 것과 근거 문장만 고릅니다. 점수 합산·V-RAY 사업성 보정·
점수-문구 정합성·결론 문장·보고서 양식은 이 도구가 계산하므로, 같은 체크 결과면 누가 써도 같은 점수와 같은 양식이 나옵니다.
"""

import re
from datetime import date
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from patent_law_mcp.upstream import commercialization_score as cs
from patent_law_mcp.upstream.trl_consistency import describe_trl_from_stage, reconcile_trl

_DATA_RE = r"실험|데이터|수치|효능|효율|수율|비교예|대조군"
_FOOD_CLASSES = {"A01", "A21", "A22", "A23", "A24", "A47"}


class ChecklistHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(description="체크리스트 항목 ID (예: T-A1, M5, B2)")]
    evidence: Annotated[str, Field(min_length=2, description="원문에서 이 항목을 뒷받침하는 문장·청구항 발췌 (그대로 인용)")]


def _rubric() -> Dict[str, Any]:
    groups: Dict[str, List[Dict[str, Any]]] = {"technology": [], "market": [], "business": []}
    for c in cs.CHECKLIST:
        groups[c["axis"]].append({"id": c["id"], "points": c["points"], "group": c["group"], "criterion": c["text"]})
    return {
        "mode": "평가 기준 안내",
        "how_to": (
            "1) 특허 원문(초록·청구항·명세서, 있으면 요약서)을 읽고 아래 체크리스트에서 원문으로 확인되는 항목만 골라 "
            "checked_items에 {id, evidence(원문 인용)}로 넣으십시오. 추정으로 고르지 마십시오. "
            "2) trl_rules에서 충족되는 가장 높은 단계 하나를 trl로 넣으십시오. "
            "3) 근거 문장(technology_reason 등)은 writing_rules대로 쓰거나, 비우면 원본의 점수 구간별 기본 문구를 씁니다. "
            "4) ipc_codes·filing_date·registration_number·abstract를 넣으면 IPC 항목(T-B3·M1)과 V-RAY 보정을 도구가 계산합니다."
        ),
        "scoring": f"각 항목 기본 {cs.BASE}점에서 가감, 상한 {cs.CAP}·하한 {cs.FLOOR}. 사업성 = 체크리스트 60% + V-RAY 지수 40%. 총점 = 기술성×0.35 + 시장성×0.35 + 사업성×0.30",
        "checklist": groups,
        "trl_rules": {f"TRL {k}": v for k, v in cs.TRL_RULES.items()},
        "writing_rules": cs.WRITING_RULES,
        "score_version": cs.SCORE_VERSION,
        "upstream": "patent-summary-wizard analyze-commercialization",
    }


def evaluate_patent_commercialization(
    patent_id: Annotated[str, Field(min_length=1, description="특허(출원·등록)번호 또는 식별 이름")],
    checked_items: Optional[List[ChecklistHit]] = None,
    trl: Annotated[Optional[int], Field(ge=1, le=9)] = None,
    title: Optional[str] = None,
    ipc_codes: Optional[List[str]] = None,
    filing_date: Optional[str] = None,
    registration_number: Optional[str] = None,
    registration_date: Optional[str] = None,
    abstract: Optional[str] = None,
    claims_count: Annotated[Optional[int], Field(ge=0)] = None,
    summary_text: Optional[str] = None,
    technology_reason: Optional[str] = None,
    market_reason: Optional[str] = None,
    business_reason: Optional[str] = None,
    trl_reason: Optional[str] = None,
    analysis: Optional[str] = None,
    as_of: Optional[date] = None,
) -> Dict[str, Any]:
    """특허 기술사업화 평가: 기술성·시장성·사업성 점수(55~95), 총점, TRL과 근거를 고정 양식 보고서(report_markdown)로 만듭니다.
    (patent-summary-wizard 평가 모델 포팅, 규칙 버전 s2-2026-11)

    사용법: checked_items 없이 부르면 체크리스트·TRL 기준·작성 규칙을 돌려줍니다. 원문을 읽고 충족 항목과 근거를 골라 다시 부르십시오.
    Claude는 항목만 고르고 점수는 정하지 않습니다 — 합산·V-RAY 사업성 보정·점수-문구 정합성·결론 문장을 도구가 계산합니다.
    보고서는 report_markdown을 그대로 보여 주십시오 (사용자 간 양식 통일).

    Args:
        patent_id: 특허번호 또는 식별 이름
        checked_items: 원문으로 확인된 체크리스트 항목 [{id: "T-A1", evidence: "원문 인용"}]. 없으면 기준표 반환
        trl: TRL 기준표에서 충족되는 가장 높은 단계 (1~9). 채점할 때 필수
        title: 발명의 명칭 (보고서 제목)
        ipc_codes: IPC 코드 목록 (첫 번째가 주분류). 넣으면 T-B3(서브클래스 2개 이상)·M1(소비재·식품·농축산물 IPC)을 자동 판정
        filing_date: 출원일 (V-RAY 잔존 권리기간)
        registration_number: 등록번호 (V-RAY 권리 확정 여부)
        registration_date: 등록일
        abstract: 초록 (V-RAY 명세서 충실도, 실험 데이터 유무 판단)
        claims_count: 청구항 수 (기본 문구에만 사용, 점수에는 반영 안 함)
        summary_text: 요약서 본문 ('## 상용화전망' 섹션이 있으면 그 서술 단계로 TRL을 맞춤)
        technology_reason: 기술성 근거 2문장 (없으면 점수 구간별 기본 문구)
        market_reason: 시장성 근거 2문장
        business_reason: 사업성 근거 2문장
        trl_reason: TRL 근거 1문장
        analysis: 종합 의견 2문장
        as_of: 평가 기준일 (기본 오늘, 잔존 권리기간 계산)
    """
    if checked_items is None:
        return _rubric()
    if trl is None:
        return {
            "mode": "입력 필요",
            "error": "trl이 없습니다. trl_rules에서 충족되는 가장 높은 단계 하나를 trl(1~9)로 넣어 다시 부르십시오.",
            "trl_rules": {f"TRL {k}": v for k, v in cs.TRL_RULES.items()},
        }

    as_of = as_of or date.today()
    warnings: List[str] = []
    notes: List[str] = []
    ipc = [c.strip() for c in (ipc_codes or []) if c and c.strip()]

    # ---- 체크리스트 합산
    hits: Dict[str, str] = {}
    unknown = []
    for h in checked_items:
        hid = h.id.strip().upper()
        if hid not in cs.CHECKLIST_BY_ID:
            unknown.append(h.id)
            continue
        if hid in hits:
            warnings.append(f"{hid} 항목이 두 번 들어와 한 번만 반영했습니다.")
            continue
        hits[hid] = h.evidence.strip()
    if unknown:
        return {
            "mode": "입력 오류",
            "error": f"체크리스트에 없는 항목 ID: {', '.join(unknown)}. checked_items 없이 불러 기준표의 ID를 확인하십시오.",
        }

    if ipc:
        subclasses = {c.replace(" ", "")[:4].upper() for c in ipc}
        auto = {
            "T-B3": (len(subclasses) >= 2, f"IPC 서브클래스 {len(subclasses)}개 ({', '.join(sorted(subclasses))})"),
            "M1": (ipc[0].replace(" ", "")[:3].upper() in _FOOD_CLASSES, f"주분류 IPC {ipc[0]}"),
        }
        for hid, (ok, ev) in auto.items():
            if ok:
                hits[hid] = f"[IPC 자동 판정] {ev}"
            elif hid in hits:
                hits.pop(hid)
                notes.append(f"{hid}는 IPC로 자동 판정해 해당하지 않아 제외했습니다 ({ev}).")

    for a, b in (("T-A1", "T-A4"), ("T-B1", "T-B4"), ("T-C1", "T-C3"), ("M3", "M7"), ("M5", "M8")):
        if a in hits and b in hits:
            warnings.append(f"{a}(가점)와 {b}(감점)가 함께 선택됐습니다. 원문 근거를 다시 확인하십시오.")

    breakdown: Dict[str, List[Dict[str, Any]]] = {"technology": [], "market": [], "business": []}
    raw = {"technology": cs.BASE, "market": cs.BASE, "business": cs.BASE}
    for c in cs.CHECKLIST:
        if c["id"] in hits:
            raw[c["axis"]] += c["points"]
            breakdown[c["axis"]].append({"id": c["id"], "points": c["points"], "criterion": c["text"], "evidence": hits[c["id"]]})
    checklist_scores = {k: cs.clamp_score(v) for k, v in raw.items()}

    # ---- TRL: 요약서 상용화전망 서술과 정합성 (V-RAY 전에 적용)
    trl_final, trl_band, trl_changed = trl, None, False
    if summary_text:
        r = reconcile_trl(trl, summary_text)
        if r["changed"]:
            trl_final, trl_band, trl_changed = r["trl"], r["band"], True
            notes.append(f"요약서 상용화전망이 '{r['band'].label}' 단계로 서술돼 TRL {trl} → {trl_final}로 맞췄습니다.")

    # ---- V-RAY 사업성 보정
    vray = cs.vray_business_index(
        trl=trl_final,
        as_of=as_of,
        filing_date=filing_date,
        registration_number=registration_number,
        registration_date=registration_date,
        ipc_count=len(ipc),
        abstract_len=len(abstract or ""),
    )
    if not vray["term_known"]:
        warnings.append("출원일이 없어 V-RAY 잔존 권리기간을 20년(최대)으로 가정했습니다.")
    if not ipc:
        warnings.append("IPC가 없어 V-RAY 적용 폭을 0으로 계산했고, T-B3·M1은 선택한 항목 그대로 반영했습니다.")
    scores = {
        "technology": checklist_scores["technology"],
        "market": checklist_scores["market"],
        "business": cs.blend_business(checklist_scores["business"], vray["index"]),
    }

    # ---- 점수-문구 정합성
    reasons_in = {"technology": technology_reason or "", "market": market_reason or "", "business": business_reason or ""}
    adjustments = []
    reasons: Dict[str, str] = {}
    for axis in ("technology", "market", "business"):
        before = scores[axis]
        scores[axis] = cs.enforce_consistency(scores[axis], reasons_in[axis])
        if scores[axis] != before:
            adjustments.append(f"{cs.AXIS_LABEL[axis]} {before} → {scores[axis]} (근거 문장의 강한 긍정 표현에 맞춤)")
        text = cs.soften_if_overclaim(scores[axis], reasons_in[axis])
        reasons[axis] = cs.uplift_if_underclaim(scores[axis], text)
    total = cs.total_score(scores["technology"], scores["market"], scores["business"])

    # ---- 문구 후처리 (원본 순서)
    evidence_blob = " ".join([abstract or "", *hits.values()])
    has_data = bool(re.search(_DATA_RE, evidence_blob))
    multi_ipc = len({c[:1].upper() for c in ipc}) >= 2 or len(ipc) >= 2
    fallbacks = {
        "technology": cs.make_technology_fallback(scores["technology"], claims_count or 0, has_data, multi_ipc),
        "market": cs.make_market_fallback(scores["market"]),
        "business": cs.make_business_fallback(scores["business"]),
    }
    used_fallback = []
    for axis in ("technology", "market", "business"):
        out = cs.normalize_reason(reasons[axis], fallbacks[axis])
        if out == fallbacks[axis]:
            used_fallback.append(cs.AXIS_LABEL[axis])
        reasons[axis] = out
    if trl_changed:
        trl_text = describe_trl_from_stage(trl_final, trl_band)
    else:
        trl_text = cs.ensure_complete_sentence(trl_reason or "", cs.make_trl_fallback(trl_final))
    if any(int(n) != trl_final for n in re.findall(r"TRL\s*([0-9])", trl_text)):
        trl_text = cs.make_trl_fallback(trl_final)
    analysis_text = cs.normalize_analysis(analysis or "", cs.make_analysis_fallback(scores["technology"], scores["market"], scores["business"]))
    for axis in reasons:
        reasons[axis] = cs.strip_duration_mentions(cs.strip_score_mentions(cs.strip_trl_mentions(reasons[axis])))
    analysis_text = cs.strip_duration_mentions(cs.strip_score_mentions(analysis_text))

    appended = []
    for axis in reasons:
        if cs.AXIS_LABEL[axis] in used_fallback:
            continue  # 원본 기본 문구는 그대로 쓴다
        r = cs.ensure_conclusion(axis, scores[axis], reasons[axis])
        reasons[axis] = r["text"]
        if r["appended"]:
            appended.append(cs.AXIS_LABEL[axis])
    if used_fallback:
        notes.append(f"근거 문장이 없거나 규칙에 맞지 않아 기본 문구를 썼습니다: {', '.join(used_fallback)}")
    if appended:
        notes.append(f"점수 구간 결론 문장을 붙였습니다: {', '.join(appended)}")

    result = {
        "mode": "평가 결과",
        "patent_id": patent_id,
        "title": title or "",
        "total_score": total,
        "total_grade": cs.grade(total),
        "scores": {
            axis: {"score": scores[axis], "grade": cs.grade(scores[axis]), "checklist_score": checklist_scores[axis], "weight": cs.WEIGHTS[axis]}
            for axis in ("technology", "market", "business")
        },
        "trl": {"level": trl_final, "proposed": trl, "adjusted_by_summary": trl_changed, "reason": trl_text},
        "reasons": {"technology": reasons["technology"], "market": reasons["market"], "business": reasons["business"]},
        "analysis": analysis_text,
        "checklist_breakdown": breakdown,
        "vray": {
            "index": vray["index"],
            "stage": vray["stage"],
            "parts": vray["parts"],
            "registered": vray["registered"],
            "business_blend": f"체크리스트 {checklist_scores['business']} × 0.6 + V-RAY {vray['index']} × 0.4 → {cs.blend_business(checklist_scores['business'], vray['index'])}",
        },
        "consistency_adjustments": adjustments,
        "warnings": warnings,
        "notes": notes,
        "as_of": as_of.isoformat(),
        "score_version": cs.SCORE_VERSION,
        "disclaimer": "특허 문서 근거만으로 낸 1차 사업화 평가입니다. 공식 기술가치평가(금액 산정)나 시장 조사를 대신하지 않습니다.",
        "upstream": "patent-summary-wizard analyze-commercialization",
    }
    result["report_markdown"] = render_report(result)
    return result


def render_report(r: Dict[str, Any]) -> str:
    s, t = r["scores"], r["trl"]
    head = f"## 기술사업화 평가 — {r['title']} ({r['patent_id']})" if r["title"] else f"## 기술사업화 평가 — {r['patent_id']}"
    lines = [
        head,
        "",
        "| 구분 | 점수 | 등급 |",
        "|:---|---:|:---:|",
        f"| **종합** | **{r['total_score']}** | **{r['total_grade']}** |",
        f"| 기술성 (35%) | {s['technology']['score']} | {s['technology']['grade']} |",
        f"| 시장성 (35%) | {s['market']['score']} | {s['market']['grade']} |",
        f"| 사업성 (30%) | {s['business']['score']} | {s['business']['grade']} |",
        f"| 기술성숙도 | TRL {t['level']} | {r['vray']['stage']} |",
        "",
        "### 종합 의견",
        r["analysis"],
        "",
        "### 기술성",
        r["reasons"]["technology"],
        "",
        "### 시장성",
        r["reasons"]["market"],
        "",
        "### 사업성",
        r["reasons"]["business"],
        "",
        f"### 기술성숙도 (TRL {t['level']})",
        t["reason"],
        "",
        "### 채점 근거",
        "",
        "| 구분 | 항목 | 가감 | 원문 근거 |",
        "|:---|:---|---:|:---|",
    ]
    any_hit = False
    for axis, label in (("technology", "기술성"), ("market", "시장성"), ("business", "사업성")):
        for h in r["checklist_breakdown"][axis]:
            any_hit = True
            ev = h["evidence"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {label} | {h['id']} {h['criterion']} | {h['points']:+d} | {ev} |")
    if not any_hit:
        lines.append("| — | 원문으로 확인된 항목 없음 (기본 60점) | 0 | — |")
    v = r["vray"]
    p = v["parts"]
    lines += [
        "",
        "### 사업성 보정 (V-RAY 간이 기술가치평가 인자)",
        "",
        "| 인자 | 값 | 가중치 |",
        "|:---|---:|---:|",
        f"| 사업화 소요기간 (성숙도, {v['stage']} {p['lead']}년) | {p['maturity']:.2f} | 0.35 |",
        f"| 권리 유효성 ({'등록' if v['registered'] else '미등록'}) | {p['validity']:.2f} | 0.25 |",
        f"| 잔존 권리기간 ({p['remaining_years']:.1f}년) | {p['life_ratio']:.2f} | 0.20 |",
        f"| 권리 적용 폭 (IPC 수) | {p['breadth']:.2f} | 0.20 |",
        f"| **실행성 지수** | **{v['index']}** | |",
        "",
        f"사업성 = {v['business_blend']}",
        "",
        f"<sub>총점 = 기술성×0.35 + 시장성×0.35 + 사업성×0.30 · 각 항목 기본 60점, 55~95점 · 기준일 {r['as_of']} · 평가 규칙 {r['score_version']} · {r['disclaimer']}</sub>",
    ]
    return "\n".join(lines)
