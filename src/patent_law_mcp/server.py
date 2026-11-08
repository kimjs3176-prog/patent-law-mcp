"""Patent MCP 메인 서버 (FastMCP 기반)

특허실무 전문 도구 세트:
- 기술실시계약 실무 (전용/통상실시 조건 설계, 계약서 리스크 검토)
- 국가직무발명 처분·보상 실무 (승계 심의, 처분보상금 산정, 무상실시 심의)
- 청구항 권리범위 실무 (구성요소 완비 법칙 분해, FTO 대비표, 회피설계)
- 특허 분석 실무 (원문 근거 요약, 수치 그라운딩 보정, TRL 사업화 진단)
- 특허 추천 실무 (기업 니즈 기반 매칭, 유사 특허 추천, 무상기술이전 대상 조회)
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
    evaluate_free_license_qualification,
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
    name="patent-mcp",
    description="특허실무(기술실시계약, 국가직무발명 처분·보상, 청구항 FTO 분석, 기술이전 추천) 전문 MCP 서버",
)

# 1. 기술실시계약 실무 도구 등록
mcp.tool(name="design_licensing_terms", description="전용/통상실시 계약 표준 조건(기술료율, 불실시 특약, 재실시 제한, 감사대비 장부열람권) 산출")(
    design_licensing_terms
)
mcp.tool(name="review_licensing_contract", description="기술실시계약서 초안 조항 검토 및 공공기술 감사 리스크 체크리스트 점검")(
    review_licensing_contract
)

# 2. 직무발명 및 국유특허 처분 실무 도구 등록
mcp.tool(name="process_invention_disclosure", description="직무발명 신고 접수 및 직무범위성 심의위원회 상정 안건 작성")(
    process_invention_disclosure
)
mcp.tool(name="calculate_disposal_compensation", description="국유특허 기술료 입금에 따른 발명자 처분보상금(순수입 50%) 산출 및 지급 명세서 작성")(
    calculate_disposal_compensation
)
mcp.tool(name="evaluate_free_license_qualification", description="국유특허 무상실시(농업인·청년농·소상공인 대상 기술료 면제) 적격성 심의")(
    evaluate_free_license_qualification
)

# 3. 청구항 및 FTO/회피설계 실무 도구 등록
mcp.tool(name="analyze_claim_elements_chart", description="청구항 1항 구성요소 분해 및 목표 제품과의 요소별 대비표(Element-by-Element Chart) 작성")(
    analyze_claim_elements_chart
)
mcp.tool(name="evaluate_workaround_points", description="청구항 구성요소 기준 침해 회피설계(생략·치환·공지기술 항변) 전략 제시")(
    evaluate_workaround_points
)

# 4. 특허 분석 실무 도구 등록
mcp.tool(name="summarize_patent", description="특허 원문 근거 요약서 생성 및 AI 환각 수치 보정")(
    summarize_patent
)
mcp.tool(name="evaluate_commercialization", description="특허 기술성숙도(TRL 1~9) 및 시장 사업화 가능성 진단")(
    evaluate_commercialization
)

# 5. 특허 추천 실무 도구 등록
mcp.tool(name="find_patents_by_business_need", description="기업 주력 품목 및 도입 목적에 꼭 맞는 국유/공공특허 매칭 추천")(
    find_patents_by_business_need
)
mcp.tool(name="recommend_similar_patents", description="기준 특허와 기술적·기능적으로 유사한 특허 후보 추천")(
    recommend_similar_patents
)
mcp.tool(name="recommend_free_transfer_patents", description="중소기업 및 농업인 대상 무상기술이전(나눔특허, 국유특허 무상실시) 추천")(
    recommend_free_transfer_patents
)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
