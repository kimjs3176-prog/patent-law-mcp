"""Vercel(서버리스) 배포용 ASGI 앱 — 저장소 맨 위 app.py가 이 모듈의 app을 내보냅니다.

서버리스 함수는 요청 사이에 프로세스 상태가 유지된다는 보장이 없으므로
요청마다 상태 없는(stateless) MCP 세션 관리자를 새로 띄워 처리하고, 응답은 JSON으로 돌려줍니다.
lifespan 이벤트에 의존하지 않습니다.

환경변수
- PATENT_LAW_MCP_TOKEN: 설정하면 모든 요청에 'Authorization: Bearer <토큰>'을 요구 (권장)
- PATENT_LAW_MCP_ALLOW_ANONYMOUS=1: 토큰 없이 공개 운영 (토큰을 설정하지 않았을 때 명시적으로 켜야 함)
- KIPRIS_API_KEY, LAW_OC, PATENT_LAW_MCP_PROFILE: 로컬 실행과 같음
- PATENT_LAW_MCP_CACHE: 비우면 Vercel에서는 /tmp/patent-law-mcp/cache.sqlite3 (쓰기 가능한 유일한 위치)
"""

import json
import os

if os.environ.get("VERCEL"):  # Vercel이 자동으로 넣는 변수. 함수 파일시스템은 /tmp만 쓸 수 있다
    os.environ.setdefault("PATENT_LAW_MCP_CACHE", "/tmp/patent-law-mcp/cache.sqlite3")

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager  # noqa: E402
from mcp.server.transport_security import TransportSecuritySettings  # noqa: E402

from patent_law_mcp.http_app import BearerAuthMiddleware  # noqa: E402
from patent_law_mcp.server import DISPLAY_NAME, mcp  # noqa: E402

MCP_PATHS = ("/mcp", "/mcp/")
# 공개 HTTPS 배포에서는 DNS rebinding 보호(로컬 서버용)가 필요 없고, Vercel 도메인이 배포마다 달라 Host 검사를 끕니다.
_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)


async def _send_json(send, status: int, body: dict) -> None:
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json; charset=utf-8")]})
    await send({"type": "http.response.body", "body": json.dumps(body, ensure_ascii=False).encode()})


async def mcp_app(scope, receive, send):
    if scope["type"] == "lifespan":  # 상태를 들고 있지 않으므로 할 일이 없다
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    if scope["type"] != "http":
        return
    path = scope.get("path", "")
    if path in ("", "/"):
        token_set = bool(os.environ.get("PATENT_LAW_MCP_TOKEN", "").strip())
        anonymous = os.environ.get("PATENT_LAW_MCP_ALLOW_ANONYMOUS", "").strip().lower() in ("1", "true", "yes")
        await _send_json(send, 200, {
            "name": DISPLAY_NAME,
            "mcp_endpoint": "/mcp",
            "auth": "Bearer 토큰" if token_set else ("없음 (공개)" if anonymous else "미설정 — /mcp 요청이 거부됩니다"),
            "kipris_api_key": bool(os.environ.get("KIPRIS_API_KEY", "").strip()),
            "law_oc": bool(os.environ.get("LAW_OC", "").strip()),
            "profile": os.environ.get("PATENT_LAW_MCP_PROFILE", "national"),
        })
        return
    if path not in MCP_PATHS:
        await _send_json(send, 404, {"error": "not found", "mcp_endpoint": "/mcp"})
        return
    manager = StreamableHTTPSessionManager(app=mcp._mcp_server, json_response=True, stateless=True, security_settings=_SECURITY)
    async with manager.run():
        await manager.handle_request(scope, receive, send)


def _public_status_or(protected):
    """'/'(상태 확인)는 토큰 없이 열어 두고, 나머지 경로만 보호한다. 배포 직후 주소 확인용."""

    async def app(scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "") in ("", "/"):
            return await mcp_app(scope, receive, send)
        return await protected(scope, receive, send)

    return app


def build_app():
    token = os.environ.get("PATENT_LAW_MCP_TOKEN", "").strip()
    if token:
        return _public_status_or(BearerAuthMiddleware(mcp_app, token))
    if os.environ.get("PATENT_LAW_MCP_ALLOW_ANONYMOUS", "").strip().lower() in ("1", "true", "yes"):
        return mcp_app

    async def refuse(scope, receive, send):  # 설정 누락을 조용히 공개 운영으로 넘기지 않는다
        if scope["type"] == "lifespan" or (scope["type"] == "http" and scope.get("path", "") in ("", "/")):
            return await mcp_app(scope, receive, send)
        if scope["type"] == "http":
            await _send_json(send, 503, {
                "error": "서버 설정 필요",
                "detail": "Vercel 환경변수에 PATENT_LAW_MCP_TOKEN을 설정하거나, 토큰 없이 공개하려면 PATENT_LAW_MCP_ALLOW_ANONYMOUS=1을 설정한 뒤 다시 배포하십시오.",
            })

    return refuse


app = build_app()
