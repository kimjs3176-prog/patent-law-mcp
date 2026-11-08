"""특허 분석 및 요약 실무 도구

원칙: 원문(명칭·초록·청구항·명세서)에 있는 문장만 발췌·재배열합니다.
원문에서 찾지 못한 항목은 지어내지 않고 '미확인'으로 표시합니다.
"""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from patent_law_mcp.tools.claim_utils import (
    detect_technology_kind,
    is_deleted_claim,
    is_dependent_claim,
    normalize_ws,
    split_claim_elements,
    TECH_TYPE_LABELS,
)
from patent_law_mcp.upstream import application_grounding, summary_grounding, trl_consistency
from patent_law_mcp.upstream.video_signature import recommend_video_signature


_FIGURE_TOKEN_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)*(?:\s*[~∼～〜\-–]\s*[0-9]+(?:[.,][0-9]+)*)?\s*(?:%|배|시간|분|초|일|개월|년|회|원|kWh|킬로와트시)")


def _figure_tokens(text: str) -> List[str]:
    return [re.sub(r"\s+", "", t) for t in _FIGURE_TOKEN_RE.findall(text)]


SectionMode = Literal["auto", "sections_only", "whole_text"]


def ground_summary_figures(
    summary_text: Annotated[str, Field(min_length=1)],
    source_text: Annotated[str, Field(min_length=1)],
    section_mode: SectionMode = "auto",
) -> Dict[str, Any]:
    """작성된 요약문에서 원문에 없는 효과 수치('30% 절감', '2배 향상', '3시간 단축', '99% 이상의 신뢰도' 등)를 찾아,
    해당 문장을 '원문에 정량 근거가 없어 추가 검증이 필요하다'로 바꿉니다. (patent-summary-wizard summaryGrounding 포팅)

    원문의 같은 지표 문장에 같은 수치가 있을 때만 수치를 남깁니다 (성분 농도 등 다른 맥락의 같은 숫자는 근거로 보지 않음).

    Args:
        summary_text: 점검할 요약문
        source_text: 대조할 특허 원문 (초록·청구항·명세서)
        section_mode: "auto"(요약문에 '## 발명요약' 같은 제목이 있으면 그 섹션만, 없으면 전체),
            "sections_only"(업스트림과 같이 기술분야·발명요약·농산업활용·상용화전망 섹션만), "whole_text"(전체)
    """
    has_sections = bool(summary_grounding.EFFECT_SECTION_RE.search(summary_text))
    whole = section_mode == "whole_text" or (section_mode == "auto" and not has_sections)
    src = summary_grounding.GroundingSource(description=source_text)
    if whole:
        wrapped = f"## 발명요약\n{summary_text}"
        sanitized = summary_grounding.strip_unsupported_effect_figures(wrapped, src)[len("## 발명요약\n"):]
    else:
        sanitized = summary_grounding.strip_unsupported_effect_figures(summary_text, src)

    before, after = _figure_tokens(summary_text), _figure_tokens(sanitized)
    removed = list(before)
    for t in after:
        if t in removed:
            removed.remove(t)
    return {
        "sanitized_text": sanitized,
        "changed": sanitized != summary_text,
        "removed_figures": removed,
        "scope": "전체 텍스트" if whole else "기술분야·발명요약·농산업활용·상용화전망 섹션",
        "upstream": "patent-summary-wizard summaryGrounding.ts",
    }


class ProposedApplication(BaseModel):
    kind: Literal["청구항", "명세서"] = Field(..., description="제안 근거: 청구항 또는 명세서")
    label: str = Field(..., description="용도명 (발췌에 그대로 나오는 짧은 명사구)")
    evidence: str = Field(..., description="원문 연속 발췌 15~200자 (요약·재작성 금지)")


