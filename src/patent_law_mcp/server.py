"""Patent Law MCP 메인 서버 (FastMCP 기반)

지식재산처 국가직무발명특허권(국유특허) 업무 중심 실무 보조 도구
(신고·승계·등록보상 → 처분 방식·실시료 예정가격 → 계약 → 처분보상 → 수탁기관 관리 → 심판·소송)

[면책 조항]
본 MCP 서버는 변리사의 출원·심사 대리 업무를 대신하지 않으며,
공공연구기관 및 국가직무발명의 기술이전 계약 실무, 처분·보상 행정 절차,
도입 기업 제품과의 권리범위 1차 대조를 보조하기 위한 도구입니다.
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from patent_law_mcp.legal_sources import check_legal_source_updates
from patent_law_mcp.policies.policy_manager import get_policy_table
from patent_law_mcp.tools.analysis import (
    evaluate_commercialization,
    ground_patent_applications,
    ground_summary_figures,
    summarize_patent,
)
from patent_law_mcp.tools.bundling_and_targeting import bundle_patents_for_transfer, find_target_licensees_by_patent
from patent_law_mcp.tools.claims_practice import verify_tech_transfer_scope_match
from patent_law_mcp.tools.contract_practice import design_licensing_terms, review_licensing_contract
from patent_law_mcp.tools.deadlines import (
    calculate_annuity_schedule,
    check_portfolio_annuities,
    calculate_patent_deadline,
    calculate_patent_term,
    check_patent_rights_status,
)
from patent_law_mcp.tools.document_parser import (
    analyze_patent_document,
    get_bundled_sample_patent,
    parse_raw_patent_text,
)
from patent_law_mcp.tools.employee_invention_practice import (
    calculate_disposal_compensation,
    evaluate_exclusive_renewal,
    evaluate_unutilized_free_license,
    process_invention_disclosure,
)
from patent_law_mcp.tools.national_disposal import (
    calculate_registration_compensation,
    calculate_royalty_estimate,
    get_trustee_obligations,
    guide_national_dispute,
    plan_national_disposal,
)
from patent_law_mcp.tools.kipris_connector import fetch_patent_smart, inspect_and_summarize_by_appno
from patent_law_mcp.tools.law_lookup import get_law_article, search_laws
from patent_law_mcp.tools.patent_search import search_patents

mcp = FastMCP(
    name="patent-law-mcp",
    instructions=(
        "지식재산처 국가직무발명특허권(국유특허) 업무 중심 MCP 서버. 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 "
        "규정·시행규칙과 지식재산처 고시(업무 운영요령)를 기준으로 신고·승계, 등록보상금, 처분 방식 판정, 실시료 예정가격, "
        "계약, 처분보상금, 수탁기관 보고·정산, 심판·소송 절차를 다룹니다. 대학·출연연(public_research)·민간 기업(private_company) "
        "프로파일은 profile 인자나 PATENT_LAW_MCP_PROFILE로 보조 지원합니다. "
        "도구가 found=False·warnings·'미확인'을 반환하면 그 사실을 그대로 전달하고, 특허번호·출원인·수치를 추측해 채우지 마십시오. "
        "법령·고시 기준값은 policies/kipo_notice_rules.yaml에 있으며, verification_notes에 원문 확인이 필요한 항목이 표시됩니다. "
        "결과의 legal_audit_basis.source_text_verified_on은 원문 대조일이며, 그 이후 개정 여부는 check_legal_source_updates로 확인합니다."
    ),
)

LOCAL = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
NETWORK = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)


def register(fn, name: str, description: str, annotations: ToolAnnotations = LOCAL) -> None:
    mcp.tool(name=name, description=description, annotations=annotations)(fn)


# 1. 국가직무발명특허권 업무 (지식재산처 규정·시행규칙·고시 기준, 핵심)
register(
    process_invention_disclosure,
    "process_invention_disclosure",
    "직무발명 신고 접수·승계 심의 안건 (국유특허: 시행규칙 제2조 신고서류, 제3조 승계 고려사항, 고시 제26조 국가 명의 부기 명칭, 제4조 등록요청)",
)
register(
    calculate_registration_compensation,
    "calculate_registration_compensation",
    "[국유특허] 등록보상금 발명자별 배분 (영 제16조: 특허 50만·실용신안 30만·디자인 20만 원 범위, 동일 발명 1회)",
)
register(
    plan_national_disposal,
    "plan_national_disposal",
    "[국유특허] 처분 방식 판정 — 유상·무상(영 제10조 제2항 4개 사유), 수의계약·경쟁입찰(영 제11조, 예외 7개), "
    "계약기간 상한(3년+연장), 입찰 공고 마감(30일 전), 수의계약 신청서류·계약서 기재사항·신원 확인 서류",
)
register(
    calculate_royalty_estimate,
    "calculate_royalty_estimate",
    "[국유특허] 실시료·매각 예정가격 계산 (시행규칙 제11조: 총판매예정수량 × 연도별 공장도가격 평균 × 점유율 × 기본율 3%(2~4%), "
    "단위당 실시료, 중소기업 재실시 2%, 전용실시 최소실시료 비교)",
)
register(
    design_licensing_terms,
    "design_licensing_terms",
    "통상·전용실시 계약조건 초안 (국유특허: 시행규칙 제11조 기본율 3%·점유율 산식, 최소실시료 300만 원, 경쟁입찰 원칙, 계약기간 3년)",
)
register(
    review_licensing_contract,
    "review_licensing_contract",
    "기술실시계약서 초안의 필수 조항 포함 여부 1차 점검 (부정·면제 문구는 '확인 필요'로 표시, 최종 법무 검토 필요)",
)
register(
    evaluate_unutilized_free_license,
    "evaluate_unutilized_free_license",
    "[국유특허 전용] 등록 후 일정 기간 미실시된 국유특허의 무상 통상실시 해당 여부와 후속 유상 전환 조건 검토",
)
register(
    evaluate_exclusive_renewal,
    "evaluate_exclusive_renewal",
    "[국유특허 전용] 전용실시계약 갱신 검토 (투자금 미회수·인허가 시험 진행 사유 자동 판정, 신청 기한 확인)",
)
register(
    calculate_disposal_compensation,
    "calculate_disposal_compensation",
    "기술료 수입 기준 발명자 보상금 산출 및 발명자별 비과세·과세 구분 (재직 근로소득 / 퇴직 기타소득). "
    "profile: national(국유특허 처분보상금)·public_research·private_company",
)
register(
    get_trustee_obligations,
    "get_trustee_obligations",
    "[국유특허 수탁기관] 분기 실적보고(다음 달 15일)·대장 통지 일정, 계약 승인·처분결과 통지·만료 후 정산, "
    "변경 통보(30일), 금품 수수 금지, 기여보상금 상한(15%) 정리",
)
register(
    guide_national_dispute,
    "guide_national_dispute",
    "[국유특허] 심판 청구·특허법원 소송 시 지식재산처·발명기관 대응 절차와 대리인 선임 (고시 제21조~제24조)",
)
register(
    check_legal_source_updates,
    "check_legal_source_updates",
    "기준값의 근거 법령·고시(규정·시행규칙·고시·특허법 등)가 마지막 원문 대조 이후 개정됐는지 국가법령정보센터 현재 원문으로 확인 "
    "(버전 변경, 감시 조문 본문 변경·삭제, '300만원'·'3퍼센트' 같은 기준값 문구 누락). 인증키 불필요, 24시간 캐시",
    NETWORK,
)
register(
    get_policy_table,
    "get_policy_table",
    "프로파일(national·public_research·private_company)별 기준값(최소실시료·보상 비율·비과세 한도 등), 근거 조항, 원문 확인 필요 항목 조회",
)

# 2. 권리 유지·기한 관리
register(
    calculate_annuity_schedule,
    "calculate_annuity_schedule",
    "설정등록일 기준 연차료 납부기한·추가납부기간·회복 신청 가능기간과 현재 상태 계산 (금액은 계산하지 않음)",
)
register(
    check_portfolio_annuities,
    "check_portfolio_annuities",
    "여러 특허의 다음 연차료 기한을 한 번에 계산해 소멸 추정·회복 가능·추가납부·임박 순으로 정렬 (보유 국유특허 일괄 점검)",
)
register(
    calculate_patent_term,
    "calculate_patent_term",
    "출원일 기준 존속기간 만료일 계산 (특허 20년·실용신안 10년, 연장 일수 반영)",
)
register(
    calculate_patent_deadline,
    "calculate_patent_deadline",
    "특허 절차 기한 계산 (특허법 제14조: 첫날 불산입·역 계산·공휴일이면 다음 날). 조약/국내우선권 12개월, PCT 31개월, "
    "심사청구 3년, 공지예외 12개월 또는 임의 개월·일수",
)
register(
    check_patent_rights_status,
    "check_patent_rights_status",
    "특허번호로 서지·상태 조회(번호 검증) 후 존속기간 만료일과 연차료 상태 정리",
    NETWORK,
)

# 3. 특허·법령 원문 확보 (실데이터)
register(
    search_patents,
    "search_patents",
    "KIPRIS Plus 공식 API로 한국 특허 검색 (키워드 또는 출원인+명칭, KIPRIS_API_KEY 필요). 결과는 가공·재정렬하지 않음",
    NETWORK,
)
register(
    fetch_patent_smart,
    "fetch_patent_smart",
    "출원·등록·공개번호로 특허 서지·초록·청구항 조회. 받은 문서의 번호가 요청과 일치하는지 검증하며, "
    "확인 못 하면 found=False 반환 (출원번호는 KIPRIS_API_KEY 필요, 등록·공개번호는 Google Patents)",
    NETWORK,
)
register(
    inspect_and_summarize_by_appno,
    "inspect_and_summarize_by_appno",
    "특허번호로 원문 조회·검증 후 요약 초안까지 실행 (조회 실패 시 요약하지 않고 사유 반환)",
    NETWORK,
)
register(
    search_laws,
    "search_laws",
    "국가법령정보센터에서 법령(법률·시행령·시행규칙) 또는 행정규칙(고시 등) 검색 (LAW_OC 필요)",
    NETWORK,
)
register(
    get_law_article,
    "get_law_article",
    "법령명과 조문 번호로 현행 조문 원문(항·호·목)과 시행일 조회 (예: 특허법 제100조, LAW_OC 필요)",
    NETWORK,
)
register(
    parse_raw_patent_text,
    "parse_raw_patent_text",
    "붙여넣은 공보·명세서 텍스트에서 명칭·출원/등록/공개번호·출원인·IPC·초록·청구항 분해 (찾지 못한 항목은 warnings로 안내)",
)
register(
    get_bundled_sample_patent,
    "get_bundled_sample_patent",
    "도구 시연·테스트용 가상 샘플 특허 로드 (실존 특허 아님)",
)

# 4. 기술 분석·요약 (기술이전 상담 자료)
register(
    summarize_patent,
    "summarize_patent",
    "특허 원문(명칭·초록·청구항·명세서)에서 문장을 발췌해 기술이전 상담용 요약 초안과 기술소개영상 시그니처 유형 추천 생성 "
    "(원문에 없는 효과·수치는 만들지 않음)",
)
register(
    analyze_patent_document,
    "analyze_patent_document",
    "붙여넣은 공보 텍스트를 파싱해 요약 초안·TRL 안내·수요기업 탐색 참고자료를 함께 생성 (외부 API 불필요)",
)
register(
    ground_summary_figures,
    "ground_summary_figures",
    "작성된 요약문에서 원문에 없는 효과 수치('30% 절감', '2배 향상', '3시간 단축' 등)가 든 문장을 '추가 검증 필요'로 교체 "
    "(patent-summary-wizard summaryGrounding 규칙)",
)
register(
    ground_patent_applications,
    "ground_patent_applications",
    "제안된 활용 용도를 원문 발췌와 대조해 청구항 명시 용도·명세서 일반 용도·근거 미확인으로 분류 "
    "(patent-summary-wizard applicationGrounding 규칙)",
)
register(
    evaluate_commercialization,
    "evaluate_commercialization",
    "실증 근거 수준 또는 요약서 상용화전망 서술로 TRL 판정, 제시 TRL이 서술 단계와 어긋나면 보정 "
    "(patent-summary-wizard trlConsistency 규칙)",
)
register(
    verify_tech_transfer_scope_match,
    "verify_tech_transfer_scope_match",
    "청구항 구성요소와 도입 희망 기업 제품 설명의 키워드 1차 대조 (부정 표현 반영, 침해 감정 아님)",
)

# 5. 기술 마케팅 보조
register(
    bundle_patents_for_transfer,
    "bundle_patents_for_transfer",
    "여러 특허(공정·장치·소재)를 기술이전 패키지로 묶고 유형별 역할과 계약 구조 초안 정리",
)
register(
    find_target_licensees_by_patent,
    "find_target_licensees_by_patent",
    "IPC 기반 KSIC 참고 매핑과 기업 규모별 수요기업군·발굴 채널 정리",
)

def main(argv=None):
    import argparse
    import os

    ap = argparse.ArgumentParser(prog="patent-law-mcp", description="특허 실무 MCP 서버")
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default=os.environ.get("PATENT_LAW_MCP_TRANSPORT", "stdio"))
    ap.add_argument("--host", default=os.environ.get("PATENT_LAW_MCP_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PATENT_LAW_MCP_PORT", "8000")))
    ap.add_argument("--allowed-host", action="append", default=[], help="외부 접속 Host 헤더 허용 (예: mcp.example.org)")
    args = ap.parse_args(argv)

    if args.transport == "stdio":
        mcp.run()
        return
    from patent_law_mcp.http_app import serve_http

    serve_http(mcp, args.host, args.port, args.allowed_host)


if __name__ == "__main__":
    main()
