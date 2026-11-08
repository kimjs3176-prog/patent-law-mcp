"""기술이전 권리범위 매칭 및 FTO 저촉 확인 실무 도구

출원/회피설계 자문이 아닌, 기술이전 계약 체결 전 '도입 희망 기업 제품과 특허 권리범위의 일치 여부' 확인에 특화
"""

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def verify_tech_transfer_scope_match(
    claim_text: str,
    target_product_spec: str,
) -> Dict[str, Any]:
    """기술이전 계약 체결 전, 도입 희망 기업의 실시 제품이 특허 청구항의 권리범위에 부합하는지 매칭을 검토합니다.

    All Elements Rule(구성요소 완비의 법칙)에 따라, 기업 제품이 해당 특허 기술을 실제로 실시하는지(실시권 필요 여부) 확인합니다.

    Args:
        claim_text: 기술이전 대상 특허의 청구항 1항 원문
        target_product_spec: 도입 희망 기업의 제품 또는 적용 예정 공정 설명
    """
    clean_claim = claim_text.strip()
    raw_parts = [p.strip() for p in re.split(r"[;\n]+", clean_claim) if len(p.strip()) > 5]

    elements = []
    prod_spec_lower = target_product_spec.lower()

    matched_elements_count = 0

    for idx, part in enumerate(raw_parts, start=1):
        element_id = f"특허 필수 구성 {chr(64 + idx)}"

        keywords = [w for w in re.findall(r"[가-힣a-zA-Z0-9]{2,}", part) if len(w) >= 2][:4]
        matches = [k for k in keywords if k.lower() in prod_spec_lower]

        if len(matches) >= 2:
            status = f"실시 제품에 포함됨 (일치 키워드: {', '.join(matches)})"
            matched_elements_count += 1
            is_matched = True
        elif len(matches) == 1:
            status = f"유사 구성으로 실시 중 (관련 키워드: {matches[0]})"
            is_matched = True
            matched_elements_count += 1
        else:
            status = "실시 제품에서 해당 구성 미실시"
            is_matched = False

        elements.append({
            "element_id": element_id,
            "claim_statement": part,
            "company_product_status": status,
            "is_matched": is_matched,
        })

    is_full_license_needed = matched_elements_count == len(elements)

    if is_full_license_needed:
        licensing_recommendation = (
            "✅ 기술실시계약 필수: 기업 제품이 특허의 모든 구성요소를 그대로 실시하고 있으므로, "
            "특허 침해 시비를 예방하고 합법적 독점/비독점 권리를 확보하기 위해 전용실시 또는 통상실시 계약 체결이 반드시 필요합니다."
        )
    elif matched_elements_count > 0:
        licensing_recommendation = (
            "⚠️ 부분 실시 상태: 일부 구성요소만 매칭되므로, 제품 상용화 과정에서 전체 구성을 완성할 계획인지 확인 후 "
            "사전 실시권 계약 또는 개량발명 협의를 진행하십시오."
        )
    else:
        licensing_recommendation = (
            "ℹ️ 실시 불일치: 현재 기업 제품 사양은 본 특허의 권리범위와 직접 일치하지 않습니다. "
            "다른 공공특허 매칭을 검토하거나 기술 도입 범위를 재설정하십시오."
        )

    return {
        "verified_elements": elements,
        "licensing_necessity_evaluation": licensing_recommendation,
        "disclaimer": (
            "본 분석은 기술이전 상담 및 계약 필요성 판단을 위한 실무 검토 자료이며, "
            "침해 소송에 대한 최종 법적 감정은 변리사 또는 법률 전문가의 정밀 감정을 거쳐야 합니다."
        ),
    }
