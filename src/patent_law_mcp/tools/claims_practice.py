"""특허 청구항 권리범위 분석 및 FTO/침해·회피설계 실무 도구

주요 실무 기능:
- analyze_claim_elements_chart: 독립항의 구성요소 완비의 법칙(All Elements Rule) 기반 분해 및 3단계 침해 위험 태깅
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

    All Elements Rule(구성요소 완비의 법칙)에 따라 목표 제품의 침해 위험을 3단계로 정밀 태깅합니다.

    Args:
        claim_text: 독립항(청구항 1항) 원문 텍스트
        target_product_spec: 비교 대상 제품 또는 실시 기술의 사양 설명
    """
    clean_claim = claim_text.strip()

    # 세미콜론(;), 불릿, 개행 등을 기준으로 구성요소 분해
    raw_parts = [p.strip() for p in re.split(r"[;\n]+", clean_claim) if len(p.strip()) > 5]

    elements = []
    prod_spec_lower = (target_product_spec or "").lower()

    for idx, part in enumerate(raw_parts, start=1):
        element_id = f"구성 {chr(64 + idx)}"  # 구성 A, B, C...

        # 3단계 침해 위험 태깅 로직
        if not target_product_spec:
            match_status = "검토 대기 (제품 사양 미입력)"
            risk_tag = "대기"
        else:
            # 주요 단어 추출 후 제품 사양과 비교
            keywords = [w for w in re.findall(r"[가-힣a-zA-Z0-9]{2,}", part) if len(w) >= 2][:4]
            matches = [k for k in keywords if k.lower() in prod_spec_lower]

            if len(matches) >= 2:
                match_status = f"문언 일치 위험 높음 (주요 키워드: {', '.join(matches)})"
                risk_tag = "문언 침해 주의"
            elif len(matches) == 1:
                match_status = f"구성 일부 상이/치환 의심 (유사 키워드: {matches[0]} - 균등론 검토 필요)"
                risk_tag = "균등 침해 검토"
            else:
                match_status = "구성 결여 유력 (대상 제품에서 해당 특징 미발견)"
                risk_tag = "비침해 유력 (회피 성공)"

        elements.append({
            "element_id": element_id,
            "claim_statement": part,
            "target_product_match": match_status,
            "risk_assessment": risk_tag,
        })

    has_non_infringement = any(e["risk_assessment"] == "비침해 유력 (회피 성공)" for e in elements)

    overall_fto_summary = (
        "결과: 최소 1개 이상의 필수 구성요소가 결여되어 All Elements Rule상 '문언 침해'는 성립하지 않을 가능성이 높습니다. "
        "다만 상이한 구성이 통상의 기술자에게 자명한 치환인지 '균등론' 성립 여부를 최종 점검하십시오."
        if has_non_infringement and target_product_spec
        else "결과: 모든 구성요소가 대상 제품에 대응되거나 유사하게 실시될 경우 침해 성립 가능성이 매우 높으므로 회피설계가 필수적입니다."
    )

    return {
        "claim_decomposition": elements,
        "overall_fto_summary": overall_fto_summary,
        "all_elements_rule_principle": (
            "구성요소 완비의 법칙: 청구항에 기재된 A, B, C, D 중 어느 하나라도 대상 제품에 포함되지 않으면 문언 침해가 성립하지 않습니다."
        ),
    }


def evaluate_workaround_points(
    claim_elements: List[Dict[str, str]],
) -> Dict[str, Any]:
    """청구항 구성요소 분해 결과를 바탕으로 특허 침해를 회피하기 위한 실무 전략(생략·치환·역설계)을 제시합니다."""
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