def ground_patent_applications(
    applications: Annotated[List[ProposedApplication], Field(min_length=1)],
    claims: List[str],
    abstract: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """제안된 활용 용도마다 원문 발췌를 대조해 '청구항 명시 용도'·'명세서 일반 용도'·'근거 미확인'으로 분류합니다.
    (patent-summary-wizard applicationGrounding 포팅)

    청구항에 용도가 직접 적혀 있고 발췌가 청구항 원문과 일치할 때만 청구항 명시 용도로 인정합니다.

    Args:
        applications: 제안 용도 목록 [{kind, label, evidence}]
        claims: 청구항 원문 목록
        abstract: 초록
        description: 명세서 본문
    """
    items = [a if isinstance(a, ProposedApplication) else ProposedApplication.model_validate(a) for a in applications]
    src = summary_grounding.GroundingSource(abstract=abstract, claims=claims, description=description)
    results = []
    for a in items:
        grounded = application_grounding.ground_applications(f"[[용도|{a.kind}|{a.label}|{a.evidence}]]", src)
        hit = grounded["applications"][0] if grounded["applications"] else None
        results.append({
            "label": a.label,
            "proposed_as": a.kind,
            "verdict": ("청구항 명시 용도" if hit["claimed_in_claims"] else "명세서 일반 용도") if hit else "근거 미확인",
            "claimed_in_claims": bool(hit and hit["claimed_in_claims"]),
            "evidence": a.evidence,
        })
    return {
        "applications": results,
        "rule": "청구항 명시는 법적 권리범위 확정이나 등록·실시 보장을 뜻하지 않습니다.",
        "upstream": "patent-summary-wizard applicationGrounding.ts",
    }


_RANGE = r"\d+(?:\.\d+)?(?:\s*[~∼～\-]\s*\d+(?:\.\d+)?)?"
_SPEC_PATTERNS = [
    ("온도 조건", re.compile(rf"({_RANGE})\s*(℃|°C|도씨)")),
    ("파장", re.compile(rf"({_RANGE})\s*(nm)\b")),
    ("처리 시간", re.compile(rf"({_RANGE})\s*(시간|분간|초간|일간|분|초)(?![가-힣])")),
    ("농도/배합비", re.compile(rf"({_RANGE})\s*(wt%|중량\s*%|중량부|%\s*\(v/v\)|%|ppm)")),
    ("운전 조건", re.compile(rf"({_RANGE})\s*(bar|MPa|kPa|rpm|L/min)\b")),
]


def extract_key_spec_chips(source_text: str, limit: int = 6) -> List[Dict[str, str]]:
    """원문에 적힌 수치 파라미터(온도·파장·시간·농도·운전조건)를 발췌합니다. 없으면 빈 목록을 반환합니다."""
    chips: List[Dict[str, str]] = []
    seen = set()
    for key, pattern in _SPEC_PATTERNS:
        for m in pattern.finditer(source_text):
            value = normalize_ws(f"{m.group(1)}{m.group(2)}")
            if (key, value) in seen:
                continue
            seen.add((key, value))
            start, end = max(0, m.start() - 15), min(len(source_text), m.end() + 10)
            chips.append({"key": key, "value": value, "context": normalize_ws(source_text[start:end])})
            if len(chips) >= limit:
                return chips
    return chips


def _section(text: str, start_pattern: str, end_pattern: str) -> str:
    m = re.search(rf"(?:{start_pattern})\s*([\s\S]*?)(?=(?:{end_pattern})|\Z)", text)
    return normalize_ws(m.group(1)) if m else ""


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.다])\s+", normalize_ws(text)) if len(s.strip()) > 10]


def _extract_effect(abstract: str, description: str) -> Optional[str]:
    effect_section = _section(
        description,
        r"【발명의\s*효과】|발명의\s*효과",
        r"【도면의\s*간단한\s*설명】|도면의\s*간단한\s*설명|【발명을\s*실시하기|발명을\s*실시하기|【|\Z",
    )
    if effect_section:
        return " ".join(_sentences(effect_section)[:2]) or effect_section[:200]

    verb_re = re.compile(summary_grounding.EFFECT_VERB)
    for text in (description, abstract):
        hits = [s for s in _sentences(text) if "효과" in s or verb_re.search(s)]
        if hits:
            return " ".join(hits[:2])
    return None


def _extract_problem(abstract: str, description: str) -> Dict[str, str]:
    problem = _section(
        description,
        r"【해결하(?:고자|려는)\s*(?:하는\s*)?과제】|해결하(?:고자|려는)\s*(?:하는\s*)?과제",
        r"【과제의\s*해결\s*수단】|과제의\s*해결\s*수단|【발명의\s*효과】|발명의\s*효과|【",
    )
    if problem:
        return {"text": problem[:300], "source": "명세서 '해결하려는 과제' 발췌"}
    first = _sentences(abstract)[:1]
    if first:
        return {"text": first[0][:300], "source": "초록 첫 문장 발췌 (과제 항목 미기재)"}
    return {"text": "", "source": "미확인"}


