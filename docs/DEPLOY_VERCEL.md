# Vercel 배포 — 커넥터 주소 만들기

국가직무발명특허권등 업무 보조 도구를 Vercel에 올려 Claude 커넥터용 주소(`https://<프로젝트>.vercel.app/mcp`)를 만드는 방법입니다.
사용자 안내(커넥터 등록)는 [README](../README.md)를 보십시오.

## 0. 요금제 — 비용이 나가지 않게

| 요금제 | 비용 | 사용량을 넘으면 |
|:---|:---|:---|
| **Hobby (권장)** | 무료 | 요금이 청구되지 않고, 넘긴 기능이 30일이 지날 때까지 멈춥니다 |
| Pro | 월 기본요금 + 초과 사용량 | 지출 한도(Spend Management)를 걸어야 추가 요금을 막을 수 있습니다 (아래 5번) |

- 비용이 전혀 나가지 않게 하려면 **Hobby 팀(개인 계정)에서 배포**하고 결제 수단을 등록하지 마십시오. 유료 팀에 실수로 배포하지 않도록, Import 화면 위쪽의 팀 선택이 Hobby인지 확인하십시오.
- Hobby 월 포함량(2026-11 기준): 함수 호출 100만 회, Active CPU 4시간, 메모리 360GB-시간, 데이터 전송 100GB. 이 서버는 요청 하나에 CPU를 수십~수백 ms 쓰므로 업무용으로는 여유가 큽니다.
- Vercel 약관에서 Hobby의 상업적 이용 제한 여부를 확인하십시오 (기관 업무용이면 해당될 수 있습니다). 이 문서는 [약관](https://vercel.com/legal/terms) 원문을 확인하지 않았습니다.

## 1. 프로젝트 만들기

1. [vercel.com](https://vercel.com)에 GitHub 계정으로 로그인합니다.
2. **Add New… → Project**에서 `kimjs3176-prog/patent-law-mcp` 저장소를 **Import**합니다.
3. Framework Preset은 그대로 둡니다. 저장소 맨 위의 `app.py`를 Vercel이 Python 앱으로 인식합니다.
4. **Deploy**를 누르기 전에 같은 화면의 **Environment Variables**를 펼쳐 아래 2번의 값을 넣습니다. 나중에 넣어도 되지만, 그때는 다시 배포해야 반영됩니다.

## 2. 환경변수

| 이름 | 필요 여부 | 값 | 설명 |
|:---|:---|:---|:---|
| `PATENT_LAW_MCP_ALLOW_ANONYMOUS` | **필수 (공개 운영)** | `1` | 누구나 로그인·토큰 없이 쓸 수 있게 공개합니다. 도구는 모두 읽기 전용이라 서버 데이터를 바꿀 수 없습니다 |
| `PATENT_LAW_MCP_TOKEN` | 넣지 않음 | — | 넣으면 공개 대신 토큰 방식이 됩니다 (아래 "토큰 방식으로 바꾸려면") |
| `KIPRIS_API_KEY` | **넣지 않음 (권장)** | — | 공개 운영에서는 모든 사용자가 한 키의 호출 한도를 나눠 써 금방 막힙니다. 키가 없으면 검색은 Google Patents로 하고, 공식 KIPRIS 검색이 필요한 사용자는 커넥터 요청 헤더 `x-api-key`로 본인 키를 씁니다 |
| `LAW_OC` | 선택 | 국가법령정보 공동활용 OC | 법령 검색·조문 조회 (`search_laws`, `get_law_article`). 운영 배포(patent-law-mcp.vercel.app)에서 2026-11-22 동작 확인. Open API 신청 정보의 IP·도메인 등록 조건에 따라 막히면 이 값을 지우십시오. 원문 개정 점검(`check_legal_source_updates`)은 이 값 없이 동작합니다 |
| `PATENT_LAW_MCP_PROFILE` | 선택 | `national` (기본) | `public_research`(대학·출연연), `private_company`(민간 기업) |
| `PATENT_LAW_MCP_CACHE` | 설정 불필요 | — | Vercel에서는 자동으로 `/tmp/patent-law-mcp/cache.sqlite3`를 씁니다 (`off`로 끌 수 있음) |

`PATENT_LAW_MCP_ALLOW_ANONYMOUS`도 `PATENT_LAW_MCP_TOKEN`도 넣지 않으면 서버는 공개로 넘어가지 않고 `/mcp` 요청을 503(설정 필요)으로 거부합니다. 공개는 이 값으로 명시적으로 켜야 합니다.

> [!WARNING]
> **서버에 `KIPRIS_API_KEY`를 넣으면 모든 사용자가 그 키의 호출 한도를 함께 씁니다.** 그래서 기본 구성은 서버 키 없이 운영하는 것입니다: 특허 키워드 검색은 Google Patents(비공식)로, 공식 KIPRIS 검색·출원번호 조회는 사용자가 커넥터 요청 헤더 `x-api-key`로 보낸 본인 키로 합니다 (그 요청에만 쓰고 저장하지 않음). 그래도 서버 키를 넣는다면 아래 5번의 요청 수 제한을 꼭 거십시오.

<details>
<summary><b>토큰 방식으로 바꾸려면 (특정 사용자만 쓰게 할 때)</b></summary>

1. `PATENT_LAW_MCP_ALLOW_ANONYMOUS`를 지우고 `PATENT_LAW_MCP_TOKEN`에 긴 임의 문자열을 넣은 뒤 다시 배포합니다.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

2. 사용자는 커넥터 등록 때 **요청 헤더**에 이름 `authorization`, 값 `Bearer <토큰>`을 넣어야 합니다. 요청 헤더 항목은 베타라 계정에 따라 보이지 않을 수 있고, 그 계정은 연결할 수 없습니다.

</details>

### 대시보드에서 넣기·고치기

1. 프로젝트 → **Settings → Environment Variables**
2. **Key**에 이름, **Value**에 값을 넣고, 환경은 **Production**을 선택한 뒤 **Save**
3. **Deployments** 탭 → 가장 최근 배포의 **⋯ → Redeploy**

> [!IMPORTANT]
> 환경변수는 **그 뒤에 만든 배포에만** 적용됩니다. 값을 넣거나 바꾼 뒤에는 반드시 다시 배포(Redeploy)하십시오.

### CLI로 넣기 (선택)

```bash
vercel env add PATENT_LAW_MCP_ALLOW_ANONYMOUS production
```

```bash
vercel --prod
```

## 3. 주소 확인

1. 프로젝트 첫 화면의 **Domains**에 보이는 주소(`<프로젝트>.vercel.app`)를 엽니다. 배포마다 생기는 긴 주소(`…-<해시>-….vercel.app`)가 아니라 이 **고정 주소**를 쓰십시오.
2. 브라우저에서 `https://<프로젝트>.vercel.app/` 을 열면 **주요 기능·사용 안내 페이지**가 나옵니다. 위쪽 상태 표시(운영 중·공개, 도구 수, 원문 대조일, 법령 조회·KIPRIS 검색 가능 여부)로 설정을 확인할 수 있습니다.
3. 설정 상태를 JSON으로 보려면 `https://<프로젝트>.vercel.app/status` 를 엽니다 (토큰·키 값은 표시하지 않음).

```json
{"name": "국가직무발명특허권등 업무 보조 도구", "mcp_endpoint": "/mcp", "auth": "없음 (공개)", "kipris_api_key": false, "law_oc": true, "profile": "national", "tool_count": 26, "source_text_verified_on": "2026-11-22"}
```

4. 커넥터 주소는 끝에 `/mcp`를 붙인 **`https://<프로젝트>.vercel.app/mcp`** 입니다. 이 주소를 사용자에게 알려 주고, [README](../README.md)의 커넥터 등록 절차를 안내하십시오.

## 4. 사용량을 줄이는 저장소 설정 (`vercel.json`, 자동 적용)

| 설정 | 값 | 효과 |
|:---|:---|:---|
| `regions` | `icn1` (서울) | 함수를 한 지역(서울)에서만 실행. 국가법령정보센터·KIPRIS와 가까워 응답 대기 시간이 줄어듭니다 |
| `ignoreCommand` | `main` 외 브랜치는 빌드 건너뜀 | 작업 브랜치에 푸시할 때마다 미리보기 배포가 생기지 않습니다 (CLI 배포는 그대로 빌드) |
| `functions.maxDuration` | 60초 | 요청 하나가 60초를 넘으면 끊습니다. 근거 법령 8개를 받아 대조하는 원문 점검 도구가 30초 안팎이라 여유를 둔 값입니다 |
| `functions.excludeFiles` | 테스트·스크립트·문서 제외 | 함수 묶음 크기를 줄입니다 |

## 5. 비용 안전 설정 (대시보드, 직접 설정)

공개 운영이라 주소를 아는 누구나 요청할 수 있습니다. Hobby는 사용량을 넘어도 요금이 나가지 않지만, 한도를 다 쓰면 30일간 모든 사용자가 쓸 수 없게 되므로 **요청 수 제한을 꼭 거십시오.**

**요청 수 제한 (필수, Hobby에서도 1개 규칙 무료)** — 한 사람이 과도하게 요청해 월 사용량을 소진하는 것을 막습니다.
1. 프로젝트 → **Firewall** → **Rules**(또는 **Configure**) → **Add Rule**
2. 조건: Request Path가 `/mcp`로 시작
3. 동작: **Rate Limit** — 기준 IP, 고정 창 1분, 60회 (Claude 대화 한 번에 도구 호출이 보통 몇 회라 일반 사용에는 충분합니다), 초과 시 **429 Too Many Requests**
4. **Save** 후 **Publish**

**Pro 요금제를 쓴다면 지출 한도**
1. 팀 **Settings → Billing → Spend Management**
2. **Add Budget** → **Team** 선택 → 금액(USD) 입력
3. **Pause production deployments**를 켭니다 — 한도에 닿으면 운영 배포가 멈추고(503), 추가 요금이 쌓이지 않습니다
4. 확인 주기 때문에 한도 도달 후 몇 분 늦게 멈출 수 있습니다. 50%·75%·100%에서 메일 알림이 옵니다

**사용량 확인** — 팀 **Usage** 탭에서 함수 호출 수·Active CPU를 월 포함량과 비교해 볼 수 있습니다.

## 6. 문제 해결

| 증상 | 원인과 조치 |
|:---|:---|
| `/`를 열면 안내 페이지 대신 Vercel 로그인 화면이 나옴 | Deployment Protection이 켜져 있습니다. 고정 주소(`<프로젝트>.vercel.app`)를 쓰거나, **Settings → Deployment Protection**에서 Production 보호를 끄십시오. 커넥터 요청은 Anthropic 서버에서 오므로 Vercel 로그인을 통과할 수 없습니다 |
| `/status`의 `"auth": "미설정 …"` | 공개 설정이 반영되지 않았습니다. `PATENT_LAW_MCP_ALLOW_ANONYMOUS=1` 확인 후 **Redeploy** |
| 커넥터 연결 시 401 | `PATENT_LAW_MCP_TOKEN`이 남아 있어 토큰 방식으로 동작 중입니다. 지우고 다시 배포하십시오 |
| 커넥터 연결 시 503 | `PATENT_LAW_MCP_ALLOW_ANONYMOUS=1`이 반영되지 않았습니다. 환경변수 확인 후 **Redeploy** |
| 404 | 주소 끝의 `/mcp`가 빠졌는지 확인 |
| 배포 실패 | Vercel 배포 로그(Build Logs)를 확인. Python 3.12(Vercel 기본)에서 `pyproject.toml`·`uv.lock`으로 의존성을 설치합니다 |

## 참고

- 서버는 요청마다 상태 없이(stateless) MCP 요청을 처리하고 JSON으로 응답합니다. 서버리스 함수 사이에 세션을 유지하지 않습니다.
- 로컬 실행·Docker 배포·개발 방법은 [OPERATIONS.md](OPERATIONS.md)를 보십시오.
