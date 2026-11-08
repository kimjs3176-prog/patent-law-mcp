"""특허 분석 및 요약 실무 도구

원칙: 원문(명칭·초록·청구항·명세서)에 있는 문장만 발췌·재배열합니다.
원문에서 찾지 못한 항목은 지어내지 않고 '미확인'으로 표시합니다.
"""

import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import Field

from patent_law_mcp.tools.claim_utils import (
    detect_technology_kind,
    is_deleted_claim,
    is_dependent_claim,
    normalize_ws,
    split_claim_elements,
    TECH_TYPE_LABELS,
)


class GroundingCorrector:
    """원문에 없는 '효과 수치'를 정성적 표현으로 바꾸는 결정론적 보정기"""

    EFFECT_VERBS = r"(?:절감|감소|감축|저감|향상|증가|증대|개선|단축|방지|억제|줄|높|낮|늘|상승|하락|제고|축소|완화|경감)"
    NUM = r"\d+(?:[.,]\d+)*"
    RANGE = rf"{NUM}(?:\s*[~∼～〜\-–]\s*{NUM})?"
    QUALIFIER = r"(?:이상|이하|가량|내외|정도|수준|까지|가까이|남짓)"

    EFFECT_FIGURE_RE = re.compile(
        rf"(?:(?:기존|종전|관행|일반)\s*(?:[가-힣]{{1,6}}\s*)?대비\s*)?(?:약\s*|최대\s*|평균\s*)?({RANGE})\s*(%|배)\s*{QUALIFIER}?\s*(?:의\s*)?(?=\**\s*{EFFECT_VERBS})",
    )

    @staticmethod
    def _norm(text: str) -> str:
        text = re.sub(r"[∼～〜\-–]", "~", text or "")
        return re.sub(r"[\s,]", "", text)

    @classmethod
    def check(cls, summary_text: str, source_text: str) -> Dict[str, Any]:
        source_norm = cls._norm(source_text)
        removed: List[str] = []
        kept: List[str] = []

        def replacer(match: re.Match) -> str:
            figure, unit = match.group(1), match.group(2)
            if cls._norm(figure + unit) in source_norm:
                kept.append(f"{figure}{unit}")
                return match.group(0)
            removed.append(f"{figure}{unit}")
            return "유의미한 수준으로 " if unit == "%" else "상당한 수준으로 "

        sanitized = cls.EFFECT_FIGURE_RE.sub(replacer, summary_text)
        return {"sanitized_text": re.sub(r" {2,}", " ", sanitized), "removed_figures": removed, "kept_figures": kept}

    @classmethod
    def sanitize_unverified_figures(cls, summary_text: str, source_text: str) -> str:
        return cls.check(summary_text, source_text)["sanitized_text"]


def ground_summary_figures(
    summary_text: Annotated[str, Field(min_length=1)],
    source_text: Annotated[str, Field(min_length=1)],
) -> Dict[str, Any]:
    """LLM 등이 작성한 요약문에서 원문에 없는 효과 수치(예: '30% 절감', '2배 향상')를 찾아 정성적 표현으로 바꿉니다.

    Args:
        summary_text: 점검할 요약문
        source_text: 대조할 특허 원문(초록·청구항·명세서)
    """
    result = GroundingCorrector.check(summary_text, source_text)
    result["note"] = (
        "'수치 + %/배 + 효과 동사' 형태만 점검합니다. 다른 형태의 수치나 정성적 과장 표현은 사람이 확인해야 합니다."
    )
    return result


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

    verb_re = re.compile(GroundingCorrector.EFFECT_VERBS)
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
        "warnings": warnings,
        "notice": "원문 문장을 발췌·재배열한 자동 초안입니다. 대외 배포 전 원문과 대조하십시오.",
    }


EvidenceLevel = Literal["unknown", "concept", "lab_validated", "prototype", "field_validated", "commercial"]

_TRL_BY_EVIDENCE = {
    "concept": ("TRL 1~3", "기초 원리·개념 수준 (실험 검증 전)"),
    "lab_validated": ("TRL 3~4", "실험실 규모 성능 검증"),
    "prototype": ("TRL 5~6", "시제품 제작 및 유사 환경 성능 검증"),
    "field_validated": ("TRL 7", "실제 운용 환경(현장) 실증 완료"),
    "commercial": ("TRL 8~9", "제품화·양산 또는 판매 실적 보유"),
}


def evaluate_commercialization(
    technology_domain: str,
    evidence_level: EvidenceLevel = "unknown",
    target_market: Optional[str] = None,
    evidence_note: Optional[str] = None,
) -> Dict[str, Any]:
    """확인된 실증 근거 수준으로 기술성숙도(TRL) 범위를 판정합니다.

    Args:
        technology_domain: 기술 분야
        evidence_level: 확인된 근거 수준 ("unknown"(모름), "concept"(개념), "lab_validated"(실험실 검증),
            "prototype"(시제품 검증), "field_validated"(현장 실증), "commercial"(제품화·판매))
        target_market: 목표 시장 (선택)
        evidence_note: 근거 자료 메모 (예: "2024년 농가 3곳 현장 실증 보고서")
    """
    checkpoints = [
        "원료 수급 안정성 및 제조 단가",
        "해당 시 인허가·등록 규제(농약관리법·비료관리법·식품위생법 등) 소요 기간",
        "수요기업 기술이전 시 실시권 유형(통상/전용) 및 절차",
    ]

    if evidence_level == "unknown":
        return {
            "technology_domain": technology_domain,
            "target_market": target_market or "미지정",
            "estimated_trl": None,
            "trl_description": "TRL 미산정: 실증 근거(시제품·현장실증·판매 실적 등) 정보가 없습니다.",
            "how_to_assess": "evidence_level에 확인된 근거 수준을 지정하면 TRL 범위를 산정합니다.",
            "key_checkpoints": checkpoints,
        }

    trl, desc = _TRL_BY_EVIDENCE[evidence_level]
    return {
        "technology_domain": technology_domain,
        "target_market": target_market or "미지정",
        "estimated_trl": trl,
        "trl_description": desc,
        "evidence_basis": evidence_note or "근거 자료 미기재 (판정 근거를 함께 기록하십시오)",
        "key_checkpoints": checkpoints,
    }
