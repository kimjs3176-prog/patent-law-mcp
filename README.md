# Patent MCP (`patent-law-mcp`)

특허 분석, 특허 추천 및 **특허실무(기술실시계약, 국가직무발명 처분·보상, 청구항 FTO 분석)**에 고도로 특화된 Model Context Protocol (MCP) 서버입니다.

단순한 일반 법령 조문 검색을 넘어, 현직 변리사 및 기술거래기관 실무자가 실제로 수행하는 계약 조항 검토, 기술료율 산출, 직무발명 심의, 청구항 구성요소 대비표 작성 등의 전문 실무 파이프라인을 AI 에이전트(Claude Desktop, Cursor, Claude Code 등)에 제공합니다.

---

## 🛠️ 특허실무 전문 도구 세트 (Practice Tools)

### 1. 기술실시계약 실무 (`tools/contract_practice.py`)
- **`design_licensing_terms`**: 전용실시/통상실시 계약 표준 조건 설계 (기업 규모별 선급·경상기술료율, 불실시 해지특약, 재실시권 제한, 감사 대비 장부열람권 명시)
- **`review_licensing_contract`**: 기술실시계약서 초안의 독소 조항 점검, 필수 공공특허 면책 조항 누락 및 사후 감사 리스크 체크리스트

### 2. 직무발명 및 국유특허 처분 실무 (`tools/employee_invention_practice.py`)
- **`process_invention_disclosure`**: 직무발명 신고 접수 및 직무범위성 판정, 기관 심의위원회 상정 안건 작성
- **`calculate_disposal_compensation`**: 국유특허 기술료 입금에 따른 발명자 처분보상금(순수입 50%) 산출 및 지분율별 지급 명세서 작성
- **`evaluate_free_license_qualification`**: 국유특허 무상실시(농업인·청년농·소상공인 대상 기술료 전액 면제) 적격성 심의

### 3. 청구항 권리범위 및 FTO/회피설계 실무 (`tools/claims_practice.py`)
- **`analyze_claim_elements_chart`**: 청구항 1항 구성요소 완비의 법칙(All Elements Rule) 분해 및 목표 제품과의 요소별 대비표(Element-by-Element Chart) 작성
- **`evaluate_workaround_points`**: 청구항 구성요소 기준 침해 회피설계 전략(완전 생략, 실질적 메커니즘 치환, 공지기술 항변)

### 4. 특허 분석 및 그라운딩 실무 (`tools/analysis.py`)
- **`summarize_patent`**: 특허 원문 근거 요약서 생성 및 AI 환각 수치 그라운딩 보정 (atipsum 검증 로직)
- **`evaluate_commercialization`**: 기술 성숙도(TRL 1~9단계) 및 시장 사업화 진입 장벽 진단

### 5. 특허 추천 실무 (`tools/recommendation.py`)
- **`find_patents_by_business_need`**: 기업 주력 품목 및 도입 목적(신제품, 원가절감 등)에 맞는 국유/공공특허 매칭 추천
- **`recommend_similar_patents`**: 기준 특허와 기술적·기능적으로 유사한 특허 후보 추천
- **`recommend_free_transfer_patents`**: 중소기업 및 농업인 대상 무상기술이전(나눔특허, 국유특허) 추천

---

## 🔄 연계 워크플로 예시 (Chained Practice Workflow)

1. **특허 발굴**: `find_patents_by_business_need`로 기업 애로사항에 맞는 국유특허 발굴
2. **기술·권리 진단**: `summarize_patent`로 기술 요약 확인 후 `analyze_claim_elements_chart`로 제품과의 권리범위 침해/저촉 여부 검토
3. **계약조건 설계**: `design_licensing_terms`로 기업 규모에 맞는 전용/통상실시 선급·경상기술료율 및 필수 특약 조항 산출
4. **계약서 검토**: `review_licensing_contract`로 감사 대비 리스크 및 독소 조항 사전 점검
5. **사후 보상**: 계약 체결 후 `calculate_disposal_compensation`으로 발명자 처분보상금 지급 품의서 작성

---

## 🚀 빠른 시작 (`uv` 기반)

```bash
cd patent-law-mcp
uv sync
uv run patent-law-mcp
```
