"""국가직무발명 및 국유특허 처분·보상 실무 도구

주요 실무 기능:
- process_invention_disclosure: 직무발명 신고 및 직무범위성 심의위원회 상정 체크리스트
- calculate_disposal_compensation: 국유특허 기술료 수입금에 따른 발명자 처분보상금 산정 및 지급 명세표 작성
- evaluate_free_license_qualification: 국유특허 무상실시 대상자(농업인, 청년창업농, 중소기업) 자격 요건 심의 실무
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def process_invention_disclosure(
    inventor_title: str,
    institution_type: str = "national_gov",  # "national_gov"(국가/국공립), "public_agency"(준정부/출연연), "university"(대학산단)
    project_budget_source: str = "national_rnd",  # "national_rnd"(국가R&D), "institutional"(기관고유사업)
    inventor_main_duty: str = "연구개발 및 기술보급",
) -> Dict[str, Any]:
    """직무발명 신고서 접수 시 직무범위성 판정 및 심의위원회 상정 안건을 작성합니다.

    발명진흥법 제10조 및 제12조, 공무원 직무발명 규정 제4조 기반 실무 처리 절차.
    """
    is_national = institution_type == "national_gov"

    checklist = [
        {"item": "사용자등의 업무 범위 부합 여부", "verified": True, "detail": "기관 설치법 및 고유 직무 범위 내 발명"},
        {"item": "발명자의 직무 관련성", "verified": True, "detail": f"발명자의 담당 업무({inventor_main_duty})와 직접 연관"},
        {"item": "국가R&D 연구노트 구비 여부", "verified": True, "detail": "착상 및 실험 데이터 연구노트 시점 인증 확인"},
    ]

    return {
        "invention_type": "국가직무발명 (국유화 대상)" if is_national else "기관직무발명 (기관 소유 대상)",
        "applicant_name": "대한민국 (소관: 특허청 또는 농촌진흥청 등)" if is_national else "기관 명의",
        "committee_docket": {
            "title": f"직무발명 승계 여부 심의의 건 ({inventor_title})",
            "statutory_basis": "발명진흥법 제10조 및 공무원 직무발명 규정 제4조",
            "recommendation": "국가(기관) 승계 결정 및 국내외 특허출원 승인",
            "checklist": checklist,
        },
        "next_administrative_steps": [
            "직무발명 심의위원회 의결 후 1개월 이내에 발명자에게 승계 결정 서면 통지",
            "특허출원서 작성 및 등록보상금(건당 100만 원) 지급 품의 진행",
            "비밀유지 의무 고지 (출원 전 학회 발표 또는 논문 공개 금지)",
        ],
    }


def calculate_disposal_compensation(
    contract_income_krw: int,
    inventor_shares: List[Dict[str, Any]],
    direct_expenses_krw: int = 0,
) -> Dict[str, Any]:
    """국유특허 또는 공공특허 처분 수입금에 따른 발명자 처분보상금을 산출하고 지급 명세표를 작성합니다.

    발명진흥법 제18조 제3항 및 공무원 직무발명 규정 제18조 (순수입금의 50% 지급 원칙).

    Args:
        contract_income_krw: 계약 기술료 입금액 (원 단위)
        inventor_shares: 발명자별 지분 목록 (예: [{"name": "홍길동", "share_rate": 0.6}, {"name": "김연구", "share_rate": 0.4}])
        direct_expenses_krw: 직접 발생 경비 (송금 수수료, 공증료 등 공제액)
    """
    net_income = max(0, contract_income_krw - direct_expenses_krw)
    total_compensation_pool = int(net_income * 0.50)  # 50% 지급

    payout_table = []
    for inv in inventor_shares:
        name = inv.get("name", "발명자")
        rate = float(inv.get("share_rate", 1.0))
        payout = int(total_compensation_pool * rate)
        tax_estimate = int(payout * 0.22)  # 기타소득세 22% 원천징수 추정
        net_payout = payout - tax_estimate

        payout_table.append({
            "inventor_name": name,
            "share_rate": f"{rate * 100:.1f}%",
            "gross_compensation": f"{payout:,}원",
            "estimated_withholding_tax": f"{tax_estimate:,}원",
            "net_payout": f"{net_payout:,}원",
        })

    return {
        "gross_contract_income": f"{contract_income_krw:,}원",
        "deducted_direct_expenses": f"{direct_expenses_krw:,}원",
        "net_disposal_income": f"{net_income:,}원",
        "total_compensation_amount": f"{total_compensation_pool:,}원 (순수입의 50%)",
        "payment_table": payout_table,
        "statutory_reference": "공무원 직무발명 규정 제18조 제1항 및 제19조",
        "administrative_checklist": [
            "국고 세입 조치 영수증 및 입금 증빙 첨부",
            "발명자 전원의 지분율 합의서 또는 신고서 원본 대조",
            "원천징수 영수증 발급 및 발명자 개인 계좌 실명 이체",
        ],
    }


def evaluate_free_license_qualification(
    applicant_category: str,  # "farmer"(농업인), "young_farmer"(청년창업농), "small_biz"(소상공인), "startup"(창업 3년이내), "general_sme"(일반 중소기업)
    annual_sales_krw: int,
    intended_use_purpose: str = "농작물 생산 및 현장 적용",
) -> Dict[str, Any]:
    """국유특허 무상실시(기술료 전액 면제) 신청 기업/농가의 적격성을 심의합니다.

    공무원 직무발명의 처분·관리 및 보상 등에 관한 규정 제11조의2(무상실시) 기반 실무 기준.
    """
    is_eligible = applicant_category in ["farmer", "young_farmer", "small_biz", "startup"]

    requirements = [
        {"criterion": "대상자 적격성", "pass": is_eligible, "note": "농업인, 청년농업인, 소상공인, 초기창업기업에 부합"},
        {"criterion": "공익적 활용 부합성", "pass": True, "note": f"활용 목적({intended_use_purpose})이 현장 농가 소득 증대와 직결"},
        {"criterion": "불법 전매 및 재실시 방지 서약", "pass": True, "note": "재실시권 금지 서약서 징구 필수"},
    ]

    return {
        "applicant_category": applicant_category,
        "is_free_license_eligible": is_eligible,
        "exemption_rate": "기술료 100% 전액 면제" if is_eligible else "면제 불가 (유상실시 대상, 중소기업 우대요율 적용)",
        "evaluation_checklist": requirements,
        "required_documents": [
            "국유특허 무상실시 계약 신청서",
            "농업경영체등록증 또는 소상공인확인서 (또는 사업자등록증)",
            "기술 활용 사업계획서 (간이 양식 1부)",
            "재실시 및 양도 금지 확약서",
        ],
        "procedure_lead_time": "신청 접수 후 기술거래 기관 심의 거쳐 통상 7~10일 이내 계약 체결 완료",
    }
