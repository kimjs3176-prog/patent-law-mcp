"""특허 기술소개영상 '시그니처' 유형 추천.

포팅 원본: patent-video-skill/references/CONTENT_SPEC.md
- '특징 구조화 > 3. 유형 고르기' 표의 유형 선택 규칙
- 'claim'(범용) 유형의 청구항 구조(전제부·구성요소·종속항) 데이터
- '절대 규칙 (사실성)' 요약

영상 생성기(patent-video-skill)가 받을 content JSON을 대신 만들지는 않으며,
유형 선택 근거와 청구항 구조만 제공합니다. 실제 작성은 CONTENT_SPEC.md를 따릅니다.
"""

import re
from typing import Any, Dict, List, Optional

from patent_law_mcp.tools.claim_utils import (
    APPARATUS_WORDS,
    detect_technology_kind,
    is_deleted_claim,
    is_dependent_claim,
    split_claim_elements,
)

SIGNATURE_TYPES = {
    "journey": "식품·가공·추출·발효 공정 — 재료가 단계마다 모양을 바꾸며 온도 그래프를 따라간다",
    "loop": "장치·설비·재배 시스템·센서·SW 제어 — 도면 위로 매질이 실제 경로를 흐르고 제어 루프나 단계가 돈다",
    "sequence": "프라이머·마커·진단 키트 — 실제 염기가 찍히고 표적 부위가 켜진 뒤 명세서의 판독 방식으로 결과가 나온다",
    "formula": "조성물·배합 — 성분이 비율대로 채워지고 효능이 대조군 대비 막대로",
    "lineage": "품종·육종, 분리·선발 균주 — 교배 부모(분리원) → 세대·선발 단계 → 신품종·균주",
    "claim": "범용 — 독립항이 구성요소별로 조립되고 특징부가 빛난 뒤 종속항이 가지로 자란다",
}

FACTUALITY_RULES = [
    "모든 수치·조건·효과는 명세서·청구항에 적힌 그대로 쓴다. 계산해서 새 주장을 만들지 않는다.",
    "명세서에 없는 효과·시장·매출·인증은 쓰지 않는다.",
    "청구항에 직접 포함된 용도만 apps의 claim: true로 표시한다 (최대 3개).",
    "도면 좌표·경로는 도면을 직접 열어 찍는다 (추정 금지).",
]

_SEQUENCE_RE = re.compile(r"프라이머|분자\s*마커|마커\s*세트|염기\s*서열|서열\s*번호|PCR|진단\s*키트|검출용\s*(?:조성물|키트)")
_LINEAGE_TITLE_RE = re.compile(r"품종|육종|교배")
_STRAIN_RE = re.compile(r"균주")
_STRAIN_SELECT_RE = re.compile(r"분리|선발|신규")
_RATIO_RE = re.compile(r"중량\s*%|중량부|wt%|배합|함유")
_CITE_RE = re.compile(r"제\s*(\d+)\s*항|청구항\s*(\d+)")


def _claim_structure(claims: List[str]) -> Optional[Dict[str, Any]]:
    numbered = [(i, c) for i, c in enumerate(claims, start=1) if c.strip() and not is_deleted_claim(c)]
    independents = [(i, c) for i, c in numbered if not is_dependent_claim(c)]
    if not independents:
        return None
    no, main = independents[0]
    elements, subject = split_claim_elements(main)
    deps = []
    for i, c in numbered:
        if i == no or not is_dependent_claim(c):
            continue
        cited = _CITE_RE.search(c)
        of = int(cited.group(1) or cited.group(2)) if cited else None
        if of is not None and of != no and of not in [d["no"] for d in deps]:
            continue  # 독립항이나 이미 나온 종속항을 인용하는 것만 가지로 잇는다
        deps.append({"no": i, "of": of if of != no else None, "text": re.sub(r"\s+", " ", c)[:80]})
    return {
        "no": no,
        "preamble": subject,
        "elements": elements,
        "element_count_ok": 3 <= len(elements) <= 5,
        "deps": deps,
        "deps_count_ok": 2 <= len(deps) <= 5,
    }


def recommend_video_signature(title: str, claims: List[str], abstract: str = "") -> Dict[str, Any]:
    """CONTENT_SPEC.md '유형 고르기' 표에 따라 시그니처 유형을 추천하고, claim 유형에 쓸 청구항 구조를 함께 돌려준다."""
    active = [c for c in claims if c.strip() and not is_deleted_claim(c)]
    main = next((c for c in active if not is_dependent_claim(c)), active[0] if active else "")
    text = f"{title}\n{main}\n{abstract}"
    kind = detect_technology_kind(title, main)

    if _SEQUENCE_RE.search(text):
        sig, why = "sequence", "프라이머·마커·서열·진단 관련 용어가 있습니다."
    elif _LINEAGE_TITLE_RE.search(title) or (_STRAIN_RE.search(title) and _STRAIN_SELECT_RE.search(text) and kind != "method"):
        sig, why = "lineage", "품종·육종 또는 분리·선발된 균주 자체가 핵심입니다."
    elif kind == "method":
        sig, why = "journey", "제조·가공·추출·발효 등 공정(방법) 발명입니다."
    elif kind == "composition":
        if _RATIO_RE.search(text):
            sig, why = "formula", "조성물의 배합 비율·함량이 청구되어 있습니다."
        else:
            sig, why = "claim", "조성물이지만 배합 비율이 보이지 않아 범용(claim) 유형을 권합니다."
    elif kind == "apparatus":
        sig, why = "loop", "장치·시스템 발명입니다."
    elif kind == "mixed":
        if any(w in title for w in APPARATUS_WORDS):
            sig, why = "loop", "장치와 방법이 함께 청구되었고 장치 구성이 중심입니다."
        else:
            sig, why = "journey", "물건과 제조방법이 함께 청구되었고 공정이 중심입니다."
    else:
        sig, why = "claim", "다른 유형이 맞지 않아 범용(claim) 유형을 권합니다."

    return {
        "recommended_type": sig,
        "type_description": SIGNATURE_TYPES[sig],
        "reason": why,
        "claim_structure": _claim_structure(claims),
        "factuality_rules": FACTUALITY_RULES,
        "spec": "patent-video-skill/references/CONTENT_SPEC.md",
    }
