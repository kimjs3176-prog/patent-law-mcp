# 🌾 Patent Law MCP (`patent-law-mcp`)

> **공공·국유 특허 기술이전 및 국가직무발명 처분 실무 전용 Model Context Protocol (MCP) 서버**  
> 복잡한 법제처 API나 KIPRIS 인증키 없이, 설치 즉시 100% 로컬에서 동작하는 **Zero-API 완전 자립형 특허실무 도구**입니다.

---

## ⚡ 왜 Patent Law MCP인가요?

1. **🔑 API 키 0개 (Zero-Setup)**
   - 법제처(`LAW_OC`)나 KIPRIS API 키를 신청할 필요가 없습니다.
   - 키프리스나 네이버 특허의 공보 텍스트를 복사해 붙여넣기만 하면 청구항, 초록, 서지사항을 자체 스마트 파서가 100% 분해합니다.
2. **⚖️ 최신 지식재산처 고시(제2025-4호) 자동 판정**
   - **전용실시 최소실시료(300만 원 이상 / 60일 이내 납부)** 강행규정 자동 반영
   - **등록 후 3년 미실시 국유특허 3년 무상실시** 및 중소기업 재계약 시 기본율 2%p 인하 심의
   - **처분보상금 산출(순수입 50%)** 및 소득세법상 연간 700만 원 비과세 자동 계산
3. **🎬 실무 원스톱 파이프라인**
   - 특허 요약서 작성 ➔ 60초 바이어 브리핑 피치 ➔ 기술실시계약 조건 설계 ➔ 권리범위 매칭 ➔ 특허 패키징(번들링)까지 한 번에 연결됩니다.

---

## 🚀 빠른 시작 (Quick Start)

### 1. Claude Desktop 연결
Claude Desktop 설정 파일(`claude_desktop_config.json`)의 `mcpServers`에 아래 내용을 추가하세요:

```json
{
  "mcpServers": {
    "patent-law-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/절대경로/patent-law-mcp",
        "run",
        "patent-law-mcp"
      ]
    }
  }
}
```

### 2. Cursor IDE 연결
Cursor 설정의 **Features > MCP Servers**에서 `Add New MCP Server`를 누르고 등록합니다:
- **Name**: `patent-law-mcp`
- **Type**: `command`
- **Command**: `uv --directory /절대경로/patent-law-mcp run patent-law-mcp`

---

## 🛠️ 주요 도구 한눈에 보기

| 분류 | 도구명 | 하는 일 |
|:---|:---|:---|
| **📄 공보 분석 & 요약** | `analyze_patent_document` | 복사한 공보 텍스트에서 청구항·스펙 칩을 추출하고 60초 바이어 피치와 TRL을 원스톱 진단 (API 불필요) |
| | `summarize_patent` | 특허 원문 기반 A4 요약서 및 AI 환각 수치 정성적 자동 보정 |
| **💼 기술실시계약 실무** | `design_licensing_terms` | 기업 규모별 선급·경상기술료율 및 전용실시 최소실시료(300만원) 강행규정 산출 |
| | `review_licensing_contract` | 계약서 초안의 필수 감사 특약(불실시 해지권, 장부 실사권) 점검 |
| **🏛️ 국유특허 처분·행정** | `evaluate_unutilized_free_license` | 등록 후 3년 미실시 국유특허의 3년 무상 통상실시 및 중소기업 재계약 우대 심의 |
| | `calculate_disposal_compensation` | 직접비용 공제 후 순수입 50% 처분보상금 및 700만원 비과세 한도 자동 계산 |
| | `evaluate_exclusive_renewal` | 전용실시 갱신 법정 5대 사유 및 만료 30일 전 신청 요건 심의 |
| **🎯 타겟팅 & 권리범위** | `verify_tech_transfer_scope_match` | 도입 희망 기업 제품과 특허 청구항 구성요소(All Elements Rule) 일치 여부 대조 |
| | `bundle_patents_for_transfer` | 원천·공정·장치 특허를 묶어 회피설계를 막고 일괄 감면율(20~25%)을 적용하는 패키지 구성 |
| | `find_target_licensees_by_patent` | 특허 IPC 및 제품군 기반 표준산업분류(KSIC) 매칭 및 유력 수요기업군(양산/스타트업) 도출 |

---

## 📋 사용 예시 (Claude 질문 프롬프트)

- **공보 분석**: *"이 특허 공보 텍스트 붙여넣을 테니 핵심 스펙이랑 60초 바이어 브리핑 대본 뽑아줘: [공보 내용 붙여넣기]"*
- **계약 설계**: *"중소기업에 국유특허 전용실시를 주려고 해. 예상 매출 5억일 때 지식재산처 고시 기준 최소실시료랑 추천 계약조건 뽑아줘."*
- **무상실시 심의**: *"등록된 지 4년 동안 사업화 안 된 국유특허인데, 중소기업이 무상으로 가져갈 수 있는지 심의해줘."*
- **보상금 계산**: *"기술이전 계약금 5천만 원 들어왔고 출원비용 600만 원 썼어. 발명자 2명(지분 7:3) 처분보상금 명세표 뽑아줘."*

---

## ⚙️ 법령 개정 대응 (`policies/`)

- 지식재산처 고시나 소득세법이 개정될 경우, **파이썬 코드를 고칠 필요 없이 `src/patent_law_mcp/policies/kipo_notice_rules.yaml`의 숫자만 변경**하면 즉시 전 도구에 반영됩니다.
- 모든 산출 결과에는 적용된 고시 명칭과 시행일자가 감사 추적용 메타데이터(`legal_audit_basis`)로 함께 출력됩니다.

---

> ⚖️ **실무 면책 조항 (Disclaimer)**  
> 본 MCP 서버는 변리사의 특허 출원 대리, 명세서 작성, 심사/거절이유 대응 업무를 대체하지 않으며, 공공연구기관 및 기술거래기관의 기술이전 계약, 국유특허 처분·보상 행정 절차 보조를 위해 설계되었습니다.
