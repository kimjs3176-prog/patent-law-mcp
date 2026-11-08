"""Patent MCP 환경설정 및 기본 상수"""

import os
from pydantic import BaseModel


class Settings(BaseModel):
    # KIPRISPlus API Key (특허정보 개방형 플랫폼)
    kipris_api_key: str = os.getenv("KIPRIS_API_KEY", "")

    # 국가법령정보 공동활용 Open API Key
    law_api_key: str = os.getenv("LAW_API_KEY", "")

    # 기본 캐시 및 타임아웃
    request_timeout_seconds: float = 15.0


settings = Settings()
