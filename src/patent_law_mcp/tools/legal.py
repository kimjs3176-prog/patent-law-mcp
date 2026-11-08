"""특허 관련 법령 및 국가직무발명 처분·기술이전 전문 법률 도구

주요 법령:
- 발명진흥법 및 공무원 직무발명의 처분·관리 및 보상 등에 관한 규정
- 기술의 이전 및 사업화 촉진에 관한 법률 (기술이전법)
- 특허법 (전용실시권 제100조, 통상실시권 제102조)
- 국가연구개발혁신법 (연구개발성과물의 소유 및 실시)
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LawLinkHelper:
    """국가법령정보센터 공식 웹 링크 생성기"""

    @staticmethod
    def get_law_url(mst: str, ef_yd: Optional[str] = None) -> str:
        url = f"https://www.law.go.kr/lsInfoP.do?lsiSeq={mst}"
        if ef_yd and len(ef_yd) == 8 and ef_yd.isdigit():
            url += f"&efYd={ef_yd}"
        return url


# 주요 특허·기술이전 법령 메타데이터 데이터베이스 (법령 일련번호 매핑)
LAW_CATALOG = {
    "특허법": {
        "mst": "258281",
        "description": "특허권의 효력, 전용실시권(제100조), 통상실시권(제102조), 법정/강제통상실시권",
    },
    "발명진흥법": {
        "mst": "258279",
        "description": "직무발명(제10조~제17조), 국가직무발명 승계 및 처분·관리(제18조), 산업재산권 진흥",
    },
    "기술이전법": {
        "mst": "249821",
        "full_name": "기술의 이전 및 사업화 촉진에 관한 법률",
        "description": "공공기술의 이전 및 사업화 촉진(제12조), 기술이전 전담조직, 기술평가 및 신탁",
    },
    "국가연구개발혁신법": {
        "mst": "248931",
        "description": "국가R&D 연구개발성과물의 소유·관리, 중소·중견기업 우선 실시 원칙, 기술료 징수 및 사용",
    },
    "공무원직무발명규정": {
        "mst": "256911",
        "full_name": "공무원 직무발명의 처분·관리 및 보상 등에 관한 규정",
        "description": "국가직무발명의 국유화 승계, 국유특허권의 처분(매각·전용실시·통상실시), 등록/처분보상금 지급 기준",
    },
}


class NationalInventionEvaluation(BaseModel):
    is_national_employee_invention: bool = Field(
        ..., description="국가직무발명 해당 여부"
    )
    applicable_laws: List[str] = Field(..., description="적용 법령 및 규정 조문")
    succession_procedure: str = Field(..., description="국유화 승계 절차 안내")
    disposal_options: List[Dict[str, str]] = Field(
        ..., description="처분 방식별 요건 (매각, 유상/무상 전용실시, 통상실시)"
    )
    compensation_summary: str = Field(..., description="처분보상금 및 등록보상금 지급 기준")
    cautions: List[str] = Field(..., description="실무상 유의사항 및 감사 포인트")


def check_national_invention_disposal(
    inventor_status: str,
    invention_duty_related: bool,
    planned_disposal: str = "non_exclusive",
    has_commercial_revenue: bool = True,
) -> Dict[str, Any]:
    """국가직무발명 여부 판정 및 국유특허권 처분(매각, 전용/통상실시, 무상실시)과 보상금 규정을 진단합니다.

    Args:
        inventor_status: 발명자 신분 (예: "공무원", "국공립연구기관 연구원", "사립대 산단 연구원", "출연연 연구원")
        invention_duty_related: 국가/기관의 직무 범위 및 담당 업무에 속하는지 여부
        planned_disposal: 예정된 처분 방식 ("non_exclusive"(통상실시), "exclusive"(전용실시), "transfer"(양도/매각), "free"(무상실시))
        has_commercial_revenue: 기술료 등 처분 수입 발생 여부
    """
    is_gov_official = "공무원" in inventor_status or "국공립" in inventor_status
    is_national = is_gov_official and invention_duty_related

    applicable_laws = [
        "발명진흥법 제10조 (직무발명) 및 제18조 (국가직무발명의 승계 및 처분·관리)",
        "공무원 직무발명의 처분·관리 및 보상 등에 관한 규정 (대통령령)",
    ]

    if not is_national:
        return {
            "is_national_employee_invention": False,
            "summary": "발명자가 국가공무원 신분이 아니거나 직무 범위 외 발명인 경우 국가직무발명(국유특허)에 해당하지 않습니다.",
            "guidance": "정부출연연구기관 또는 대학 산학협력단 직무발명인 경우 발명진흥법 제15조 및 기관 내부 직무발명 규정이 적용됩니다.",
        }

    # 처분 방식 검토
    disposal_options = []
    if planned_disposal == "exclusive":
        disposal_options.append({
            "type": "전용실시권 설정 (국유특허)",
            "rule": "공무원 직무발명 규정 제11조 및 발명진흥법 제18조",
            "requirement": "원칙적으로 국유특허는 통상실시권이 원칙입니다. 전용실시는 공개경쟁 입찰을 거쳐야 하며, 2회 이상 유찰되거나 국가 안보 및 긴급한 기술 상용화 필요성이 입증된 경우에 한해 제한적으로 허용됩니다.",
            "price_basis": "감정평가기관의 평가액 또는 예정가격 이상의 최고가 입찰",
        })
    elif planned_disposal == "free":
        disposal_options.append({
            "type": "무상통상실시 또는 기술료 감면",
            "rule": "공무원 직무발명 규정 제11조의2",
            "requirement": "농어업인, 소상공인, 중소기업의 육성이나 재난·안전 등 공익 목적에 부합하는 경우 관계부처 심의를 거쳐 무상 또는 50% 범위 내에서 감면 계약 가능",
        })
    else:
        disposal_options.append({
            "type": "통상실시권 설정 (국유특허 기본 방식)",
            "rule": "공무원 직무발명 규정 제10조 및 제11조",
            "requirement": "실시를 원하는 자 누구에게나 균등한 조건으로 계약 체결 가능. 수의계약 가능.",
            "price_basis": "기술료 산정기준(기본료 + 경상기술료)에 따라 표준 계약 체결",
        })

    # 보상금 규정
    compensation_text = (
        "1. 등록보상금: 발명자에게 건당 100만 원 (공동발명 시 지분 분할 지급)\n"
        "2. 처분보상금: 국유특허권의 유상 처분(실시료 납부 등) 수입금이 국고에 납입된 경우, "
        "처분 수입금의 100분의 50을 발명자(공무원)에게 지급 (발명진흥법 제18조 제3항 및 공무원 직무발명 규정 제18조)"
    )

    cautions = [
        "국유특허 전용실시권 설정 시 특허청장(또는 위탁관리 기관장) 승인 및 관보 공고 절차 준수 필수",
        "처분 수입금 발생 시 처분보상금 지급 대장 작성 및 발명자별 지분 확인 필수",
        "특허 연차등록료 미납으로 인한 권리 소멸 주의 (국유재산 관리 지침)",
    ]

    return {
        "is_national_employee_invention": True,
        "applicable_laws": applicable_laws,
        "succession_procedure": "직무발명 완성 즉시 기관장에게 신고 → 국가승계 결정 통지 → 특허청 국가 명의(대한민국) 출원 및 등록",
        "disposal_options": disposal_options,
        "compensation_summary": compensation_text,
        "cautions": cautions,
    }


def evaluate_licensing_type(
    technology_origin: str = "public",  # "public"(공공연구기관/대학/국유특허) or "private"
    requested_license: str = "exclusive",  # "exclusive"(전용실시) or "non_exclusive"(통상실시)
    competitive_bid_attempts: int = 0,
    required_followup_investment: bool = False,
    is_sme_target: bool = True,
) -> Dict[str, Any]:
    """공공기술의 기술이전 시 전용실시 vs 통상실시 허용 요건 및 절차적 정당성을 진단합니다.

    기술이전법(기술의 이전 및 사업화 촉진에 관한 법률) 제12조 및 공공연구기관 기술이전 가이드라인 기반.
    """
    is_public = technology_origin == "public"

    if not is_public:
        return {
            "applicable_rule": "특허법 제100조(전용실시권) 및 제102조(통상실시권)",
            "summary": "민간 특허는 사적 자치의 원칙에 따라 당사자 간 합의로 자유롭게 전용실시/통상실시 계약 가능",
            "registration": "전용실시권은 특허청 등록이 효력발생 요건(특허법 제101조), 통상실시권은 대항요건(특허법 제118조)",
        }

    # 공공기술 기술이전인 경우
    eval_result: Dict[str, Any] = {
        "base_principle": "공공기술 통상실시 원칙 (기술이전법 제12조 제2항)",
        "requested_license": requested_license,
        "eligible_for_exclusive": False,
        "justification": [],
        "required_procedures": [],
    }

    if requested_license == "exclusive":
        reasons = []
        if competitive_bid_attempts >= 2:
            reasons.append("2회 이상 통상실시권 설정 공고를 거쳤으나 신청 기업이 없는 경우 (유찰 요건 충족)")
        if required_followup_investment:
            reasons.append("기술의 상용화를 위해 막대한 후속 설비투자나 장기 시험평가·임상이 필수적인 경우")

        if reasons:
            eval_result["eligible_for_exclusive"] = True
            eval_result["justification"] = reasons
            eval_result["required_procedures"] = [
                "전용실시 추진 사유서 및 내부 심의위원회(기술이전심의회) 의결서 작성",
                "기술이전 공고(기술이전법 제12조 제1항) 최소 15일 이상 게재",
                "독점 남용 방지를 위한 의무실시 조항(실시 개시 기한, 마일스톤) 및 해지 요건 명시",
                "재실시권(Sub-license) 허용 여부 명확화 (원칙적 불허 또는 사전 서면 승인제)",
            ]
        else:
            eval_result["eligible_for_exclusive"] = False
            eval_result["warning"] = (
                "공공연구개발 성과는 특정 기업에 독점적 전용실시권을 부여하기 전 "
                "반드시 2회 이상 공고 유찰 또는 대규모 후속 투자 필요성 등 법적 예외 요건이 객관적으로 입증되어야 합니다."
            )
            eval_result["recommended_next_step"] = (
                "1차 통상실시 공고를 먼저 진행하거나, 기업의 후속 사업화 투자계획서(확약서)를 징구하여 기술이전심의회에 부의하십시오."
            )
    else:
        eval_result["eligible_for_exclusive"] = True  # 통상실시는 원칙적 가능
        eval_result["justification"] = ["공공기술의 공평한 확산 및 산업 활용 극대화 목적에 부합"]
        eval_result["required_procedures"] = [
            "표준 기술실시계약서 체결",
            "동일 분야 타 기업 추가 통상실시권 허용 가능 안내",
            "중소·중견기업 기술료 우대 감면 적용 검토 (국가연구개발혁신법)",
        ]

    return eval_result


def query_tech_transfer_law(keyword_or_topic: str) -> Dict[str, Any]:
    """특허법, 발명진흥법, 기술이전법, 국가연구개발혁신법의 주요 조문과 해설을 검색합니다.

    Args:
        keyword_or_topic: 검색 키워드 (예: "전용실시", "통상실시", "직무발명", "처분보상금", "국유특허", "기술료")
    """
    keyword = keyword_or_topic.strip()
    matched_laws = []

    for name, info in LAW_CATALOG.items():
        matched_laws.append({
            "law_name": info.get("full_name", name),
            "summary": info["description"],
            "law_go_kr_url": LawLinkHelper.get_law_url(info["mst"]),
        })

    key_articles = {
        "전용실시": "특허법 제100조 (전용실시권) - 특허권자는 그 특허권에 대하여 타인에게 전용실시권을 설정할 수 있다.",
        "통상실시": "특허법 제102조 (통상실시권) - 특허권자는 그 특허권에 대하여 타인에게 통상실시권을 허락할 수 있다.",
        "직무발명": "발명진흥법 제10조 (직무발명) - 종업원등이 그 직무에 관하여 발명한 것이 성질상 사용자등의 업무 범위에 속하는 발명.",
        "국가직무발명": "발명진흥법 제18조 (국가직무발명의 승계 및 처분·관리) - 공무원의 직무발명은 국가가 승계하며 국유로 한다.",
        "공공기술이전": "기술이전법 제12조 (공공기술의 이전 및 사업화 촉진) - 공공연구기관의 장은 공공기술을 이전하거나 사업화하려는 자에게 통상실시권을 설정하는 것을 원칙으로 한다.",
    }

    relevant_articles = [
        f"{k}: {v}" for k, v in key_articles.items() if keyword in k or k in keyword
    ]

    return {
        "query": keyword,
        "relevant_key_articles": relevant_articles or list(key_articles.values())[:3],
        "official_laws": matched_laws,
    }
