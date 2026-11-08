"""Patent Law MCP 메인 서버 (FastMCP 기반)

공공·국유 특허 기술이전 실무 및 국가공무원 등 직무발명 처분·보상 실무 보조 도구

[면책 조항]
본 MCP 서버는 변리사의 출원·심사 대리 업무를 대신하지 않으며,
공공연구기관 및 국가직무발명의 기술이전 계약 실무, 처분·보상 행정 절차,
도입 기업 제품과의 권리범위 1차 대조를 보조하기 위한 도구입니다.
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from patent_law_mcp.tools.analysis import evaluate_commercialization, ground_summary_figures, summarize_patent
from patent_law_mcp.tools.bundling_and_targeting import bundle_patents_for_transfer, find_target_licensees_by_patent
from patent_law_mcp.tools.claims_practice import verify_tech_transfer_scope_match
from patent_law_mcp.tools.contract_practice import design_licensing_terms, review_licensing_contract
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
from patent_law_mcp.tools.kipris_connector import fetch_patent_smart, inspect_and_summarize_by_appno

mcp = FastMCP(
    name="patent-law-mcp",
    instructions=(
        "공공·국유 특허 기술이전 계약 및 국가공무원 등 직무발명 처분·보상 실무 보조 MCP 서버. "
        "도구가 found=False·warnings·'미확인'을 반환하면 그 사실을 그대로 전달하고, 특허번호·출원인·수치를 추측해 채우지 마십시오. "
        "법령·고시 기준값은 policies/kipo_notice_rules.yaml에 있으며, verification_notes에 원문 확인이 필요한 항목이 표시됩니다."
    ),
)

LOCAL = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
NETWORK = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)


def register(fn, name: str, description: str, annotations: ToolAnnotations = LOCAL) -> None:
    mcp.tool(name=name, description=description, annotations=annotations)(fn)


# 0. 특허 원문 확보
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
    parse_raw_patent_text,
    "parse_raw_patent_text",
    "붙여넣은 공보·명세서 텍스트에서 명칭·출원/등록/공개번호·출원인·IPC·초록·청구항 분해 (찾지 못한 항목은 warnings로 안내)",
)
register(
    analyze_patent_document,
    "analyze_patent_document",
    "붙여넣은 공보 텍스트를 파싱해 요약 초안·TRL 안내·수요기업 탐색 참고자료를 함께 생성 (외부 API 불필요)",
)
register(
    get_bundled_sample_patent,
    "get_bundled_sample_patent",
    "도구 시연·테스트용 가상 샘플 특허 로드 (실존 특허 아님)",
)

# 1. 분석·요약
register(
    summarize_patent,
    "summarize_patent",
    "특허 원문(명칭·초록·청구항·명세서)에서 문장을 발췌해 기술이전 상담용 요약 초안 생성 (원문에 없는 효과·수치는 만들지 않음)",
)
register(
    ground_summary_figures,
    "ground_summary_figures",
    "작성된 요약문에서 원문에 없는 효과 수치('30% 절감', '2배 향상' 등)를 찾아 정성 표현으로 교체",
)
register(
    evaluate_commercialization,
    "evaluate_commercialization",
    "확인된 실증 근거 수준(개념·실험실·시제품·현장실증·제품화)으로 기술성숙도(TRL) 범위 판정",
)

# 2. 기술실시계약
register(
    design_licensing_terms,
    "design_licensing_terms",
    "국유특허 통상·전용실시 계약조건 초안 산출 (전용실시 최소실시료·납부기한, 경쟁입찰 원칙, 예상 매출 기준 경상기술료 추정)",
)
register(
    review_licensing_contract,
    "review_licensing_contract",
    "기술실시계약서 초안의 필수 조항 포함 여부 1차 점검 (부정·면제 문구는 '확인 필요'로 표시, 최종 법무 검토 필요)",
)

# 3. 직무발명·국유특허 처분
register(
    process_invention_disclosure,
    "process_invention_disclosure",
    "직무발명 신고 접수 및 직무발명심의위원회 상정 안건 초안 작성",
)
register(
    calculate_disposal_compensation,
    "calculate_disposal_compensation",
    "국유특허 처분수입금 기준 처분보상금 산출 및 발명자별 비과세·과세 구분 (재직자 근로소득 / 퇴직자 기타소득)",
)
register(
    evaluate_unutilized_free_license,
    "evaluate_unutilized_free_license",
    "등록 후 일정 기간 미실시된 국유특허의 무상 통상실시 해당 여부와 후속 유상 전환 조건 검토",
)
register(
    evaluate_exclusive_renewal,
    "evaluate_exclusive_renewal",
    "국유특허 전용실시계약 갱신 검토 (투자금 미회수·인허가 시험 진행 사유 자동 판정, 신청 기한 확인)",
)

# 4. 권리범위·포트폴리오·수요기업
register(
    verify_tech_transfer_scope_match,
    "verify_tech_transfer_scope_match",
    "청구항 구성요소와 도입 희망 기업 제품 설명의 키워드 1차 대조 (부정 표현 반영, 침해 감정 아님)",
)
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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
