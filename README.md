# Patent Law MCP (`patent-law-mcp`)

**공공·국유 특허 기술이전 실무** 및 **지식재산처 최신 국유특허 처분관리 업무편람(지식재산처고시 제2025-4호)**에 특화된 기술거래·계약 실무 전용 Model Context Protocol (MCP) 서버입니다.

> ⚖️ **실무 포지셔닝 및 면책 (Disclaimer)**  
> 본 MCP 서버는 **변리사의 특허 출원 대리, 명세서 작성, 심사/거절이유(OA) 대응 업무를 대체하지 않습니다.**  
> 공공연구기관 및 국가직무발명의 **기술이전 계약조건 설계, 감사 대비 계약서 검토, 국유특허 처분·보상 행정 절차, 도입 기업 제품과 권리범위 매칭 확인**을 지원하는 기술거래기관/연구기관 실무 보조 도구입니다.

---

## 🛠️ 실무 도구 구성 (Practice Tools)

### 1. 기술실시계약 실무 (`tools/contract_practice.py`)
- **`design_licensing_terms`**: 지식재산처 고시 제9조에 따른 **전용실시 최소실시료(300만 원 이상 / 60일 이내 납부)** 의무 및 기업 규모별 선급·경상기술료율, 불실시 해지특약 설계
- **`review_licensing_contract`**: 기술실시계약서 초안의 지식재산처 승인 요건 및 감사원 감사 대비 필수 특약(장부실사권, 불실시 해약권 등) 점검

### 2. 직무발명 및 국유특허 처분 실무 (`tools/employee_invention_practice.py`)
- **`process_invention_disclosure`**: 직무발명 신고 접수 및 직무범위성 심의 안건 작성 (지식재산처 업무편람 표준 서식)
- **`calculate_disposal_compensation`**: 지식재산처 고시 제11조에 따라 직접비용 공제 후 **순수입금의 50% 처분보상금 산출 및 소득세법상 비과세 한도(연 700만 원) 반영 지급 명세서** 작성
- **`evaluate_unutilized_free_license`**: 등록 후 3년 미실시 국유특허의 **최대 3년 무상 통상실시(고시 제3조)**, 공동권리자 동의서 체크 및 중소기업 재계약 시 **실시료 기본율 2% 인하 우대(고시 제7조)** 심의
- **`evaluate_exclusive_renewal`**: 국유특허 전용실시계약의 **법정 5대 갱신 사유(투자금 미회수, 인허가 시험 등) 및 만료 30일 전 신청 요건(고시 제10조)** 심의

### 3. 기술이전 권리범위 매칭 실무 (`tools/claims_practice.py`)
- **`verify_tech_transfer_scope_match`**: 기술실시계약 체결 전, **도입 희망 기업 제품이 특허 청구항 필수 구성을 실제로 실시하는지(All Elements Rule) 대조**하여 실시계약 체결 필요성을 객관적으로 판정

### 4. 특허 분석 및 그라운딩 실무 (`tools/analysis.py`)
- **`summarize_patent`**: 특허 원문 근거 기술 요약서 생성 및 AI 환각 수치 그라운딩 보정 (atipsum 실무 로직)
- **`evaluate_commercialization`**: 기술 성숙도(TRL 1~9단계) 및 시장 사업화 진입 장벽 진단

### 5. 특허 추천 실무 (`tools/recommendation.py`)
- **`find_patents_by_business_need`**: 기업 주력 품목 및 도입 목적(신제품, 원가절감 등)에 맞는 국유/공공특허 매칭 추천
- **`recommend_similar_patents`**: 기준 특허와 기술적·기능적으로 유사한 특허 후보 추천
- **`recommend_free_transfer_patents`**: 중소기업 및 농업인 대상 무상기술이전(나눔특허, 국유특허) 추천

---

## 🚀 빠른 시작 (`uv` 기반)

```bash
cd patent-mcp
uv sync
uv run patent-law-mcp
```
