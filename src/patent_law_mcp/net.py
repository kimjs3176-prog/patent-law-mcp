"""외부 HTTP 호출 단일 지점 (테스트에서 교체)."""

import logging
from typing import Any

import httpx

# httpx는 INFO 로그에 요청 URL 전체를 남긴다. KIPRIS ServiceKey·법령 OC가 쿼리에 들어가므로
# 서버 로그(예: Claude Desktop 로그 파일)에 인증키가 남지 않도록 WARNING 이상만 기록한다.
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

USER_AGENT = "Mozilla/5.0 (compatible; patent-law-mcp/0.3; +https://github.com/kimjs3176-prog/patent-law-mcp)"


def http_get(url: str, **kwargs: Any) -> httpx.Response:
    headers = {"User-Agent": USER_AGENT, **(kwargs.pop("headers", None) or {})}
    return httpx.get(url, headers=headers, **kwargs)
