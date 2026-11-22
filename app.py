"""Vercel 진입점 — Vercel은 저장소 맨 위 app.py의 `app`을 ASGI 앱으로 실행합니다.

로컬 실행·Claude Desktop 연결에는 쓰지 않습니다 (patent-law-mcp 명령 사용).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # src 레이아웃 패키지를 설치 없이도 찾도록

from patent_law_mcp.vercel_app import app  # noqa: E402,F401
