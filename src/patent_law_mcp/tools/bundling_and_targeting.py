"""특허 패키징(Bundling) 및 수요기업 역매칭(Targeting) 실무 도구

농식품 및 공공 연구기관 특허의 기술이전 성공률을 극대화하기 위해:
1. 원천-제조공정-응용 제품을 하나로 묶는 '특허 번들링(Bundling)' 제안서 구성
2. 기술 특성 및 IPC/용도 기반 '수요기업 역매칭(Targeting)' 및 타겟 바이어 프로파일링
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# IPC 기반 한국표준산업분류(KSIC) 및 유관 산업군 매핑 테이블
IPC_TO_KSIC_MAP = {
    "A01": {
        "sector": "농림어업 및 농업용 기계·설비 제조업",
        "ksic": ["A011 (작물 재배업)", "C2921 (농업 및 임업용 기계 제조업)", "C10 (식료품 제조업)"],
        "buyer_traits": "스마트팜 설비 시공사, 농자재 전문 유통사, 농업회사법인, 지자체 농업기술센터 보급 사업 참여기업",
    },
    "A23": {
        "sector": "농축수산물 가공식품 및 건강기능식품 제조업",
        "ksic": ["C1079 (기타 식료품 제조업)", "C10797 (건강기능식품 제조업)", "C1080 (동물용 사료 제조업)"],
        "buyer_traits": "식품 OEM/ODM 제조사, 건강기능식품 GMP 인증 공장 보유 기업, HMR 밀키트 개발사",
    },
    "C12": {
        "sector": "미생물, 발효, 바이오 의약 및 효소 산업",
        "ksic": ["C2110 (기초 의약물질 및 생물학적 제제 제조업)", "C2042 (화장품 및 기능성 원료 제조업)"],
        "buyer_traits": "천연물 바이오 벤처, 기능성 화장품 원료 제조사, 미생물 농약/비료 생산업체",
    },
    "B01": {
        "sector": "물리화학적 분리, 여과, 농축 및 반응기 장치 산업",
        "ksic": ["C2919 (일반 목적용 기계 제조업)", "C2929 (기타 특수 목적용 기계 제조업)"],
        "buyer_traits": "플랜트 엔지니어링 설비사, 고압 추출기/원심분리기/건조기 전문 제작사",
    },
}


def bundle_patents_for_transfer(
    package_title: str,
    patents: List[Dict[str, str]],
    target_industry: str = "농식품 가공 및 스마트팜",
    discount_policy: str = "20% 패키지 일괄 감면",
) -> Dict[str, Any]:
    """여러 건의 특허(원천특허, 제조공정특허, 응용장치특허 등)를 하나의 강력한 기술이전 패키지로 묶어(Bundling) 포트폴리오를 구성합니다.

    실무 효과:
    - 단일 특허 도입 시의 회피설계 취약점을 차단
    - 패키지 일괄 기술이전 시 기술료 할인 혜택으로 도입 기업의 진입 장벽 완화
    """
    classified_bundle = []
    for idx, p in enumerate(patents, start=1):
        title = p.get("title", f"특허 기술 {idx}")
        p_id = p.get("patent_id", f"10-202X-00000{idx}")
        role = p.get("role", "")

        # 역할 자동 추정
        if not role:
            if any(k in title for k in ["장치", "시스템", "모듈", "센서"]):
                role = "장치 및 하드웨어 인프라 특허 (Apparatus)"
            elif any(k in title for k in ["방법", "공정", "제조법", "추출"]):
                role = "운전 및 제조공정 노하우 특허 (Process)"
            else:
                role = "원천 물질 및 기능성 용도 특허 (Core/Composition)"

        classified_bundle.append({
            "order": idx,
            "patent_id": p_id,
            "title": title,
            "portfolio_role": role,
            "applicant": p.get("applicant", "농촌진흥청/한국농업기술진흥원"),
            "status": p.get("status", "등록"),
        })

    portfolio_synergy = [
        "원천물질 및 추출공정, 제어장치가 상호 보완되어 제3자의 회피설계(Design-around)를 원천 차단",
        "수요기업이 양산화 착수 시 별도 추가 라이선스 없이 완제품 생산 라인 풀세트 확보 가능",
        f"패키지 일괄 계약 적용 시 기술료 감면 정책({discount_policy})을 통해 초기 투자비용 절감 유도",
    ]

    return {
        "package_title": package_title,
        "target_industry": target_industry,
        "bundled_patent_count": len(patents),
        "bundled_patents": classified_bundle,
        "portfolio_synergy_analysis": portfolio_synergy,
        "recommended_contract_structure": {
            "license_type": "패키지 일괄 통상실시 또는 전용실시",
            "bundling_discount": discount_policy,
            "due_diligence_clause": "패키지 내 주력 특허(1번) 사업화 개시 시 패키지 전체의 불실시 해지특약 요건 충족 인정",
        },
    }


def find_target_licensees_by_patent(
    technology_title: str,
    ipc_code: Optional[str] = "A23L",
    target_product: Optional[str] = None,
    preferred_company_size: str = "all",  # "sme", "startup", "middle", "all"
) -> Dict[str, Any]:
    """특허의 기술 명칭, IPC 분류, 적용 목표 제품을 바탕으로 기술도입 유력 수요기업군(Targeting)을 도출합니다.

    실무 워크플로우:
    - IPC 및 기술 키워드 기반 표준산업분류(KSIC) 매칭
    - 기업 규모별 도입 니즈(스타트업: 소액/무상실시, 중소기업: 양산/공정개선, 대기업: 신사업/독점실시) 프로파일링
    - 추천 매칭 채널 및 타겟 제안 포인트 제시
    """
    prefix = (ipc_code or "A23")[:3].upper()
    sector_info = IPC_TO_KSIC_MAP.get(prefix, {
        "sector": "일반 농산업 및 바이오 가공업",
        "ksic": ["C10 (식료품 제조업)", "C29 (기계 및 장비 제조업)"],
        "buyer_traits": "관련 제품 제조 및 OEM 전문 공장 운영 기업",
    })

    target_prod = target_product or f"{technology_title} 적용 신제품"

    buyer_personas = [
        {
            "segment": "중소·중견 제조기업 (양산 라인 구축형)",
            "priority": "최우선 추천 (1순위)",
            "fit_reason": f"기존 제조 설비 및 유통망을 보유하고 있어, {target_prod} 개발 시 빠른 매출 실현 가능",
            "licensing_strategy": "유상 통상실시 또는 3년 전용실시 (경상기술료율 1.5~2.2% 제안)",
            "pitch_key": "자체 R&D 대비 개발 기간 18개월 단축 및 국가연구기관 검증 기술을 통한 시장 신뢰도 확보",
        },
        {
            "segment": "농식품·애그테크 벤처/스타트업",
            "priority": "추천 (2순위)",
            "fit_reason": "신기술 기반 투자 유치(VC/팁스) 및 정부 R&D 사업화 과제 매칭 수요 높음",
            "licensing_strategy": "미활용 국유특허 3년 무상실시(고시 제3조) 또는 분할납부 조건",
            "pitch_key": "초기 기술료 부담 없는 무상실시 연계 및 벤처인증·공공조달 혁신시제품 가점 확보",
        },
        {
            "segment": "플랫폼·유통사 PB 및 OEM 제조 파트너",
            "priority": "전략적 추천 (3순위)",
            "fit_reason": "소비자 트렌드에 맞춘 차별화 원료/공정 확보 필요",
            "licensing_strategy": "전용실시 협약 및 공동 R&D 후속 과제 기획",
            "pitch_key": "특허 권리범위 보호를 통한 독점적 시장 진입 및 안전성 검증 완료",
        },
    ]

    sourcing_channels = [
        "한국농업기술진흥원 기술이전계약관리 플랫폼(NATI) 수요기업 풀",
        "중소벤처기업진흥공단 및 농식품모태펀드 피투자기업 디렉토리",
        "식품의약품안전처 기능성 원료 및 식품첨가물 제조 허가 기업 목록",
        "조달청 혁신장터 및 나라장터 농업용 기계·설비 입찰 참여기업 풀",
    ]

    return {
        "technology_title": technology_title,
        "classified_sector": sector_info["sector"],
        "matched_ksic_codes": sector_info["ksic"],
        "target_product": target_prod,
        "target_buyer_personas": buyer_personas,
        "recommended_sourcing_channels": sourcing_channels,
        "action_guide": "상기 타겟 기업군 풀을 대상으로 60초 엘리베이터 피치 및 특허 요약서를 첨부한 1-Pager 기술제안서(SMK) 발송 권장",
    }
