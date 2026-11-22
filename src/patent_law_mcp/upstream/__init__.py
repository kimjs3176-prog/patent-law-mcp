"""업스트림 저장소 로직의 Python 포팅

- patent-summary-wizard (kimjs3176-prog/patent-summary-wizard)
  - summary_grounding.py   ← supabase/functions/summarize-patent/summaryGrounding.ts (ground_summary_figures)
- patent-video-skill (kimjs3176-prog/patent-video-skill)
  - gazette_holders.py     ← scripts/kipris.py (holders_from_text, parse_raw_patent_text)

동기화 기준 커밋과 파일 해시는 저장소 루트의 upstream/manifest.json에 있고,
scripts/sync_upstream.py --check 로 업스트림 변경을 확인합니다. 포팅 규칙은 upstream/README.md 참고.
"""
