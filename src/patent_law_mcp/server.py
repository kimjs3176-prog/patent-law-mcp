"""Patent Law MCP 메인 서버 (FastMCP 기반)

지식재산처 최신 국유특허권 처분관리 업무편람 및
국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령(지식재산처고시 제2025-4호) 반영
"""

from mcp.server.fastmcp import FastMCP

# 도구 모듈 임포트
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
    analyze_claim_elements_chart,
    evaluate_workaround_points,
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

# FastMCP 서버 생성
mcp = FastMCP(
    name="patent-law-mcp",
    description="지식재산처 업무편람 및 고시(제2025-4호) 기반 특허실무·기술이전 전문 MCP 서버",
)

# 1. 기술실시계약 실무 도구 등록
mcp.tool(
    name="design_licensing_terms",
    description="지식재산처 고시 기준 최소실시료(300만원/60일 이내) 및 전용/통상실시 계약조건 산출",
)(design_licensing_terms)

mcp.tool(
    name="review_licensing_contract",
    description="기술실시계약서 초안 조항 검토 및 지식재산처 승인·사후 감사 리스크 체크리스트 점검",
)(review_licensing_contract)

# 2. 직무발명 및 국유특허 처분 실무 도구 등록 (지식재산처 최신 고시 반영)
mcp.tool(
    name="process_invention_disclosure",
    description="직무발명 신고 접수 및 직무범위성 심의위원회 상정 안건 작성 (지식재산처 업무편람 서식)",
)(process_invention_disclosure)

mcp.tool(
    name="calculate_disposal_compensation",
    description="지식재산처 고시 제11조에 따른 직접비용 공제 후 순수입 50% 처분보상금 산출 및 지급 명세표 작성",
)(calculate_disposal_compensation)

mcp.tool(
    name="evaluate_unutilized_free_license",
    description="등록 후 3년 미실시 국유특허의 3년 무상 통상실시 및 중소기업 재계약 시 기본율 2% 우대요율 심의 (고시 제3조·제7조)",
)(evaluate_unutilized_free_license)

mcp.tool(
    name="evaluate_exclusive_renewal",
    description="국유특허 전용실시계약의 5대 법정 갱신 사유(투자금 미회수 등) 및 만료 30일 전 신청 요건 심의 (고시 제10조)",
)(evaluate_exclusive_renewal)

# 3. 청구항 및 FTO/회피설계 실무 도구 등록
mcp.tool(
    name="analyze_claim_elements_chart",
    description="청구항 1항 구성요소 분해 및 목표 제품과의 요소별 대비표(Element-by-Element Chart) 작성",
)(analyze_claim_elements_chart)

mcp.tool(
    name="evaluate_workaround_points",
    description="청구항 구성요소 기준 침해 회피설계(생략·치환·공지기술 항변) 전략 제시",
)(evaluate_workaround_points)

# 4. 특허 분석 실무 도구 등록
mcp.tool(
    name="summarize_patent",
    description="특허 원문 근거 요약서 생성 및 AI 환각 수치 그라운딩 보정 (atipsum 실무 로직)",
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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
