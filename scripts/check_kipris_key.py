"""KIPRIS Plus 인증키(KIPRIS_API_KEY)가 이 서버에서 동작하는지 확인합니다.

    KIPRIS_API_KEY=발급받은키 uv run python scripts/check_kipris_key.py

키 값은 화면에 출력하지 않습니다. 확인용으로 공개된 국유특허 1건
(출원 10-2010-0123901, 굳지 않는 떡의 제조방법)의 서지를 조회합니다.
"""

from __future__ import annotations

import sys

from patent_law_mcp.config import settings
from patent_law_mcp.tools.kipris_connector import fetch_from_kipris_api

SAMPLE_APPLICATION = "1020100123901"


def main() -> int:
    key = settings.kipris_api_key
    if not key:
        print("✗ KIPRIS_API_KEY 환경변수가 비어 있습니다. docs/KIPRIS_API_KEY.md를 참고해 설정하십시오.")
        return 2
    print(f"· 인증키 감지 ({len(key)}자, 값은 표시하지 않음)")
    data, msg = fetch_from_kipris_api(SAMPLE_APPLICATION, key)
    if not data:
        print(f"✗ 조회 실패: {msg}")
        print("  - 서비스 신청 승인 여부(특허·실용 공개·등록공보), 키 복사 시 공백·줄바꿈, 월 호출 한도를 확인하십시오.")
        return 1
    print(f"✓ 조회 성공: {data.get('title')} (출원 {data.get('application_number')}, 등록 {data.get('register_number') or '-'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
