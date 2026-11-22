#!/usr/bin/env python3
"""국가법령정보센터 원문 정기 대조 스크립트

  uv run python scripts/check_law_sources.py --check [--report law_drift.md] [--json]
      policies/legal_sources.yaml의 감시 조문을 현재 시행 원문과 비교합니다.
      종료 코드: 0 = 변경 없음, 1 = 변경 있음(원문 검토 필요), 2 = 점검 오류
  uv run python scripts/check_law_sources.py --update [--only ID ...]
      원문 검토와 정책 YAML 반영을 마친 뒤 실행: 기준선(policies/legal_baseline.json)을 현재 원문으로 갱신합니다.
"""

import argparse
import json
import sys

from patent_law_mcp.legal_sources import LawSourceError, check_sources, render_report, update_baseline


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--update", action="store_true")
    ap.add_argument("--only", nargs="*", help="legal_sources.yaml의 id (예: notice enforcement_rule)")
    ap.add_argument("--report", help="마크다운 보고서 저장 경로")
    ap.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = ap.parse_args()

    if args.update:
        try:
            r = update_baseline(args.only)
        except (LawSourceError, OSError) as e:
            print(f"기준선 갱신 실패: {e}", file=sys.stderr)
            return 2
        print(f"기준선 갱신 ({r['verified_on']}): {', '.join(r['updated'])}")
        return 0

    result = check_sources(args.only)
    report = render_report(result)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else report)
    if result["errors"]:
        return 2
    return 1 if result["changed"] else 0


if __name__ == "__main__":
    sys.exit(main())
