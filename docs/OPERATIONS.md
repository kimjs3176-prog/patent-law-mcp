# 운영·개발 안내 — 국가직무발명특허권등 업무 보조 도구 (`patent-law-mcp`)

사용자용 안내(커넥터 등록·사용)는 [README](../README.md), Vercel 배포는 [DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)를 보십시오.
이 문서는 서버를 직접 실행·배포·수정하는 운영자와 개발자를 위한 것입니다.

## 🧭 원칙

| 원칙 | 하는 일 |
|:---|:---|
| 모르면 모른다고 답함 | 조회 실패·원문에 없는 값은 `found=False`·`warnings`·`미확인`으로 반환. 특허번호·출원인·수치를 지어내지 않음 |
| 받은 문서는 번호로 검증 | Google Patents·KIPRIS 문서의 출원·등록·공개번호가 요청과 다르면 버림 |
| 기준값은 한 파일에서 관리 | 최소실시료·기본율·보상 비율·감액기준과 근거 조항은 `policies/*.yaml`. 고치면 다음 호출부터 반영 |
| 원문과 어긋나면 표시 | 법령끼리 표현이 다른 항목은 해당 도구 결과에만 `unverified_items`로 표시 |
| 원문을 정기 대조 | 매주 국가법령정보센터 현재 원문과 기준선을 비교하고, 결과마다 원문 대조일(`source_text_verified_on`)을 표시 |

## 로컬 실행 (Claude Desktop · Claude Code, stdio)

**Claude Desktop (로컬, stdio)** — `claude_desktop_config.json`에 추가합니다.

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

인증키 없이도 국유특허 업무 도구(계산·판정·안내)는 모두 동작합니다.

> [!NOTE]
> 설정 키·명령어·패키지명은 영문 식별자 `patent-law-mcp`를 씁니다. Claude 도구 이름(`mcp__patent-law-mcp__도구명`)에는 영문·숫자·`-`·`_`만 쓸 수 있어 한글 표시 이름을 식별자로 쓰지 않습니다.

<details>
<summary><b>원격(HTTP)·Docker 배포</b></summary>

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
- 요청마다 독립적으로 처리합니다(stateless). 사용자가 `x-api-key` 헤더로 보낸 본인 KIPRIS 키는 그 요청에만 씁니다.
- 토큰 없이 127.0.0.1 이외 주소에 바인딩하면 서버가 시작을 거부합니다.

</details>

### 인증키 (모두 선택)

| 환경변수 | 쓰는 도구 | 발급 |
|:---|:---|:---|
| `KIPRIS_API_KEY` | 특허 검색, 출원번호 조회, KIPRIS 공식 서지 | plus.kipris.or.kr (특허·실용 공개·등록공보 서비스) |
| `LAW_OC` | 법령 검색·조문 조회 | open.law.go.kr Open API 신청 (무료). **호출 서버의 IP·도메인 등록 필요** |

키가 없으면 해당 도구는 발급 방법을 안내하고, 등록·공개번호 조회는 Google Patents 공개 웹으로 동작합니다.

## 🏷️ 기관 유형별 프로파일

| 프로파일 | 파일 | 적용 |
|:---|:---|:---|
| `national` **(기본)** | `policies/kipo_notice_rules.yaml` | 국유특허 — 국가공무원 등 직무발명 규정·시행규칙, 지식재산처고시 제2025-4호 |
| `public_research` | `policies/public_research.yaml` | 대학 산학협력단·정부출연연구기관 — 기술이전법·발명진흥법·기관 규정 |
| `private_company` | `policies/private_company.yaml` | 민간 기업 — 발명진흥법·사내 보상규정 |

| 설정 | 기본값 | 설명 |
|:---|:---|:---|
| `PATENT_LAW_MCP_PROFILE` | `national` | 기본 프로파일. 도구마다 `profile` 인자로 호출 단위 선택도 가능 |
| `PATENT_LAW_MCP_POLICY_FILE` | — | 다른 정책 YAML 경로 |
| `PATENT_LAW_MCP_CACHE` | `~/.cache/patent-law-mcp/cache.sqlite3` | 조회 캐시 경로, `off`면 끔 (특허 원문 7일, 검색·법령 24시간) |
| `PATENT_LAW_MCP_CACHE_TTL_HOURS` | `168` | 캐시 기본 보관 시간(시간 단위) |

