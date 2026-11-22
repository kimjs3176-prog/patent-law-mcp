"""요약문 수치 근거 확인

작성된 요약문에서 원문에 정량 근거가 없는 효과 수치('30% 절감', '2배 향상' 등)를 찾아 해당 문장을
'추가 검증 필요' 문장으로 바꿉니다. 판정 규칙은 patent-summary-wizard summaryGrounding.ts를 옮긴 것입니다
(upstream/summary_grounding.py, scripts/sync_upstream.py로 변경 추적).
"""

import re
from typing import Annotated, Any, Dict, List, Literal

from pydantic import Field

from patent_law_mcp.upstream import summary_grounding

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
