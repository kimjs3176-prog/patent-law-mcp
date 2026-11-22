"""원격 배포용 HTTP(streamable-http) 실행

- PATENT_LAW_MCP_TOKEN을 설정하면 모든 요청에 'Authorization: Bearer <토큰>'을 요구합니다.
- 127.0.0.1·localhost 이외 주소에 바인딩하려면 토큰이 필요합니다 (인증 없는 외부 공개 방지).
- 외부 도메인으로 접속받으려면 --allowed-host로 Host 헤더 값을 허용하십시오 (DNS rebinding 보호).
- 사용자가 요청 헤더 x-api-key로 보낸 본인 KIPRIS 키는 그 요청 처리에만 씁니다 (저장·기록하지 않음).
"""

import hmac
import os
from typing import Iterable, List, Optional

from mcp.server.transport_security import TransportSecuritySettings

from patent_law_mcp.config import request_kipris_key

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


class BearerAuthMiddleware:
    """HTTP 요청마다 Bearer 토큰을 확인하는 ASGI 미들웨어 (lifespan 등 HTTP 외 이벤트는 그대로 통과)."""

    def __init__(self, app, token: str):
        self.app = app
        self.expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            auth = dict(scope.get("headers") or []).get(b"authorization", b"")
            if not hmac.compare_digest(auth, self.expected):
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"www-authenticate", b"Bearer")],
                })
                await send({"type": "http.response.body", "body": b'{"error": "unauthorized"}'})
                return
        await self.app(scope, receive, send)


class KiprisKeyMiddleware:
    """요청 헤더 x-api-key(사용자 본인 KIPRIS 키)를 그 요청 처리 동안만 request_kipris_key에 둔다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        key = dict(scope.get("headers") or []).get(b"x-api-key", b"").decode("latin-1").strip()[:200]
        token = request_kipris_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            request_kipris_key.reset(token)


def configure_security(mcp, host: str, allowed_hosts: Iterable[str]) -> None:
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    for h in allowed_hosts:
        hosts += [h, f"{h}:*"]
        origins += [f"https://{h}", f"http://{h}", f"https://{h}:*", f"http://{h}:*"]
    mcp.settings.host = host
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


def build_http_app(mcp, token: Optional[str]):
    # 요청마다 독립 처리(stateless): 도구가 세션 상태를 쓰지 않고, 요청별 사용자 키(x-api-key)가 그 요청의 도구 실행까지 전달된다
    mcp.settings.stateless_http = True
    if hasattr(mcp, "_session_manager"):  # 세션 관리자는 처음 만들 때 설정이 고정되므로 새로 만들게 한다
        mcp._session_manager = None
    app = KiprisKeyMiddleware(mcp.streamable_http_app())
    return BearerAuthMiddleware(app, token) if token else app


def serve_http(mcp, host: str, port: int, allowed_hosts: List[str]) -> None:
    import uvicorn

    token = os.environ.get("PATENT_LAW_MCP_TOKEN", "").strip() or None
    if host not in LOCAL_HOSTS and not token:
        raise SystemExit(
            f"{host}에 바인딩하려면 환경변수 PATENT_LAW_MCP_TOKEN을 설정하십시오 (인증 없는 외부 공개는 허용하지 않습니다)."
        )
    configure_security(mcp, host, allowed_hosts)
    mcp.settings.port = port
    uvicorn.run(build_http_app(mcp, token), host=host, port=port, log_level="info")
