# KIPRIS Plus 인증키 발급·설정 안내

`patent-law-mcp`는 KIPRIS Plus 인증키 없이도 동작합니다. 다만 키가 없으면 아래 기능이 막히거나 대체 경로로 동작합니다.

| 기능 | 키 없음 | 키 있음 |
|:---|:---|:---|
| `search_patents` (키워드·출원인 검색) | 사용 불가 | KIPRIS 공식 검색 |
| `fetch_patent_smart` — 출원번호(10-YYYY-NNNNNNN) 조회 | 사용 불가 | KIPRIS 공식 서지·초록·청구항 |
| `fetch_patent_smart` — 등록·공개번호 조회 | Google Patents 공개 웹 (법적 상태는 Google 추정값) | Google Patents로 출원번호를 찾은 뒤 KIPRIS 공식 서지로 교체 |
| `check_patent_rights_status`, `inspect_and_summarize_by_appno` | 위와 같음 | KIPRIS의 등록 상태(`registerStatus`) 반영 |

## 1. 인증키 발급

1. [KIPRIS Plus](https://plus.kipris.or.kr)에 회원가입하고 로그인합니다.
2. Open API 서비스 목록에서 **특허·실용신안 공개·등록공보** 서비스(`patUtiModInfoSearchSevice`)를 찾아 이용을 신청합니다.
   - 이 서버는 이 서비스의 `getWordSearch`, `getAdvancedSearch`, `getBibliographyDetailInfoSearch` 세 오퍼레이션만 씁니다.
   - 다른 서비스(디자인·상표·심판 등)는 필요하지 않습니다.
3. 승인되면 마이페이지에서 **인증키(ServiceKey)** 를 확인합니다. 승인까지 시간이 걸릴 수 있습니다.
4. 무료 이용 한도, 유료 전환 조건, 승인 절차는 KIPRIS Plus 공지를 따릅니다. 이 문서에는 바뀔 수 있는 수치를 적지 않았습니다.

> 인증키는 비밀번호처럼 다루십시오. 저장소·이슈·채팅에 붙여넣지 말고, 아래처럼 **환경변수**로만 넣으십시오.
> 이 서버는 키를 도구 인자로 받지 않으며, 서버 로그에도 남기지 않습니다(`net.py`).

## 2. MCP 클라이언트에 설정

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "patent-law-mcp": {
      "command": "uv",
      "args": ["--directory", "/절대경로/patent-law-mcp", "run", "patent-law-mcp"],
      "env": {
        "KIPRIS_API_KEY": "발급받은-인증키"
      }
    }
  }
}
```

저장한 뒤 Claude Desktop을 완전히 종료했다가 다시 실행합니다.

### Claude Code (CLI)

```bash
claude mcp add patent-law-mcp -e KIPRIS_API_KEY=발급받은-인증키 -- uv --directory /절대경로/patent-law-mcp run patent-law-mcp
```

### 원격(HTTP)·Docker 배포

```bash
docker run -p 8000:8000 -e PATENT_LAW_MCP_TOKEN=긴-임의-문자열 -e KIPRIS_API_KEY=발급받은-인증키 patent-law-mcp --allowed-host mcp.example.org
```

키를 명령줄에 직접 쓰면 셸 기록에 남습니다. 운영 환경에서는 `--env-file` 이나 배포 플랫폼의 비밀값(Secret) 기능을 쓰십시오.

### Claude Code 클라우드 환경

환경 설정의 **환경변수(Environment variables)** 에 `KIPRIS_API_KEY=발급받은-인증키` 를 추가하고 새 세션을 시작합니다.

## 3. 동작 확인

키 값을 출력하지 않는 점검 스크립트가 있습니다. 공개된 국유특허 1건(출원 10-2010-0123901)을 조회합니다.

```bash
KIPRIS_API_KEY=발급받은-인증키 uv run python scripts/check_kipris_key.py
```

- `✓ 조회 성공: 굳지 않는 떡의 제조방법 …` → 정상입니다.
- `✗ KIPRIS_API_KEY 환경변수가 비어 있습니다` → MCP 설정의 `env` 위치, 클라이언트 재시작 여부를 확인하십시오.
- `✗ 조회 실패: …` → 아래 문제 해결을 확인하십시오.

MCP 클라이언트에서는 `search_patents(query="굳지 않는 떡")` 이나 `fetch_patent_smart("10-2010-0123901")` 이 결과를 돌려주면 정상입니다.

## 4. 문제 해결

| 증상 | 확인할 것 |
|:---|:---|
| `KIPRIS: …인증키…` 류의 `resultMsg` | 해당 서비스 신청이 **승인**됐는지, 키를 다른 서비스 것으로 넣지 않았는지 |
| 처음엔 되다가 실패 | 월 호출 한도 초과 여부 (KIPRIS Plus 마이페이지) |
| `KIPRIS 접속 실패 (ConnectError …)` | 서버의 외부 네트워크·프록시 설정, `plus.kipris.or.kr` 허용 여부 |
| `KIPRIS가 다른 출원번호를 반환해 결과를 버렸습니다` | 정상 동작입니다. 요청과 다른 문서는 쓰지 않습니다. 번호를 다시 확인하십시오 |
| 키를 넣었는데 여전히 "설정되지 않음" | 키 앞뒤 공백·줄바꿈, `env` 가 해당 서버 항목 안에 있는지, 클라이언트 재시작 |

결과는 24시간 캐시됩니다. 키를 바꾼 뒤 바로 확인하려면 도구 인자 `refresh=True` 를 주십시오.
