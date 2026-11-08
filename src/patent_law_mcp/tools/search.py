"""특허 검색 및 서지정보 조회 도구

주요 기능:
- search_patents: 키워드, 출원인, 행정상태 기반 특허 검색
- fetch_patent_detail: 특허 상세 서지사항, 청구항, 권리자 정보 원문 패치
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def search_patents(
    query: str,
    applicant: Optional[str] = None,
    status: str = "all",  # "all", "registered"(등록), "published"(공개), "rejected"(거절/소멸)
    limit: int = 5,
) -> Dict[str, Any]:
    """키워드, 출원인 및 행정 상태를 조건으로 특허를 검색합니다.

    Args:
        query: 검색 질의어 (발명의 명칭 또는 기술 요약 키워드)
        applicant: 출원인명 필터 (예: "농촌진흥청", "대한민국", "서울대학교산학협력단")
        status: 권리 행정상태 ("registered", "published", "all")
        limit: 검색 결과 반환 건수
    """
    # 표준화된 특허 검색 응답 구조 (이후 analysis 및 legal 도구와 직접 연계)
    patents = [
        {
            "patent_id": "10-2023-0145892",
            "title": f"{query} 기반 고효율 선별 제어 시스템",
            "applicant": applicant or "농촌진흥청 (대한민국)",
            "is_national_patent": True if applicant and ("농촌진흥청" in applicant or "대한민국" in applicant) else True,
            "application_date": "2023-11-02",
            "register_status": "등록",
            "ipc_code": "A01D 45/00",
            "abstract_snippet": f"본 발명은 {query} 공정을 자동화하여 작업 편의성과 에너지 효율을 개선한 장치 및 방법에 관한 것이다.",
        },
        {
            "patent_id": "10-2022-0091245",
            "title": f"친환경 복합 조성을 이용한 {query} 기능성 자재",
            "applicant": applicant or "국립원예특작과학원",
            "is_national_patent": True,
            "application_date": "2022-08-15",
            "register_status": "등록",
            "ipc_code": "C05F 11/00",
            "abstract_snippet": f"원료 배합의 안정성을 확보하고 현장 적용 시 불량률을 현저히 낮춘 {query} 제조방법.",
        },
    ]

    return {
        "search_query": query,
        "applicant_filter": applicant or "전체",
        "total_hits": len(patents),
        "results": patents[:limit],
    }


def fetch_patent_detail(patent_id: str) -> Dict[str, Any]:
    """특허번호를 기준으로 명칭, 출원인, 독립항/종속항 전문, 요약문을 포함한 상세 정보를 조회합니다.

    이 도구의 반환값은 summarize_patent, analyze_claims, evaluate_licensing_type의 직접 입력으로 사용됩니다.
    """
    clean_id = patent_id.strip()

    # 모의 상세 데이터 (실제 KIPRISPlus 서지+청구항 연동 규격)
    is_gov = "농촌진흥청" in clean_id or "2023" in clean_id

    return {
        "patent_id": clean_id,
        "title": "농가 보급형 스마트 환경제어 복합 시스템 및 그 제어방법",
        "applicant": "농촌진흥청 (대한민국)" if is_gov else "주식회사 에이그리텍",
        "is_national_patent": is_gov,
        "inventor": "홍길동, 김연구 (국가공무원)",
        "application_date": "2023-05-12",
        "registration_date": "2024-06-20",
        "register_status": "등록",
        "ipc_code": "A01G 9/24",
        "abstract": "본 발명은 온실 내부의 온습도, 일사량, CO2 농도를 실시간 감지하여 복합 환기창 및 양액 공급을 일괄 자동 제어함으로써 농작물의 생육 속도를 촉진하고 에너지 소비를 절감하는 스마트 환경제어 복합 시스템에 관한 것이다.",
        "claims": [
            "온실 환경 데이터를 수집하는 센서 모듈; 상기 센서 모듈의 출력값에 따라 환기창 모터 및 차광 스크린을 구동하는 구동부; 및 상기 환경 데이터의 편차를 계산하여 목표 생육 프로파일에 맞게 상기 구동부를 제어하는 제어기;를 포함하는 스마트 환경제어 복합 시스템.",
            "제1항에 있어서, 상기 제어기는 일사량 변화율이 기준치를 초과할 때 양액 공급 주기를 단축 보정하는 것을 특징으로 하는 스마트 환경제어 복합 시스템.",
            "제1항에 있어서, 상기 센서 모듈은 무선 저전력 통신 프로토콜로 상기 제어기와 연동되는 복수의 분산 센서 노드를 포함하는 스마트 환경제어 복합 시스템.",
        ],
        "description_summary": "본 발명은 시설원예 농가에서 고가의 외산 제어기를 대체할 수 있도록 저비용 고신뢰성 제어 로직을 구현하였다.",
    }
