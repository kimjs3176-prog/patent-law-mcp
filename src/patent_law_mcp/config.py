"""Patent Law MCP 환경설정

KIPRIS Plus 인증키는 도구 인자가 아니라 환경변수(KIPRIS_API_KEY)로 받습니다.
인자로 받으면 키가 대화 기록에 남기 때문입니다.
원격(HTTP) 배포에서는 사용자가 커넥터 요청 헤더(x-api-key)로 보낸 본인 키를 그 요청에만 씁니다 (request_kipris_key).
"""

import os
from contextvars import ContextVar
from dataclasses import dataclass

# 원격 배포에서 요청마다 사용자가 보낸 KIPRIS 키 (vercel_app이 요청 처리 동안만 설정, 저장·기록하지 않음)
request_kipris_key: ContextVar[str] = ContextVar("request_kipris_key", default="")


@dataclass(frozen=True)
class Settings:
    request_timeout_seconds: float = 15.0

    @property
    def kipris_api_key(self) -> str:
        """사용자가 요청 헤더로 보낸 키를 먼저, 없으면 호출 시점의 환경변수를 읽습니다."""
        return request_kipris_key.get().strip() or os.environ.get("KIPRIS_API_KEY", "").strip()


settings = Settings()
