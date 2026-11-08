"""업스트림 저장소 로직의 Python 포팅

- patent-summary-wizard (kimjs3176-prog/patent-summary-wizard)
  - summary_grounding.py   ← supabase/functions/summarize-patent/summaryGrounding.ts
  - application_grounding.py ← supabase/functions/summarize-patent/applicationGrounding.ts
  - trl_consistency.py     ← supabase/functions/analyze-commercialization/trlConsistency.ts, src/lib/trlPresentation.ts
- patent-video-skill (kimjs3176-prog/patent-video-skill)
  - gazette_holders.py     ← scripts/kipris.py (holders_from_text)
  - video_signature.py     ← references/CONTENT_SPEC.md (시그니처 유형 선택 규칙)

동기화 기준 커밋과 파일 해시는 저장소 루트의 upstream/manifest.json에 있고,
scripts/sync_upstream.py --check 로 업스트림 변경을 확인합니다. 포팅 규칙은 upstream/README.md 참고.
"""
