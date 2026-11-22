# Patent Law MCP (`patent-law-mcp`)

> 지식재산처 **국가직무발명특허권(국유특허) 업무**를 중심으로 한 Model Context Protocol(MCP) 서버
> 「국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 규정」·같은 규정 시행규칙·지식재산처 고시(업무 운영요령)를 기준으로
> 신고·승계 → 등록보상금 → 처분 방식 판정 → 실시료 예정가격 → 계약 → 처분보상금 → 수탁기관 보고·정산 → 심판·소송까지 다룹니다.
> 대학·출연연과 민간 기업 규정은 보조 프로파일로 지원합니다.

## 원칙

- **모르면 모른다고 합니다.** 조회에 실패하거나 원문에 없는 값은 `found=False`·`warnings`·`미확인`으로 돌려주고, 특허번호·출원인·수치를 지어내지 않습니다.
- **받은 문서는 번호로 검증합니다.** Google Patents·KIPRIS에서 받은 문서의 출원·등록·공개번호가 요청과 다르면 버립니다.
- **법령 기준값은 한 파일에서 관리합니다.** 최소실시료·보상 비율·비과세 한도와 근거 조항은 `policies/*.yaml`에 있고, 원문 대조가 안 된 항목은 모든 결과에 `unverified_items`로 표시됩니다.

## 빠른 시작

### Claude Desktop (로컬, stdio)

```json
{
  "mcpServers": {
    "patent-law-mcp": {
      "command": "uv",
      "args": ["--directory", "/절대경로/patent-law-mcp", "run", "patent-law-mcp"],
      "env": {
        "KIPRIS_API_KEY": "선택: KIPRIS Plus 인증키",
        "LAW_OC": "선택: 국가법령정보 공동활용 OC",
        "PATENT_LAW_MCP_PROFILE": "national"
      }
    }
  }
}
```

### 원격(HTTP) 배포

```bash
PATENT_LAW_MCP_TOKEN=긴-임의-문자열 uv run patent-law-mcp --transport streamable-http --host 0.0.0.0 --port 8000 --allowed-host mcp.example.org
```

```bash
docker build -t patent-law-mcp .
```

```bash
docker run -p 8000:8000 -e PATENT_LAW_MCP_TOKEN=긴-임의-문자열 -e KIPRIS_API_KEY=... patent-law-mcp --allowed-host mcp.example.org
```

- 클라이언트는 `https://<host>/mcp`에 `Authorization: Bearer <토큰>` 헤더로 접속합니다.
- 토큰 없이 127.0.0.1 이외 주소에 바인딩하면 서버가 시작을 거부합니다.

## 인증키 (모두 선택)

| 환경변수 | 쓰는 도구 | 발급 |
|:---|:---|:---|
| `KIPRIS_API_KEY` | 특허 검색, 출원번호 조회, KIPRIS 공식 서지 | plus.kipris.or.kr (특허·실용 공개·등록공보 서비스) |
| `LAW_OC` | 법령 검색·조문 조회 | open.law.go.kr 회원가입 후 Open API 신청 (무료). **신청 시 호출 서버의 IP·도메인을 등록해야 합니다** |

키가 없으면 해당 도구는 발급 방법을 안내하고, 등록·공개번호 조회는 Google Patents 공개 웹으로 동작합니다.

## 도구 (32개)

### 1. 국가직무발명특허권 업무 (핵심)

| 업무 단계 | 도구 | 하는 일 · 근거 |
|:---|:---|:---|
| 신고·승계 | `process_invention_disclosure` | 직무발명신고서(별지 제1호)·성질 설명서 3항목·요약서 (시행규칙 제2조), 승계 고려사항 (제3조), 국가 명의 출원 부기 명칭 (고시 제26조), 등록요청 서류 (시행규칙 제4조) |
| 등록보상 | `calculate_registration_compensation` | 특허 50만·실용신안 30만·디자인 20만 원 범위, 동일 발명 1회, 발명자 지분 배분 (영 제16조) |
| 처분 방식 | `plan_national_disposal` | 유상·무상(영 제10조 제2항 4개 사유), 통상=수의계약·전용/매각=경쟁입찰과 예외 7개 (영 제11조), 계약기간 3년+연장 (시행규칙 제6조), 입찰 공고 30일 전 (제7조), 수의계약 신청서류 (제8조), 계약서 기재사항·신원 확인 (제9조) |
| 실시료 산정 | `calculate_royalty_estimate` | 총판매예정수량 × 연도별 공장도가격 평균 × 점유율 × 기본율 3%(2~4%), 단위당 실시료, 매각 예정가격(존속기간 실시료 총액 / 매매실례가격) (시행규칙 제11조), 중소기업 재실시 2% (고시 제7조) |
| 계약 | `design_licensing_terms` · `review_licensing_contract` | 계약조건 초안 (국유특허는 시행규칙 제11조 산식·최소실시료 300만 원·경쟁입찰), 계약서 필수 조항 점검 |
| 무상실시·갱신 | `evaluate_unutilized_free_license` · `evaluate_exclusive_renewal` | 미활용 특허 무상실시 (고시 제3~7조), 전용실시 갱신 5개 사유·30일 전 신청 (고시 제10조) |
| 처분보상 | `calculate_disposal_compensation` | 직접비용 공제 후 50% (고시 제11조 제2항), 발명자별 비과세·과세 |
| 수탁기관 | `get_trustee_obligations` | 분기 실적보고 다음 달 15일 (고시 제18조), 대장 분기 통지 (시행규칙 제13조), 계약 승인·완료문서 (고시 제17조), 처분결과 통지 (시행규칙 제12조), 만료 후 정산·납부고지 (고시 제17조 제3항), 변경 30일 내 통보 (제15조), 금품 수수 금지, 기여보상금 15% 범위 (영 제18조) |
| 심판·소송 | `guide_national_dispute` | 심판당사자 지정·대리인 선임, 패소 시 소 제기 협의(30일 불변기간), 국가소송법 준용 (고시 제21~24조) |
| 기준값 | `get_policy_table` | 기준값·근거 조항·원문 확인 필요 항목 |

