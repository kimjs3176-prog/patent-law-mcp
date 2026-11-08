# Patent Law MCP (`patent-law-mcp`)

**지식재산처 최신 국유특허권 처분관리 업무편람** 및 **국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령(지식재산처고시 제2025-4호)**을 완벽히 반영한 특허실무 전문 Model Context Protocol (MCP) 서버입니다.

`patent-summary-wizard`(Agri IP Summary · atipsum)의 실무 분석 로직과 최신 지식재산처 행정규칙을 결합하여, AI 에이전트(Claude Desktop, Cursor, Claude Code 등)가 실제 국가직무발명 심의, 국유특허 기술실시계약, FTO 권리범위 분석, 처분보상금 산정 업무를 정확하게 지원합니다.

---

## 🛠️ 지식재산처 최신 업무편람 특화 도구 세트

### 1. 직무발명 및 국유특허 처분 실무 (`tools/employee_invention_practice.py`)
- **`process_invention_disclosure`**: 직무발명 신고 접수 및 직무범위성 심의 안건 작성 (지식재산처 업무편람 표준 서식)
- **`calculate_disposal_compensation`**: 지식재산처 고시 제11조에 따라 직접비용(출원·등록·기술이전 비용) 공제 후 **순수입금의 50% 처분보상금 산출 및 지분별 지급 명세서** 작성
- **`evaluate_unutilized_free_license`**: 등록 후 3년 미실시 국유특허의 **최대 3년 무상 통상실시(고시 제3조)** 및 중소기업 재계약 시 **실시료 기본율 2% 인하 우대요율(고시 제7조)** 심의
- **`evaluate_exclusive_renewal`**: 국유특허 전용실시계약의 **법정 5대 갱신 사유(투자금 미회수, 인허가 시험 등) 및 만료 30일 전 신청 요건(고시 제10조)** 심의

### 2. 기술실시계약 실무 (`tools/contract_practice.py`)
- **`design_licensing_terms`**: 지식재산처 고시 제9조에 따른 **전용실시 최소실시료(300만 원 이상 / 계약일로부터 60일 이내 납부)** 의무 및 기업 규모별 선급·경상기술료율, 불실시 해지특약 설계
- **`review_licensing_contract`**: 기술실시계약서 초안의 지식재산처 승인 요건 및 감사원 감사 대비 필수 특약(장부실사권, 불실시 해약권 등) 점검

### 3. 청구항 권리범위 및 FTO/회피설계 실무 (`tools/claims_practice.py`)
- **`analyze_claim_elements_chart`**: 독립항 구성요소 완비의 법칙(All Elements Rule) 분해 및 목표 제품과의 요소별 대비표(Element-by-Element Chart) 작성
- **`evaluate_workaround_points`**: 청구항 구성요소 기준 침해 회피설계 전략(완전 생략, 실질적 메커니즘 치환, 공지기술 항변)

### 4. 특허 분석 및 그라운딩 실무 (`tools/analysis.py`)
- **`summarize_patent`**: 특허 원문 근거 요약서 생성 및 AI 환각 수치 그라운딩 보정 (atipsum 검증 로직)
- **`evaluate_commercialization`**: 기술 성숙도(TRL 1~9단계) 및 시장 사업화 진입 장벽 진단

### 5. 특허 추천 실무 (`tools/recommendation.py`)
- **`find_patents_by_business_need`**: 기업 주력 품목 및 도입 목적(신제품, 원가절감 등)에 맞는 국유/공공특허 매칭 추천
- **`recommend_similar_patents`**: 기준 특허와 기술적·기능적으로 유사한 특허 후보 추천
- **`recommend_free_transfer_patents`**: 중소기업 및 농업인 대상 무상기술이전(나눔특허, 국유특허) 추천

---

## 📚 적용 행정규칙 및 법령 체계

- **지식재산처고시 제2025-4호**: 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령 (시행 2025. 10. 30.)
- **대통령령**: 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 규정
- **법률**: 발명진흥법, 기술의 이전 및 사업화 촉진에 관한 법률, 특허법

---

## 🚀 빠른 시작 (`uv` 기반)

```bash
cd patent-mcp
uv sync
uv run patent-law-mcp
```