def summarize_patent(
    patent_id: str,
    title: str,
    abstract: str,
    claims: Annotated[List[str], Field(min_length=1)],
    description: Optional[str] = None,
    applicant: Optional[str] = None,
) -> Dict[str, Any]:
    """특허 원문(명칭·초록·청구항·명세서)에서 문장을 발췌해 기술이전 상담용 요약 초안을 만듭니다.

    원문에 없는 효과·수치는 만들지 않으며, 찾지 못한 항목은 '미확인'으로 표시합니다.
    """
    description = description or ""
    clean_claims = [c.strip() for c in claims if c and c.strip()]
    active = [c for c in clean_claims if not is_deleted_claim(c)]
    independent = [c for c in active if not is_dependent_claim(c)]
    main_claim = independent[0] if independent else (active[0] if active else "")

    warnings: List[str] = []
    if not main_claim:
        warnings.append("유효한 청구항이 없어 권리범위 요약을 만들지 못했습니다.")
    if not abstract.strip():
        warnings.append("초록이 비어 있습니다.")

    kind = detect_technology_kind(title, main_claim)
    tech_type = TECH_TYPE_LABELS[kind]
    elements, subject = split_claim_elements(main_claim) if main_claim else ([], "")
    is_process = kind in ("method", "mixed") and any("단계" in e for e in elements)
    label = "단계" if is_process else "구성"

    components = [
        {"step": f"{label} {idx}", "description": e[:80] + ("..." if len(e) > 80 else "")}
        for idx, e in enumerate(elements, start=1)
    ]

    source_full = "\n".join([title, abstract, "\n".join(clean_claims), description])
    effect = _extract_effect(abstract, description)

    pitch = [f"[도입] {title} 기술입니다."]
    if elements:
        short = ", ".join(re.sub(r"^상기\s*", "", e)[:25] for e in elements[:4])
        josa = "로" if label == "단계" else "으로"
        pitch.append(f"[핵심] 독립항은 {len(elements)}개 {label}{josa} 이루어집니다: {short}{' 등' if len(elements) > 4 else ''}.")
    pitch.append(f"[효과] {effect}" if effect else "[효과] (명세서의 '발명의 효과'를 확인해 기재하십시오)")
    pitch.append("[제안] 기술실시계약을 통한 도입을 상담하실 수 있습니다.")

    return {
        "patent_id": patent_id,
        "title": title,
        "applicant": applicant or "미기재",
        "technology_type": tech_type,
        "claimed_subject_matter": subject or "미확인",
        "core_problem": _extract_problem(abstract, description),
        "technical_solution": main_claim[:300] + ("..." if len(main_claim) > 300 else ""),
        "workflow_or_components": components,
        "key_spec_chips": extract_key_spec_chips(source_full),
        "primary_effect": {
            "text": effect or "원문에서 효과 기재를 찾지 못했습니다 (명세서 확인 필요).",
            "source": "원문 발췌" if effect else "미확인",
        },
        "claims_overview": {
            "total": len(clean_claims),
            "deleted": len(clean_claims) - len(active),
            "independent": len(independent),
        },
        "elevator_pitch_draft": pitch,
        "video_signature_hint": recommend_video_signature(title, clean_claims, abstract),
        "warnings": warnings,
        "notice": "원문 문장을 발췌·재배열한 자동 초안입니다. 대외 배포 전 원문과 대조하십시오.",
    }


EvidenceLevel = Literal["unknown", "concept", "lab_validated", "prototype", "field_validated", "commercial"]

# 근거 수준 -> TRL 범위 (patent-summary-wizard TRL_REFERENCE_LEVELS 용어 기준)
_TRL_BY_EVIDENCE = {
    "concept": (2, 3, "기술개념 정립~개념 실증 (실험 검증 전)"),
    "lab_validated": (3, 4, "연구실 규모 기본·핵심성능 검증"),
    "prototype": (5, 6, "시작품 제작·파일럿 규모 성능 평가"),
    "field_validated": (7, 7, "실사용 환경 신뢰성 검증·수요처 평가"),
    "commercial": (8, 9, "인증·표준화 또는 양산·판매"),
}


def _trl_range(lo: int, hi: int) -> str:
    return f"TRL {lo}" if lo == hi else f"TRL {lo}~{hi}"