### 2. 권리 유지·기한 관리

| 도구 | 하는 일 |
|:---|:---|
| `calculate_annuity_schedule` | 연차료 납부기한·추가납부기간·회복 가능기간과 현재 상태 |
| `check_portfolio_annuities` | 보유 특허 여러 건의 다음 연차료를 한 번에 계산해 소멸 추정·회복 가능·추가납부·임박 순으로 정렬 |
| `calculate_patent_term` | 존속기간 만료일 (특허 20년·실용신안 10년, 연장 반영) |
| `calculate_patent_deadline` | 특허법 제14조 기간 계산 (공휴일·토요일·노동절 반영) — 우선권 12개월, PCT 31개월, 심사청구 3년, 공지예외 12개월 |
| `check_patent_rights_status` | 번호 조회 + 존속기간 + 연차료 상태 한 번에 |

### 3. 원문 확보·기술 분석

| 도구 | 하는 일 |
|:---|:---|
| `search_patents` · `fetch_patent_smart` · `inspect_and_summarize_by_appno` | KIPRIS 검색, 번호 검증 조회(해외 포함), 조회 후 요약 |
| `search_laws` · `get_law_article` | 법령·행정규칙 검색, 조문 원문·시행일 |
| `parse_raw_patent_text` · `analyze_patent_document` · `summarize_patent` | 붙여넣은 공보 분해, 원문 발췌 요약 초안 |
| `ground_summary_figures` · `ground_patent_applications` · `evaluate_commercialization` | 근거 없는 효과 수치·용도 걸러내기, TRL 판정 |
| `verify_tech_transfer_scope_match` | 청구항 구성요소와 제품 설명 1차 대조 (침해 감정 아님) |
| `get_bundled_sample_patent` | 시연용 **가상** 샘플 (실존 특허 아님) |

### 4. 기술 마케팅 보조

| 도구 | 하는 일 |
|:---|:---|
| `bundle_patents_for_transfer` · `find_target_licensees_by_patent` | 패키지 구성, IPC→KSIC 참고 매핑과 수요기업군 |

## 기관 유형별 프로파일

| 프로파일 | 파일 | 적용 |
|:---|:---|:---|
| `national` (기본) | `policies/kipo_notice_rules.yaml` | 국유특허 — 국가공무원 등 직무발명 규정, 지식재산처고시 제2025-4호 |
| `public_research` | `policies/public_research.yaml` | 대학 산학협력단·정부출연연구기관 — 기술이전법·발명진흥법·기관 규정 |
| `private_company` | `policies/private_company.yaml` | 민간 기업 — 발명진흥법·사내 보상규정 |

- 기본 프로파일은 `PATENT_LAW_MCP_PROFILE`, 호출 단위는 도구의 `profile` 인자로 고릅니다.
- 기관·사내 규정 값(보상 비율 등)은 비워 두었습니다(`null`). 기관 값을 넣거나 호출할 때 `payout_ratio`로 주십시오.
- YAML을 고치면 다음 호출부터 반영됩니다. 필수 항목이 빠지면 오류로 알립니다.
- 다른 파일을 쓰려면 `PATENT_LAW_MCP_POLICY_FILE`로 경로를 지정합니다.

## 원문 대조 결과 (2026-11-08·2026-11-22, 국가법령정보센터)

| 대상 | 확인한 원문 |
|:---|:---|
| 고시 | 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령 [지식재산처고시 제2025-4호, 2025.10.30. 시행] 제3~11조·제13~24조·제26조 |
| 규정 | 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 규정 [대통령령 제35809호, 2025.10.01. 시행] 제2·10·11·12·14·16·17·18조 |
| 시행규칙 | 같은 규정 시행규칙 [총리령 제2054호, 2025.10.01. 시행] 제2~13조 |
| 법률 | 특허법 [법률 제21134호, 2025.11.11. 시행] 제14·30·54·55·59·79·81·81조의3·88·201조, 실용신안법 제22조, 발명진흥법 제12·13조, 같은 법 시행령 제7조, 소득세법 시행령 제17조의3 |