기관·사내 규정 값(보상 비율 등)은 비워 두었습니다(`null`). 기관 값을 YAML에 넣거나 호출할 때 `payout_ratio`로 주십시오. 국유특허 계약조건 초안은 기업 규모별 참고 요율 대신 시행규칙 제11조 산식(`share_rate` × 기본율 3%)을 씁니다. 캐시는 성공한 조회만 저장하며, `refresh=True`를 주면 무시합니다.

<a id="verification"></a>

## 📚 원문 대조 결과

국가법령정보센터 원문과 2026-11-08·2026-11-22에 대조했습니다.

| 대상 | 확인한 원문 |
|:---|:---|
| 고시 | 국가공무원 등 직무발명의 처분·관리 및 보상 등에 관한 업무 운영요령 [지식재산처고시 제2025-4호, 2025.10.30. 시행] 제3\~11조·제13\~24조·제26조, 별표 1 |
| 규정 | 같은 규정 [대통령령 제35809호, 2025.10.01. 시행] 제2·5·8·10·11·12·14·16·17·18·21조 |
| 시행규칙 | 같은 규정 시행규칙 [총리령 제2054호, 2025.10.01. 시행] 제2\~13조 |
| 법률 | 특허법 [법률 제21134호, 2025.11.11. 시행] 제14·30·54·55·59·79·81·81조의3·88·186·201조, 실용신안법 제22조, 발명진흥법 제12·13조, 같은 법 시행령 제7조, 소득세법 시행령 제17조의3 |

> [!WARNING]
> **원문끼리 표현이 달라 남겨 둔 쟁점** — 해당 도구 결과의 `unverified_items`에 표시됩니다.
> - **처분보상금 비율**: 규정 제17조 제1항은 "처분수입금의 100분의 50 **이상**의 범위에서 고시하는 바에 따라", 고시 제11조 제2항은 "직접비용을 **공제한** 금액의 100분의 50". 도구는 고시 산식을 적용합니다.
> - **무상실시 근거**: 고시 제3조 제2항은 근거를 영 제10조 제2항 **제1호**로 들지만, 현행 제1호는 '농업인·어업인의 소득 증대'입니다 (2024.11.12. 영 개정).
> - **보상금 감액**: 고시 별표 1은 비밀유지 위반 시 '기관포상금(영 제18조 제1항)'도 감액 대상으로 적지만, 현행 영 제18조는 수탁기관 '기여보상금'입니다 (기관포상금은 2024.11.12. 영 개정으로 폐지).

### 🗓️ 원문 정기 대조

기준값이 기대는 조문을 [`legal_sources.yaml`](../src/patent_law_mcp/policies/legal_sources.yaml)에 적어 두고, 국가법령정보센터 현재 시행 원문과 기준선([`legal_baseline.json`](../src/patent_law_mcp/policies/legal_baseline.json))을 비교합니다.

| 감지하는 변화 | 예 |
|:---|:---|
| 버전 변경 | 규정·고시가 새로 공포·시행됨 (타법개정 포함) |
| 감시 조문 본문 변경·삭제 | 시행규칙 제11조 문장이 바뀌면 기준선과의 차이(diff)를 보고 |
| 기준값 문구 누락 | 고시 제9조에서 '300만원'이 사라지면 `exclusive_licensing.minimum_royalty_amount`부터 확인하라고 안내 |

- **자동 점검**: GitHub Actions가 매주 월요일 05:43(KST)에 실행하고, 바뀐 것이 있으면 `law-drift` 이슈를 열거나 갱신합니다. 화면 구조 변경 등으로 점검이 실패하면 작업이 실패로 표시됩니다.
- **답변할 때**: 모든 도구 결과에 원문 대조일(`legal_audit_basis.source_text_verified_on`)이 붙고, `check_legal_source_updates` 도구로 그 이후 개정 여부를 바로 확인할 수 있습니다.
- **반영 절차**: 원문 확인 → 정책 YAML·테스트 수정 → 기준선 갱신 → PR.

