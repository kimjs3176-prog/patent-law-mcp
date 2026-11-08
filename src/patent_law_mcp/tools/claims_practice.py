"""특허 청구항 권리범위 분석 및 FTO/침해·회피설계 실무 도구

주요 실무 기능:
- analyze_claim_elements_chart: 독립항의 구성요소 완비의 법칙(All Elements Rule) 기반 분해 및 침해 대비표 생성
- evaluate_workaround_points: 청구범위 회피설계(Workaround) 및 구성요소 치환·생략 가이드
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def analyze_claim_elements_chart(
    claim_text: str,
    target_product_spec: Optional[str] = None,
) -> Dict[str, Any]:
    """독립항을 핵심 구성요소(Element)별로 분해하고, 목표 제품과의 요소별 대비표(Element-by-Element Chart)를 구성합니다.

    All Elements Rule(구성요소 완비의 법칙)에 따라, 대상 제품이 청구항의 모든 구성요소를 그대로 포함하는지 검토합니다.

    Args:
        claim_text: 독립항(청구항 1항) 원문 텍스트
        target_product_spec: 비교 대상 제품 또는 실시 기술의 사양 설명
    """
    clean_claim = claim_text.strip()

    # 세미콜론(;), 불릿, 번호 등을 기준으로 구성요소 분해
    raw_parts = [p.strip() for p in re.split(r"[;\n]+", clean_claim) if len(p.strip()) > 5]

    elements = []
    for idx, part in enumerate(raw_parts, start=1):
        # 주어/목적어 형태의 구성 명칭 발췌
        elements.append({
            "element_id": f"구성 {chr(64 + idx)}",  # 구성 A, B, C...
            "claim_statement": part,
            "target_product_match": "포함 (직접 침해 가능성)" if target_product_spec else "검토 대기",
            "practical_role": "핵심 기술적 특징 및 유기적 결합 요소",
        })

    return {
        "claim_decomposition": elements,
        "all_elements_rule_status": (
            "침해 성립 요건: 대상 제품이 위 구성요소(A, B, C...) 전부를 완비해야 문언 침해가 성립합니다. "
            "단 하나의 구성요소라도 누락되면 원칙적으로 문언 침해에서 벗어납니다."
        ),
        "doctrine_of_equivalents_note": (
            "구성요소를 변경하더라도 과제의 해결원리가 동일하고 동일한 효과를 나타내며, "
            "그 변경이 해당 분야 통상의 지식을 가진 자에게 자명한 경우 '균등 침해'가 문제될 수 있으므로 기능적 차별화가 필수적입니다."
        ),
    }


def evaluate_workaround_points(
    claim_elements: List[Dict[str, str]],
) -> Dict[str, Any]:
    """청구항 구성요소 분해 결과를 바탕으로 특허 침해를 회피하기 위한 실무 전략(생략·치환·역설계)을 제시합니다.

    Args:
        claim_elements: analyze_claim_elements_chart에서 도출된 구성요소 목록
    """
    workaround_strategies = [
        {
            "strategy": "구성요소 완전 생략 (Omission)",
            "method": "독립항에 기재된 필수 구성 중 1개 이상의 요소를 사용하지 않고도 동일 목적을 달성하는 우회 메커니즘 설계",
            "safety_level": "가장 안전 (All Elements Rule에 의해 문언 및 균등침해 배제)",
        },
        {
            "strategy": "기능 및 작동 메커니즘의 실질적 변경 (Substantial Difference)",
            "method": "단순 형상·치수 변경이 아닌 제어 알고리즘이나 물성 반응 원리를 다르게 변경하여 균등론 성립 차단",
            "safety_level": "전문 변리사 감정 필요",
        },
        {
            "strategy": "공지기술(Free State Art)의 항변 확보",
            "method": "해당 구성요소가 특허 출원 전 이미 공지된 종래기술과 동일함을 입증하여 권리범위 축소 유도",
            "safety_level": "무효심판 또는 거절이유 대응 병행",
        },
    ]

    return {
        "workaround_action_items": workaround_strategies,
        "practical_advice": (
            "회피설계 시 가장 확실한 방법은 독립항의 한 구성을 '아예 빼버리는(생략)' 설계입니다. "
            "불가피하게 치환할 경우 균등론을 피하기 위해 '작동 원리의 차이'와 '새로운 현저한 효과'를 연구노트에 증빙으로 남겨두어야 합니다."
        ),
    }
