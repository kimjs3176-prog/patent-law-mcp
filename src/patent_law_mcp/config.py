"""Patent Law MCP 환경설정

KIPRIS Plus 인증키는 도구 인자가 아니라 환경변수(KIPRIS_API_KEY)로만 받습니다.
인자로 받으면 키가 대화 기록에 남기 때문입니다.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float = 15.0

    @property
    def kipris_api_key(self) -> str:
        """호출 시점의 환경변수를 읽습니다 (서버 재시작 없이 키 교체 가능)."""
        return os.environ.get("KIPRIS_API_KEY", "").strip()


settings = Settings()