```bash
uv run python scripts/check_law_sources.py --check
```

```bash
uv run python scripts/check_law_sources.py --update
```

`--check`의 종료 코드는 0(변경 없음)·1(검토 필요)·2(점검 오류)입니다. 시행 예정(공포 후 미시행) 개정은 시행일이 되어야 감지됩니다.

<details>
<summary><b>원문과 일치를 확인한 수치·기한</b></summary>

| 항목 | 값 | 근거 |
|:---|:---|:---|
| 미활용 특허 무상실시 | 등록 후 3년 미실시, 최대 3년 | 고시 제3조 |
| 중소기업 재실시 기본율 | 2%로 낮추어 적용 가능 | 고시 제7조 |
| 전용실시 최소실시료 | 300만 원, 계약일부터 60일 (수의계약·갱신에도 적용) | 고시 제9조 |
| 전용실시 갱신 | 5개 사유, 만료일 30일 전 신청 | 고시 제10조 |
| 처분보상금 | 직접비용 공제 후 100분의 50 | 고시 제11조 제2항 |
| 보상금 감액 | 통지 전 자기 명의 출원·이전 → 전액 미지급 / 미신고 출원·이전 → 전액 미지급 또는 50% / 비밀유지 위반 → 50% | 고시 별표 1 |
| 수탁기관 보고 | 분기 실적보고 다음 달 15일, 변경 30일 내 통보 | 고시 제18조·제15조 |
| 등록보상금 | 특허 50만·실용신안 30만·디자인 20만 원 범위, 1회 | 영 제16조 |
| 기여보상금 | 처분수입금의 100분의 15 범위 | 영 제18조 |
| 실시료 예정가격 | 기본율 3% (2\~4%), 단위당 실시료 가능 | 시행규칙 제11조 |
| 계약기간 | 3년 이내 (준비기간 1년 이상·존속기간 4년 내 만료 시 연장) | 시행규칙 제6조 |
| 입찰 공고 | 입찰일 30일 전 | 시행규칙 제7조 |
| 심결 취소소송 | 등본 송달일부터 30일 (불변기간) | 특허법 제186조 |
| 연차료 회복 | 추가납부기간 만료일부터 3개월, 특허료 2배 | 특허법 제81조의3 |
| PCT 국내단계 | 2년 7개월 | 특허법 제201조 |
| 직무발명 승계 | 예약승계 규정 있으면 완성 때 승계, 승계하지 않을 때만 4개월 내 통지 | 발명진흥법 제13조 |
| 직무발명보상금 비과세 | 연 700만 원, 특수관계인 제외 | 소득세법 시행령 제17조의3 |

</details>

## 🔁 업스트림 동기화

요약 효과 수치 근거 확인과 기술사업화 평가(체크리스트·V-RAY·TRL 정합성) 규칙은 [patent-summary-wizard](https://github.com/kimjs3176-prog/patent-summary-wizard)에서, 공보 특허권자 추출 규칙은 [patent-video-skill](https://github.com/kimjs3176-prog/patent-video-skill)에서 옮겨 왔습니다. 매일 GitHub Actions가 변경을 확인해 `upstream-sync` 이슈를 열며, 반영 절차는 [`upstream/README.md`](../upstream/README.md)에 있습니다.

<a id="development"></a>

## 🛠️ 개발

```bash
uv sync
```

```bash
uv run pytest -q
```

```bash
uv run python scripts/scenario_check.py
```

```bash
python3 scripts/sync_upstream.py --check
```

`scenario_check.py`는 서버를 별도 프로세스로 띄워 MCP 프로토콜(stdio·HTTP)로 50개 실사용 시나리오를 점검합니다. 네트워크가 없으면 `--offline`을 붙이십시오.
