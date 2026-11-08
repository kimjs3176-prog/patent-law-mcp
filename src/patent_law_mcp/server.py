"""Patent Law MCP 메인 서버 (FastMCP 기반)

공공·국유 특허 기술이전 실무 및 지식재산처 최신 업무편람·고시(제2025-4호) 특화

[면책 조항]
본 MCP 서버는 변리사의 출원·심사 대리 업무를 대신하지 않으며,
공공연구기관 및 국가직무발명의 기술이전 계약 실무, 처분·보상 행정 절차,
도입 기업 제품과의 권리범위 매칭 검토를 보조하기 위한 전문 실무 도구입니다.
"""

from mcp.server.fastmcp import FastMCP

# 기존 도구 모듈 임포트
from patent_law_mcp.tools.contract_practice import (
    design_licensing_terms,
    review_licensing_contract,
)
from patent_law_mcp.tools.employee_invention_practice import (
    process_invention_disclosure,
    calculate_disposal_compensation,
    evaluate_unutilized_free_license,
    evaluate_exclusive_renewal,
)
from patent_law_mcp.tools.claims_practice import (
    verify_tech_transfer_scope_match,
)
from patent_law_mcp.tools.analysis import (
    summarize_patent,
    evaluate_commercialization,
)
from patent_law_mcp.tools.recommendation import (
    find_patents_by_business_need,
    recommend_similar_patents,
    recommend_free_transfer_patents,
)

# 신규 고도화 도구 모듈 임포트 (1번: KIPRISPlus 실시간 연동, 4번: 패키징 & 수요기업 역매칭)
from patent_law_mcp.tools.kipris_connector import (
    fetch_patent_from_kipris,
    inspect_and_summarize_by_appno,
)
from patent_law_mcp.tools.bundling_and_targeting import (
    bundle_patents_for_transfer,
    find_target_licensees_by_patent,
)

# FastMCP 서버 생성
mcp = FastMCP(
    name="patent-law-mcp",
    description=(
        "공공·국유 특허 기술이전 계약 및 지식재산처 업무편람(고시 제2025-4호) 특화 기술거래 실무 MCP 서버. "
        "(출원·심사 대리가 아닌 기술이전·처분 실무 보조 도구)"
    ),
)

# 1. 기술실시계약 실무 도구 등록
mcp.tool(
    name="design_licensing_terms",
    description="지식재산처 고시 기준 전용실시 최소실시료(300만원/60일 이내) 및 전용/통상실시 계약조건 산출",
)(design_licensing_terms)

mcp.tool(
    name="review_licensing_contract",
    description="기술실시계약서 초안 조항 검토 및 지식재산처 승인·사후 감사 리스크 체크리스트 점검",
)(review_licensing_contract)

# 2. 직무발명 및 국유특허 처분 실무 도구 등록
mcp.tool(
    name="process_invention_disclosure",
    description="직무발명 신고 접수 및 직무범위성 심의위원회 상정 안건 작성 (지식재산처 업무편람 서식)",
)(process_invention_disclosure)

mcp.tool(
    name="calculate_disposal_compensation",
    description="지식재산처 고시 제11조에 따른 직접비용 공제 후 순수입 50% 처분보상금 산출 및 세액 명세표 작성",
)(calculate_disposal_compensation)

mcp.tool(
    name="evaluate_unutilized_free_license",
    description="등록 후 3년 미실시 국유특허의 3년 무상 통상실시 및 중소기업 재계약 시 기본율 2% 우대요율 심의 (고시 제3조·제7조)",
)(evaluate_unutilized_free_license)

mcp.tool(
    name="evaluate_exclusive_renewal",
    description="국유특허 전용실시계약의 5대 법정 갱신 사유(투자금 미회수 등) 및 만료 30일 전 신청 요건 심의 (고시 제10조)",
)(evaluate_exclusive_renewal)

# 3. 기술이전 권리범위 매칭 실무 도구 등록
mcp.tool(
    name="verify_tech_transfer_scope_match",
    description="기술이전 계약 체결 전, 도입 희망 기업 제품과 특허 청구항 권리범위 매칭 및 실시권 필요성 검토",
)(verify_tech_transfer_scope_match)

# 4. 특허 분석 실무 도구 등록
mcp.tool(
    name="summarize_patent",
    description="특허 원문 근거 기술 요약서 생성 및 AI 환각 수치 그라운딩 보정, 60초 브리핑 피치 대본 생성",
)(summarize_patent)

mcp.tool(
    name="evaluate_commercialization",
    description="특허 기술성숙도(TRL 1~9) 및 시장 사업화 가능성 진단",
)(evaluate_commercialization)

# 5. 특허 추천 실무 도구 등록
mcp.tool(
    name="find_patents_by_business_need",
    description="기업 주력 품목 및 도입 목적에 꼭 맞는 국유/공공특허 매칭 추천",
)(find_patents_by_business_need)

mcp.tool(
    name="recommend_similar_patents",
    description="기준 특허와 기술적·기능적으로 유사한 특허 후보 추천",
)(recommend_similar_patents)

mcp.tool(
    name="recommend_free_transfer_patents",
    description="중소기업 및 농업인 대상 무상기술이전(나눔특허, 국유특허 무상실시) 추천",
)(recommend_free_transfer_patents)

# 6. [신규 고도화 1번] KIPRISPlus 실시간 연동 도구
mcp.tool(
    name="fetch_patent_from_kipris",
    description="13자리 출원번호 입력으로 KIPRIS Plus 실시간 Open API 서지사항, 권리상태, 등록청구항 조회",
)(fetch_patent_from_kipris)

mcp.tool(
    name="inspect_and_summarize_by_appno",
    description="출원번호 하나로 KIPRIS 조회부터 원문 요약, 스펙 칩 발췌, TRL 진단, 60초 피치 대본까지 원스톱 실행",
)(inspect_and_summarize_by_appno)

# 7. [신규 고도화 4번] 특허 패키징(Bundling) 및 수요기업 역매칭(Targeting) 도구
mcp.tool(
    name="bundle_patents_for_transfer",
    description="원천·공정·장치 특허를 묶어 회피설계를 방지하고 일괄 감면율을 적용하는 기술이전 패키지 제안서 구성",
)(bundle_patents_for_transfer)

mcp.tool(
    name="find_target_licensees_by_patent",
    description="특허 IPC 및 제품 분야 기반 표준산업분류(KSIC) 매칭, 유력 수요기업군(양산/스타트업) 타겟팅 전략 도출",
)(find_target_licensees_by_patent)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