- **원문과 일치**:
  - 무상실시 (고시 제3조: 등록 후 3년 미실시, 최대 3년)
  - 최소실시료 (고시 제9조: 300만 원, 60일 — 수의계약·갱신에도 적용)
  - 갱신 신청 (고시 제10조 제4항: 만료일 30일 전)
  - 처분보상금 (고시 제11조 제2항: 직접비용 공제 후 100분의 50)
  - 연차료 회복 (특허법 제81조의3 제3항: 추가납부기간 만료일부터 3개월, 특허료 2배)
  - PCT (특허법 제201조: 2년 7개월)
  - 비과세 한도 (연 700만 원)
  - 승계 통지 기한 (4개월)
  - 실시료 예정가격 산식·기본율 3%(2~4%)·단위당 실시료 (시행규칙 제11조), 계약기간 3년과 연장 사유 (제6조), 입찰 공고 30일 전 (제7조)
  - 수탁기관 분기 실적보고 다음 달 15일 (고시 제18조), 변경 30일 내 통보 (제15조 제2항), 기여보상금 100분의 15 범위 (영 제18조)
  - 심결 취소소송 30일 불변기간 (특허법 제186조 제3항·제4항)
- **바로잡음**:
  - 중소기업 우대는 '2%p 인하'가 아니라 **'기본율을 2%로 낮추어 적용할 수 있다'** (고시 제7조)
  - 전용실시 갱신 사유는 2개가 아니라 **5개** (고시 제10조 제1항)
  - 특허법 제14조의 '근로자의 날'은 2025.11.11. 개정으로 **'노동절'**
  - 발명진흥법 제13조(2024.2.6. 개정): 예약승계 규정이 있으면 **완성 때 자동 승계**되고, 승계하지 않을 때만 4개월 내 통지
- **원문끼리 표현이 달라 남겨 둔 쟁점** (YAML `verification_notes`, 도구 출력에 표시):
  - 처분보상금 비율: 규정 제17조 제1항은 "처분수입금의 100분의 50 **이상**의 범위에서 고시하는 바에 따라", 고시 제11조 제2항은 "직접비용을 **공제한** 금액의 100분의 50". 도구는 고시 산식을 적용합니다.
  - 무상실시 근거: 고시 제3조 제2항은 근거를 영 제10조 제2항 **제1호**로 들지만, 현행 제1호는 '농업인·어업인의 소득 증대'입니다 (2024.11.12. 영 개정).
  - 보상금 감액: 고시 별표 1(보상금등의 감액기준)은 첨부 서식이라 수치로 넣지 않았습니다. 등록·처분보상금 결과에 확인 항목으로 표시됩니다.
- **바뀐 동작**: 국유특허 프로파일의 계약조건 초안은 더 이상 기업 규모별 참고 요율을 쓰지 않고 시행규칙 제11조 산식(점유율 `share_rate` × 기본율 3%)을 씁니다. 규모별 요율은 대학·민간 프로파일에만 남습니다.

## 캐시

- 조회 결과는 SQLite에 저장합니다. 기본 경로는 `~/.cache/patent-law-mcp/cache.sqlite3`입니다.
- 보관 기간은 특허 원문 7일, 검색·법령 24시간입니다.
- 성공한 조회만 저장하며, `refresh=True`를 주면 캐시를 무시합니다.
- 설정: `PATENT_LAW_MCP_CACHE`(경로 또는 `off`), `PATENT_LAW_MCP_CACHE_TTL_HOURS`

## 업스트림 동기화

요약 근거 확인·용도 근거·TRL 정합성 규칙은 [patent-summary-wizard](https://github.com/kimjs3176-prog/patent-summary-wizard)에서, 공보 특허권자 추출과 영상 시그니처 규칙은 [patent-video-skill](https://github.com/kimjs3176-prog/patent-video-skill)에서 옮겨 왔습니다.
- 매일 GitHub Actions가 변경을 확인해 `upstream-sync` 이슈를 엽니다.
- 반영 절차는 [`upstream/README.md`](upstream/README.md)를 보십시오.

## 개발

```bash
uv sync
```

```bash
uv run pytest -q
```

```bash
python3 scripts/sync_upstream.py --check
```

```bash
uv run python scripts/scenario_check.py
```

`scenario_check.py`는 서버를 별도 프로세스로 띄워 MCP 프로토콜(stdio·HTTP)로 36개 실사용 시나리오를 점검합니다. 네트워크가 없으면 `--offline`을 붙이십시오.

---

> ⚖️ **면책** 이 서버는 변리사의 출원 대리, 명세서 작성, 심사 대응, 침해 감정을 대체하지 않습니다. 계약·보상·기한 계산 결과는 실무 검토용 초안이며, 최종 판단은 법령·고시 원문과 등록원부, 전문가 검토로 확인하십시오.
