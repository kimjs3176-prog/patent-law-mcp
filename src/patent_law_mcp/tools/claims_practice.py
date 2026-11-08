"""기술이전 권리범위 1차 대조 도구

출원·회피설계 자문이 아니라, 기술이전 상담 전에 '도입 희망 기업 제품 설명'이
청구항 구성요소를 담고 있는지 키워드 수준에서 1차로 대조합니다. 침해 감정이 아닙니다.
"""

import math
import re
from typing import Annotated, Any, Dict, List

from pydantic import Field

from patent_law_mcp.tools.claim_utils import split_claim_elements

_STOPWORDS = {
    "상기", "포함", "포함하는", "있어서", "특징", "특징으로", "하는", "되는", "및", "또는", "각각", "복수", "복수의",
    "일측", "타측", "구비", "형성", "형성된", "배치", "배치되어", "위한", "위해", "의한", "따라", "통해", "이용",
    "이용한", "것을", "것", "단계", "부재", "수단", "적어도", "하나", "이상", "이하", "구성", "구성된",
}
_JOSA = ("으로부터", "에서의", "으로서", "으로써", "로부터", "에서", "에게", "으로", "로서", "로써", "부터", "까지",
         "와의", "과의", "하는", "되는", "하여", "되어", "하고", "되고", "을", "를", "이", "가", "은", "는", "의",
         "에", "와", "과", "로", "도", "만")
_STOPWORDS |= {
    "the", "said", "and", "or", "of", "to", "for", "with", "from", "into", "onto", "on", "in", "at", "by", "an",
    "wherein", "comprising", "comprises", "including", "configured", "which", "that", "each", "least", "one", "plurality",
}
_NEGATION = re.compile(r"없이|없는|없음|없다|없으며|미적용|미사용|미장착|제외|않|아니|\bno\b|\bnot\b|\bwithout\b|\bnone\b|\blacks?\b")
_NEGATION_BEFORE = re.compile(r"\b(?:without|no|not|lacks?|free of|absence of)\b[\w\s-]{0,12}$")


def _stem(token: str) -> str:
    if token.isascii():
        return token.lower()
    for j in _JOSA:
        if token.endswith(j) and len(token) - len(j) >= 2:
            return token[: -len(j)]
    return token


def _keywords(element: str) -> List[str]:
    out: List[str] = []
    for tok in re.findall(r"[가-힣A-Za-z0-9]{2,}", element):
        stem = _stem(tok)
        if len(stem) >= 2 and stem not in _STOPWORDS and tok.lower() not in _STOPWORDS and stem not in out:
            out.append(stem)
    return out


def _present(keyword: str, spec: str) -> str:
    """'present' | 'negated' | 'absent' — 키워드 직후 짧은 범위에 부정 표현이 있으면 negated."""
    found = False
    for m in re.finditer(re.escape(keyword.lower()), spec):
        found = True
        window = spec[m.end(): m.end() + 12]
        window = re.split(r"[.,;\n]|하며|하고|이며", window)[0]
        before = re.split(r"[.,;\n]", spec[max(0, m.start() - 25): m.start()])[-1]
        if not _NEGATION.search(window) and not _NEGATION_BEFORE.search(before):
            return "present"
    return "negated" if found else "absent"


def verify_tech_transfer_scope_match(
    claim_text: Annotated[str, Field(min_length=5)],
    target_product_spec: Annotated[str, Field(min_length=5)],
) -> Dict[str, Any]:
    """독립항 구성요소별로 기업 제품 설명에 해당 키워드가 있는지 대조합니다 (구성요소 완비 원칙 1차 점검).

    Args:
        claim_text: 대상 특허의 독립항 원문 (보통 청구항 1)
        target_product_spec: 도입 희망 기업의 제품·공정 설명
    """
    elements, subject = split_claim_elements(claim_text)
    if not elements:
        raise ValueError("청구항에서 구성요소를 찾지 못했습니다. 독립항 전문을 입력하십시오.")
    spec = target_product_spec.lower()

    results = []
    for idx, element in enumerate(elements, start=1):
        keywords = _keywords(element)
        states = {k: _present(k, spec) for k in keywords}
        present = [k for k, s in states.items() if s == "present"]
        negated = [k for k, s in states.items() if s == "negated"]
        need = max(1, math.ceil(len(keywords) / 2))

        if keywords and len(present) >= need:
            status, matched = "일치 가능성 높음", True
        elif present:
            status, matched = "부분 일치 (확인 필요)", False
        else:
            status, matched = "제품 설명에서 확인되지 않음", False
        results.append({
            "element_id": f"구성 {idx}",
            "claim_statement": element,
            "keywords": keywords,
            "matched_keywords": present,
            "negated_keywords": negated,
            "company_product_status": status,
            "is_matched": matched,
        })

    matched_count = sum(r["is_matched"] for r in results)
    partial = any(r["company_product_status"].startswith("부분") for r in results)
    if matched_count == len(results):
        verdict = (
            "모든 구성요소가 제품 설명에서 확인됩니다. 제품이 청구항 권리범위에 속할 가능성이 높으므로 "
            "실시권 계약 필요성을 검토하십시오."
        )
    elif matched_count or partial:
        verdict = (
            f"{len(results)}개 구성요소 중 {matched_count}개만 확인됩니다. 구성요소 완비 원칙상 하나라도 빠지면 "
            "문언 침해가 성립하지 않을 수 있으나, 균등 여부와 향후 제품 계획을 확인하십시오."
        )
    else:
        verdict = "제품 설명에서 청구항 구성요소가 확인되지 않습니다. 대상 특허나 도입 범위를 다시 검토하십시오."

    return {
        "claimed_subject_matter": subject or "미확인",
        "verified_elements": results,
        "matched_elements": f"{matched_count}/{len(results)}",
        "licensing_necessity_evaluation": verdict,
        "method_note": "키워드 대조이며 동의어·상위개념·균등물은 판단하지 못합니다. 부정 표현('~없이', '~미적용')은 불일치로 봅니다.",
        "disclaimer": "기술이전 상담용 1차 검토 자료이며, 침해 여부 판단은 변리사 감정을 거쳐야 합니다.",
    }
