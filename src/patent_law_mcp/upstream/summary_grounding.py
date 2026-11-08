"""원문에 없는 '효과 수치'를 요약서에서 걷어내는 결정론적 보정기.

포팅 원본: patent-summary-wizard/supabase/functions/summarize-patent/summaryGrounding.ts
(정규식·판정 순서·대체 문구를 원본과 같게 유지합니다. JS의 \\d는 ASCII 숫자이므로 [0-9]로 옮겼습니다.)

원문(초록·청구항·설명)에 없는 "30% 이상 감소", "약제 낭비를 15% 이상 방지", "손실률을 5% 미만으로 억제"처럼
AI가 지어낸 정량 효과는 사실로 읽히기 쉬우므로, 수치를 뺀 정성 표현으로 남긴다.
원문에 있는 수치(청구항의 배합비·회복률 등)와 시장 섹션은 건드리지 않는다.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Union


@dataclass
class GroundingSource:
    title: Optional[str] = None
    abstract: Optional[str] = None
    claims: Union[List[str], str, None] = None
    description: Optional[str] = None


@dataclass
class SourceFigures:
    percent: Set[str] = field(default_factory=set)
    times: Set[str] = field(default_factory=set)


# 효과 수치를 검사하는 섹션(발명요약·농산업활용·상용화전망·기술분야). 관련시장 동향은 제외한다.
EFFECT_SECTION_RE = re.compile(
    r"(^##[ \t]*(?:기술\s*분야|발명\s*요약|농산업\s*활용|상용화\s*전망)[^\n]*\n)([\s\S]*?)(?=^##\s|\Z)", re.M
)

NUM = r"[0-9]+(?:[.,][0-9]+)*"
RANGE = rf"{NUM}(?:\s*[~∼～〜\-–]\s*{NUM})?"
EFFECT_VERB = r"(?:절감|감소|감축|저감|향상|증가|증대|개선|단축|방지|억제|줄|높|낮|늘|상승|하락|제고|축소|완화|경감)"
QUALIFIER = r"(?:이상|이하|가량|내외|정도|수준|까지|가까이|남짓)"

EFFECT_FIGURE_RE = re.compile(
    rf"(?:(?:기존|종전|관행|일반)\s*(?:[가-힣]{{1,6}}\s*)?대비\s*)?(?:약\s*|최대\s*|평균\s*)?({RANGE})\s*(%|배)\s*{QUALIFIER}?\s*(?:의\s*)?(?=\**\s*{EFFECT_VERB})"
)
CEILING_RE = re.compile(rf"(?:약\s*)?({RANGE})\s*%\s*(?:미만|이하|이내)(\**)\s*(으로|로)(?=\s)")
FLOOR_NOUN_RE = re.compile(
    rf"(?:약\s*)?({RANGE})\s*%\s*(?:이상|대)의\s*(?=\**\s*(?:신뢰도|정확도|정확성|판별률|판별\s*정확도|재현성|검출률|회수율|생존율|순도|효율))"
)
OTHER_EFFECT_FIGURE_RE = re.compile(
    rf"(?:약\s*|최대\s*|평균\s*)?({RANGE})\s*(시간|분|초|일|개월|년|회|원|kWh|킬로와트시)\s*{QUALIFIER}?\s*(?:의\s*)?(?=\**\s*{EFFECT_VERB})"
)
REVERSE_EFFECT_RE = re.compile(rf"({EFFECT_VERB}[가-힣]*\s*(?:효과|율|률)?\s*(?:은|는|이|가|:)?\s*)(?:약\s*)?({RANGE})\s*(%|배)")

_METRIC_RE = re.compile(
    r"(?:[가-힣]{0,8}(?:비용|수율|효율|정확도|신뢰도|회복률|회수율|생존율|순도|손실률|실패율|이병률|살포량|시간|에너지|소비량|노동력|감염|항균활성))"
)
_SENTENCE_RE = re.compile(r"[\s\S]+?(?:[.!?](?=\s|\Z)|\n|\Z)")
_PERF_NOUN_RE = re.compile(r"(?:회복률|회수율|정확도|신뢰도|효율|수율|생존율|순도)")
_LABEL_RE = re.compile(r"^\s*\*\*(?:청구항 명시 용도|명세서 일반 용도):[^*]+\*\*\.\s*")


def source_text(src: Optional[GroundingSource]) -> str:
    if not src:
        return ""
    claims = "\n".join(src.claims) if isinstance(src.claims, list) else str(src.claims or "")
    return "\n".join(p for p in (src.title, src.abstract, claims, src.description) if p)


def _norm_num(n: str) -> str:
    return re.sub(r"^0+(?=[0-9])", "", n.replace(",", ""))


def source_figures(src: Optional[GroundingSource]) -> SourceFigures:
    """원문에서 단위와 함께 쓰인 수치를 모은다(%·배). '73 내지 100%' 같은 범위의 하한도 포함한다."""
    text = source_text(src)

    def collect(unit: str) -> Set[str]:
        out: Set[str] = set()
        pattern = re.compile(rf"({NUM})(?:\s*(?:[~∼～〜\-–]|내지|에서|부터)\s*({NUM}))?\s*(?:{unit})")
        for m in pattern.finditer(text):
            out.add(_norm_num(m.group(1)))
            if m.group(2):
                out.add(_norm_num(m.group(2)))
        return out

    return SourceFigures(percent=collect("%|퍼센트|중량%|wt%"), times=collect("배"))


def _range_supported(rng: str, unit: str, figs: SourceFigures) -> bool:
    pool = figs.times if unit == "배" else figs.percent
    return all(_norm_num(n) in pool for n in re.split(r"\s*[~∼～〜\-–]\s*", rng))


def metric_terms(text: str) -> List[str]:
    return _METRIC_RE.findall(text)


def sentences(text: str) -> List[str]:
    return _SENTENCE_RE.findall(text)


def _contextual_support(rng: str, unit: str, sentence: str, src: GroundingSource) -> bool:
    """수치가 같다는 것만으로는(예: 성분 농도) 성능 근거가 아니다 — 같은 지표 문장에 있어야 한다."""
    terms = metric_terms(sentence)
    for excerpt in sentences(source_text(src)):
        if not _range_supported(rng, unit, source_figures(GroundingSource(description=excerpt))):
            continue
        if not re.search(EFFECT_VERB, excerpt) and not _PERF_NOUN_RE.search(excerpt):
            continue
        if any(word in terms for word in metric_terms(excerpt)):
            return True
    return False


def strip_unsupported_effect_figures(summary: str, src: Optional[GroundingSource]) -> str:
    """기술분야·발명요약·농산업활용·상용화전망 섹션에서 원문에 없는 효과 수치(%, 배, 시간 등)를 빼고 정성 표현으로 바꾼다.

    원문을 알 수 없으면(빈 원문) 판단하지 않고 그대로 둔다.
    """
    if not summary:
        return summary
    if not source_text(src).strip():
        return summary
    assert src is not None

    def fix_sentence(sentence: str) -> str:
        changed = False

        def effect(m: re.Match) -> str:
            nonlocal changed
            if _contextual_support(m.group(1), m.group(2), sentence, src):
                return m.group(0)
            changed = True
            return ""

        def ceiling(m: re.Match) -> str:
            nonlocal changed
            if _contextual_support(m.group(1), "%", sentence, src):
                return m.group(0)
            changed = True
            josa = m.group(3)
            return f"확인되지 않은 수준{m.group(2)}{'으로' if josa == '로' else josa}"

        def floor(m: re.Match) -> str:
            nonlocal changed
            if _contextual_support(m.group(1), "%", sentence, src):
                return m.group(0)
            changed = True
            return "검증이 필요한 "

        def other(m: re.Match) -> str:
            nonlocal changed
            rng, unit = m.group(1), m.group(2)
            figure = re.compile(rf"{re.escape(rng)}\s*{re.escape(unit)}")
            supported = any(
                figure.search(excerpt)
                and re.search(EFFECT_VERB, excerpt)
                and any(term in metric_terms(sentence) for term in metric_terms(excerpt))
                for excerpt in sentences(source_text(src))
            )
            if supported:
                return m.group(0)
            changed = True
            return ""

        def reverse(m: re.Match) -> str:
            nonlocal changed
            if _contextual_support(m.group(2), m.group(3), sentence, src):
                return m.group(0)
            changed = True
            return m.group(1) + "추가 검증 필요"

        out = EFFECT_FIGURE_RE.sub(effect, sentence)
        out = CEILING_RE.sub(ceiling, out)
        out = FLOOR_NOUN_RE.sub(floor, out)
        out = OTHER_EFFECT_FIGURE_RE.sub(other, out)
        out = REVERSE_EFFECT_RE.sub(reverse, out)
        if not changed:
            return sentence
        # 지어낸 수치를 '유의미한 개선'처럼 똑같이 지어낸 정성 표현으로 바꾸지 않는다.
        label = _LABEL_RE.match(sentence)
        metrics = metric_terms(sentence)
        subject = f"{metrics[0]} 관련 효과는" if metrics else "해당 효과는"
        lead = " " if sentence.startswith(" ") else ""
        tail = "\n" if sentence.endswith("\n") else " "
        return f"{lead}{label.group(0) if label else ''}{subject} 원문에 정량 근거가 없어 추가 검증이 필요하다.{tail}"

    def fix_section(m: re.Match) -> str:
        heading, body = m.group(1), m.group(2)
        return heading + "".join(fix_sentence(s) for s in sentences(body))

    return EFFECT_SECTION_RE.sub(fix_section, summary)