def evaluate_commercialization(
    technology_domain: str,
    evidence_level: EvidenceLevel = "unknown",
    target_market: Optional[str] = None,
    evidence_note: Optional[str] = None,
    commercialization_outlook: Optional[str] = None,
    proposed_trl: Annotated[Optional[int], Field(ge=1, le=9)] = None,
) -> Dict[str, Any]:
    """확인된 실증 근거 수준, 또는 요약서 '상용화전망' 서술로 기술성숙도(TRL)를 판정합니다.

    commercialization_outlook을 주면 patent-summary-wizard trlConsistency와 같은 규칙으로 '현재 도달한 단계'를 찾고
    (목표·예정·경쟁 기술 서술은 제외), proposed_trl이 그 단계 범위를 벗어나면 범위 안으로 보정합니다.

    Args:
        technology_domain: 기술 분야
        evidence_level: 확인된 근거 수준 ("unknown", "concept", "lab_validated", "prototype", "field_validated", "commercial")
        target_market: 목표 시장 (선택)
        evidence_note: 근거 자료 메모 (예: "2024년 농가 3곳 현장 실증 보고서")
        commercialization_outlook: 요약서의 상용화전망 문단 (선택)
        proposed_trl: 검토할 TRL 값 1~9 (선택, commercialization_outlook과 함께 쓰면 정합성 보정)
    """
    checkpoints = [
        "원료 수급 안정성 및 제조 단가",
        "해당 시 인허가·등록 규제(농약관리법·비료관리법·식품위생법 등) 소요 기간",
        "수요기업 기술이전 시 실시권 유형(통상/전용) 및 절차",
    ]
    result: Dict[str, Any] = {
        "technology_domain": technology_domain,
        "target_market": target_market or "미지정",
        "key_checkpoints": checkpoints,
    }

    if commercialization_outlook:
        text = commercialization_outlook
        if not trl_consistency.find_commercialization_section(text):
            text = f"## 상용화전망\n{text}"
        band = trl_consistency.detect_summary_maturity(text)
        if band and proposed_trl is not None:
            rec = trl_consistency.reconcile_trl(proposed_trl, text)
            result.update({
                "estimated_trl": f"TRL {rec['trl']}",
                "trl_adjusted": rec["changed"],
                "proposed_trl": proposed_trl,
                "trl_description": trl_consistency.describe_trl_from_stage(rec["trl"], band),
                "reference_levels": trl_consistency.reference_levels(rec["trl"], rec["trl"]),
            })
        elif band:
            result.update({
                "estimated_trl": _trl_range(band.min, band.max),
                "trl_description": f"상용화전망이 기술완성도를 '{band.label}' 단계로 서술합니다.",
                "reference_levels": trl_consistency.reference_levels(band.min, band.max),
            })
        else:
            result.update({
                "estimated_trl": f"TRL {proposed_trl}" if proposed_trl else None,
                "trl_description": "상용화전망에서 현재 도달 단계 서술(실험실·파일럿·양산 준비 등)을 찾지 못했습니다.",
            })
        result["stage_rule"] = "patent-summary-wizard trlConsistency.ts (현재·과거로 서술된 최고 단계, 목표·예정·경쟁 기술 제외)"
        return result

    if evidence_level == "unknown":
        result.update({
            "estimated_trl": f"TRL {proposed_trl}" if proposed_trl else None,
            "trl_description": "TRL 미산정: 실증 근거(시제품·현장실증·판매 실적 등) 정보가 없습니다."
            if not proposed_trl
            else "제시된 TRL을 확인할 근거 정보가 없습니다.",
            "how_to_assess": "evidence_level 또는 commercialization_outlook을 주면 TRL 범위를 산정합니다.",
        })
        return result

    lo, hi, desc = _TRL_BY_EVIDENCE[evidence_level]
    result.update({
        "estimated_trl": _trl_range(lo, hi),
        "trl_description": desc,
        "reference_levels": trl_consistency.reference_levels(lo, hi),
        "evidence_basis": evidence_note or "근거 자료 미기재 (판정 근거를 함께 기록하십시오)",
    })
    if proposed_trl is not None and not lo <= proposed_trl <= hi:
        result["proposed_trl_note"] = f"제시된 TRL {proposed_trl}은(는) 근거 수준({_trl_range(lo, hi)})과 맞지 않습니다."
    return result
