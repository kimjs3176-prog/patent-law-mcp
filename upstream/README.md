# 업스트림 동기화

patent-law-mcp의 일부 판정 규칙은 아래 저장소의 로직을 Python으로 옮긴 것입니다.

| 업스트림 | 파일 | MCP 모듈 |
|:---|:---|:---|
| patent-summary-wizard | `summarize-patent/summaryGrounding.ts` | `upstream/summary_grounding.py` → `ground_summary_figures` |
| patent-video-skill | `scripts/kipris.py` | `upstream/gazette_holders.py` → `parse_raw_patent_text`, `tools/kipris_connector.py` (KIPRIS 응답 경로) |

특허 분석(용도 근거·TRL)·영상 시그니처 규칙은 2026-11-22 도구 정리로 MCP에서 삭제해 더 이상 포팅하지 않습니다 (`manifest.json`의 `ignored`).

## 어떻게 맞춰 두나

- `manifest.json`: 추적 파일 목록, 마지막으로 맞춘 커밋, 파일 해시, 포팅하지 않는 파일(`ignored`)과 사유
- `snapshots/`: 마지막으로 맞춘 업스트림 파일 사본 (다음 변경의 diff 기준)
- `scripts/sync_upstream.py --check`: 최신 업스트림과 비교 (0 = 같음, 1 = 반영 필요, 2 = 오류)
- `.github/workflows/upstream-sync.yml`: 매일 점검해 변경이 있으면 `upstream-sync` 라벨 이슈를 열거나 갱신

## 변경이 생기면

1. 이슈(또는 `python3 scripts/sync_upstream.py --check`)의 diff를 보고 반영 대상 모듈을 고칩니다.
   정규식·판정 순서·대체 문구는 원본과 같게 유지합니다 (JS `\d` → `[0-9]`, JS `$`(m 플래그 없음) → `\Z`).
2. 업스트림 테스트가 바뀌었으면 `tests/test_upstream_parity.py`에 같은 케이스를 옮깁니다.
3. `uv run pytest -q` 통과 후 `python3 scripts/sync_upstream.py --update`로 기준선을 갱신하고 커밋합니다.
4. 새 파일이 감지되면 포팅 대상이면 `files`에, 아니면 `ignored`에 사유와 함께 추가합니다.
