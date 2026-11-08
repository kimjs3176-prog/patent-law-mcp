"""특허 패키징(Bundling) 및 수요기업 탐색(Targeting) 실무 도구

1. 여러 특허를 하나의 기술이전 패키지로 묶을 때의 구성·역할 정리
2. IPC 기반 표준산업분류(KSIC) 참고 매핑과 수요기업군 탐색 방향 제시

근거 없는 수치(개발기간 단축, 감면율 등)는 만들지 않으며, 사용자가 준 값만 반영합니다.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from patent_law_mcp.tools.claim_utils import detect_technology_kind

# IPC 서브클래스 앞 3자리 → 한국표준산업분류(KSIC) 참고 매핑 (내장 범위: A01·A23·C12·B01)
IPC_TO_KSIC_MAP = {
    "A01": {
        "sector": "농림어업 및 농업용 기계·설비 제조업",
        "ksic": ["A011 (작물 재배업)", "C2921 (농업 및 임업용 기계 제조업)", "C10 (식료품 제조업)"],
        "buyer_traits": "스마트팜 설비 시공사, 농자재 유통사, 농업회사법인, 농업기술센터 보급사업 참여기업",
    },
    "A23": {
        "sector": "농축수산물 가공식품 및 건강기능식품 제조업",
        "ksic": ["C1079 (기타 식료품 제조업)", "C10797 (건강기능식품 제조업)", "C1080 (동물용 사료 제조업)"],
        "buyer_traits": "식품 OEM/ODM 제조사, 건강기능식품 GMP 공장 보유 기업, HMR·밀키트 개발사",
    },
    "C12": {
        "sector": "미생물·발효·바이오 소재 산업",
        "ksic": ["C2110 (기초 의약물질 및 생물학적 제제 제조업)", "C2042 (화장품 제조업)"],
        "buyer_traits": "천연물 바이오 벤처, 기능성 화장품 원료사, 미생물 농약·비료 생산업체",
    },
    "B01": {
        "sector": "분리·여과·농축 및 반응기 장치 산업",
        "ksic": ["C2919 (기타 일반 목적용 기계 제조업)", "C2929 (기타 특수 목적용 기계 제조업)"],
        "buyer_traits": "플랜트 엔지니어링사, 추출기·원심분리기·건조기 제작사",
    },
}

_ROLE_LABELS = {
    "method": "공정 특허 (Process)",
    "apparatus": "장치 특허 (Apparatus)",
    "composition": "소재·조성물 특허 (Composition)",
    "mixed": "물건·방법 복합 특허",
    "product": "물건 특허 (Product)",
}


class BundlePatent(BaseModel):
    patent_id: str = Field(..., min_length=1, description="출원·등록번호")
    title: str = Field(..., min_length=1, description="발명의 명칭")
    role: Optional[str] = Field(None, description="패키지 내 역할 (비우면 명칭으로 자동 분류)")
    applicant: Optional[str] = Field(None, description="출원인/특허권자")
    status: Optional[str] = Field(None, description="권리 상태 (등록·공개 등)")


def bundle_patents_for_transfer(
    package_title: str,
    patents: List[BundlePatent],
    target_industry: Optional[str] = None,
    discount_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """여러 특허(공정·장치·소재 등)를 하나의 기술이전 패키지로 묶고 구성·역할을 정리합니다.

    Args:
        package_title: 패키지 이름
        patents: 묶을 특허 목록 (2건 이상)
        target_industry: 목표 산업 (선택)
        discount_rate: 패키지 일괄 감면율 0~1 (선택, 기관 기준이 있을 때만)
    """
    items = [p if isinstance(p, BundlePatent) else BundlePatent.model_validate(p) for p in patents]
    if len(items) < 2:
        raise ValueError("패키지는 특허 2건 이상으로 구성해야 합니다.")
    ids = [p.patent_id.strip() for p in items]
    if len(set(ids)) != len(ids):
        raise ValueError("같은 특허번호가 중복되어 있습니다.")
    if discount_rate is not None and not 0 <= discount_rate < 1:
        raise ValueError("discount_rate는 0 이상 1 미만이어야 합니다 (예: 0.2 = 20%).")

    bundle, kinds = [], set()
    for idx, p in enumerate(items, start=1):
        kind = detect_technology_kind(p.title)
        kinds.add(kind)
        bundle.append({
            "order": idx,
            "patent_id": p.patent_id,
            "title": p.title,
            "portfolio_role": p.role or _ROLE_LABELS[kind],
            "applicant": p.applicant or "미기재",
            "status": p.status or "미확인",
        })

    if len(kinds) >= 2:
        synergy = (
            "서로 다른 유형(공정·장치·소재 등)의 특허가 함께 묶여 있어, 한 건만 실시허락할 때보다 "
            "회피설계 여지가 줄어들 수 있습니다. 실제 효과는 각 청구항을 대비해 확인하십시오."
        )
    else:
        synergy = "같은 유형의 특허로만 구성되어 있어 패키지 보완 효과가 제한적일 수 있습니다. 청구항 범위가 겹치는지 확인하십시오."

    return {
        "package_title": package_title,
        "target_industry": target_industry or "미지정",
        "bundled_patent_count": len(bundle),
        "bundled_patents": bundle,
        "portfolio_synergy_analysis": synergy,
        "recommended_contract_structure": {
            "license_type": "패키지 일괄 통상실시 (전용실시는 경쟁입찰 등 별도 요건 검토)",
            "bundling_discount": (
                f"{discount_rate:.0%} 일괄 감면 (기관 내부 기준 — 국유특허는 감면 근거 조항 확인 필요)"
                if discount_rate is not None
                else "감면율 미지정 (적용 시 근거 기준을 확인하십시오)"
            ),
            "due_diligence_clause_draft": "패키지 내 주력 특허의 사업화 개시를 패키지 전체 불실시 해지특약 판단에 반영할지 계약서에 명시",
        },
    }


CompanySize = Literal["all", "sme", "startup", "middle"]

_PERSONAS = [
    {
        "sizes": {"sme", "middle"},
        "segment": "중소·중견 제조기업 (양산 라인 보유)",
        "fit_reason": "기존 제조 설비와 유통망을 활용해 {product}에 빠르게 적용할 수 있는 기업군",
        "licensing_strategy": "유상 통상실시 우선 검토. 전용실시는 경쟁입찰 원칙 등 요건 검토 후 결정",
        "pitch_key": "국가연구기관 연구성과 기반 기술 — 실증 수준은 TRL 근거 자료로 제시",
    },
    {
        "sizes": {"startup"},
        "segment": "농식품·애그테크 벤처/스타트업",
        "fit_reason": "신기술 기반 투자 유치·정부 사업화 과제 연계 수요가 있는 기업군",
        "licensing_strategy": "미활용 국유특허 무상실시 요건 해당 여부 확인 (evaluate_unutilized_free_license)",
        "pitch_key": "초기 기술료 부담 완화 방안(무상실시·분할납부 등) 안내",
    },
    {
        "sizes": {"sme", "middle"},
        "segment": "유통사 PB 및 OEM 제조 파트너",
        "fit_reason": "차별화된 원료·공정 확보 수요가 있는 기업군",
        "licensing_strategy": "통상실시 + 공동 후속 연구 협의",
        "pitch_key": "청구항 권리범위 내 실시로 법적 안정성 확보",
    },
]


def find_target_licensees_by_patent(
    technology_title: str,
    ipc_code: Optional[str] = None,
    target_product: Optional[str] = None,
    preferred_company_size: CompanySize = "all",
) -> Dict[str, Any]:
    """특허 명칭·IPC·적용 제품으로 수요기업군 탐색 방향(KSIC 참고 매핑, 기업군, 발굴 채널)을 정리합니다.

    Args:
        technology_title: 기술(발명) 명칭
        ipc_code: IPC 분류 (예: "A23L 7/10"). 비우면 산업 매핑을 생략
        target_product: 적용 목표 제품 (선택)
        preferred_company_size: 대상 기업 규모 ("all", "sme", "startup", "middle")
    """
    prefix = ipc_code.strip()[:3].upper() if ipc_code and ipc_code.strip() else ""
    sector_info = IPC_TO_KSIC_MAP.get(prefix)
    product = target_product or f"{technology_title} 적용 제품"

    personas = [
        {k: (v.format(product=product) if isinstance(v, str) else v) for k, v in p.items() if k != "sizes"}
        for p in _PERSONAS
        if preferred_company_size == "all" or preferred_company_size in p["sizes"]
    ]

    return {
        "technology_title": technology_title,
        "ipc_code": ipc_code or "미기재",
        "classified_sector": sector_info["sector"] if sector_info else "내장 매핑에 없는 분류 (KSIC 직접 확인 필요)",
        "matched_ksic_codes": sector_info["ksic"] if sector_info else [],
        "buyer_traits": sector_info["buyer_traits"] if sector_info else None,
        "mapping_note": "IPC→KSIC는 A01·A23·C12·B01만 수록한 참고용 매핑입니다.",
        "target_product": product,
        "preferred_company_size": preferred_company_size,
        "target_buyer_personas": personas,
        "recommended_sourcing_channels": [
            "한국농업기술진흥원 기술이전계약관리 플랫폼(NATI) 수요기업 풀",
            "중소벤처기업진흥공단 및 농식품모태펀드 피투자기업 목록",
            "식품의약품안전처 기능성 원료·식품첨가물 제조 허가 기업 목록",
            "조달청 혁신장터·나라장터 농업용 기계·설비 입찰 참여기업",
        ],
        "action_guide": "기업군별로 특허 요약서와 청구항 대비표를 첨부해 기술 제안서를 발송하십시오.",
    }
