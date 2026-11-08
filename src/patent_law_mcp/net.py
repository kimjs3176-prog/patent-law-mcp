"""외부 HTTP 호출 단일 지점 (테스트에서 교체)."""

from typing import Any

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; patent-law-mcp/0.3; +https://github.com/kimjs3176-prog/patent-law-mcp)"


def http_get(url: str, **kwargs: Any) -> httpx.Response:
    headers = {"User-Agent": USER_AGENT, **(kwargs.pop("headers", None) or {})}
    return httpx.get(url, headers=headers, **kwargs)
