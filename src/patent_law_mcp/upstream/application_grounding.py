"""활용 용도의 근거(청구항 명시 / 명세서 일반) 검증기.

포팅 원본: patent-summary-wizard/supabase/functions/summarize-patent/applicationGrounding.ts
모델이 제안한 용도 라벨은 원문 연속 발췌가 있을 때만 받아들인다.
"""

import re
from typing import Any, Dict, List, Optional

from patent_law_mcp.upstream.summary_grounding import GroundingSource

APPLICATION_GROUNDING_INSTRUCTION = """
[활용 용도 근거 구분 — 최우선]
농산업활용 가능성의 각 용도 문단 첫머리에 [[용도|청구항|용도명|원문 연속 발췌]] 또는 [[용도|명세서|용도명|원문 연속 발췌]]를 붙인다.
용도명은 발췌에 직접 등장하는 짧은 명사구로 쓴다. 발췌는 해당 청구항 또는 설명·초록의 연속된 원문 15~200자이며 요약하거나 재작성하지 않는다. |, 줄바꿈, ]]는 발췌에 넣지 않는다.
청구항에 용도가 직접 기재된 경우만 청구항으로 분류한다. 성분·균주·장치가 청구되었다는 이유만으로 명세서의 모든 용도가 청구된 것으로 간주하지 않는다.
설명·초록에만 등장한 용도는 명세서로 분류하고 청구항 권리범위와 동일시하지 않는다. 근거 없는 인접 분야 확장은 쓰지 않는다.
청구항 명시는 법적 권리범위 확정이나 등록·실시 보장을 의미하지 않는다. 해당 용도의 근거가 없으면 용도를 지어내지 말고 원문 확인이 필요하다고 쓴다."""

_MARKER_RE = re.compile(r"\[\[용도\|([^|\]\n]*)\|([^|\]\n]*)\|([^\]\n]*)\]\]")
_MALFORMED_RE = re.compile(r"\[\[용도[^\n]*(?:\]\]|\Z)")
_USE_WORD_RE = re.compile(r"(?:용|제조|생산|처리|방제|치료|예방|검출|진단|재배|발효|추출)")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def ground_applications(summary: str, source: Optional[GroundingSource]) -> Dict[str, Any]:
    """[[용도|구분|용도명|발췌]] 표식을 검증해 '청구항 명시 용도'·'명세서 일반 용도'·'용도 근거 미확인'으로 바꾼다."""
    applications: List[Dict[str, Any]] = []
    raw_claims = (source.claims if source else None) or ""
    claims = _normalize("\n".join(raw_claims) if isinstance(raw_claims, list) else raw_claims)
    description = _normalize("\n".join(p for p in ((source.abstract if source else None), (source.description if source else None)) if p))

    def replace(m: re.Match) -> str:
        kind, label, evidence = m.group(1), _normalize(m.group(2)), _normalize(m.group(3))
        valid = 2 <= len(label) <= 60 and 15 <= len(evidence) <= 200 and label in evidence
        in_claims = valid and kind == "청구항" and bool(_USE_WORD_RE.search(evidence)) and evidence in claims
        in_description = valid and evidence in description
        if not in_claims and not in_description:
            return "**용도 근거 미확인** — 아래 활용 설명은 원문 대조가 필요하다. "
        applications.append({
            "label": label,
            "claimed_in_claims": in_claims,
            "source": "claims" if in_claims else "description",
            "evidence": evidence,
        })
        return f"**{'청구항 명시 용도' if in_claims else '명세서 일반 용도'}: {label}**. "

    content = _MARKER_RE.sub(replace, summary)
    # 형식이 깨진 표식은 확정된 청구 용도로 노출하지 않는다.
    return {"content": _MALFORMED_RE.sub("용도 근거 미확인. ", content), "applications": applications}
