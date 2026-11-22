"""Vercel 배포용 ASGI 앱 — 토큰·공개 모드·설정 누락, 요청마다 상태 없는 MCP 처리"""

import json

from starlette.testclient import TestClient

from patent_law_mcp import vercel_app

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
HDR = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _client(monkeypatch, **env):
    for k in ("PATENT_LAW_MCP_TOKEN", "PATENT_LAW_MCP_ALLOW_ANONYMOUS"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return TestClient(vercel_app.build_app(), base_url="https://my-proj.vercel.app")


def test_token_required_and_stateless_requests_work(monkeypatch):
    c = _client(monkeypatch, PATENT_LAW_MCP_TOKEN="s3cret")
    assert c.post("/mcp", json=INIT, headers=HDR).status_code == 401
    auth = {**HDR, "Authorization": "Bearer s3cret"}
    r = c.post("/mcp", json=INIT, headers=auth)
    assert r.status_code == 200 and r.json()["result"]["serverInfo"]["name"] == "patent-law-mcp"
    tools = c.post("/mcp", json=LIST, headers=auth).json()["result"]["tools"]  # 세션 없이 다음 요청도 처리
    assert len(tools) == 33


def test_anonymous_must_be_explicit(monkeypatch):
    r = _client(monkeypatch).post("/mcp", json=INIT, headers=HDR)
    assert r.status_code == 503 and "PATENT_LAW_MCP_TOKEN" in r.json()["detail"]
    ok = _client(monkeypatch, PATENT_LAW_MCP_ALLOW_ANONYMOUS="1").post("/mcp", json=INIT, headers=HDR)
    assert ok.status_code == 200


def test_root_and_unknown_paths(monkeypatch):
    c = _client(monkeypatch, PATENT_LAW_MCP_ALLOW_ANONYMOUS="1")
    assert c.get("/").json()["mcp_endpoint"] == "/mcp"
    assert c.get("/sse").status_code == 404



def test_status_page_is_public_and_shows_config_without_secrets(monkeypatch):
    c = _client(monkeypatch, PATENT_LAW_MCP_TOKEN="s3cret", KIPRIS_API_KEY="k")
    r = c.get("/")
    assert r.status_code == 200 and r.json()["auth"] == "Bearer 토큰" and r.json()["kipris_api_key"] is True
    assert "s3cret" not in r.text and '"k"' not in r.text
    assert _client(monkeypatch).get("/").json()["auth"].startswith("미설정")


def test_browser_gets_landing_page_and_programs_get_status(monkeypatch):
    c = _client(monkeypatch, PATENT_LAW_MCP_ALLOW_ANONYMOUS="1")
    page = c.get("/", headers={"Accept": "text/html,application/xhtml+xml"})
    assert page.status_code == 200 and page.headers["content-type"].startswith("text/html")
    assert "국가직무발명특허권등" in page.text and "/mcp" in page.text
    status = c.get("/status").json()
    assert status["tool_count"] == 33 and status["source_text_verified_on"]
    assert c.get("/").json()["auth"] == "없음 (공개)"  # Accept가 HTML이 아니면 지금처럼 JSON
    tok = _client(monkeypatch, PATENT_LAW_MCP_TOKEN="s3cret")
    assert tok.get("/", headers={"Accept": "text/html"}).status_code == 200  # 안내 페이지는 토큰 없이 열림
    assert tok.get("/status").status_code == 200


def test_landing_page_lists_every_tool_exactly():
    # 안내 페이지의 도구 이름이 실제 등록된 도구와 어긋나지 않도록
    import asyncio
    import re

    from patent_law_mcp.server import mcp

    html = vercel_app.INDEX_HTML.decode("utf-8")
    on_page = set(re.findall(r"<code>([a-z_]+)</code>", html))
    registered = {t.name for t in asyncio.run(mcp.list_tools())}
    assert on_page == registered, (registered - on_page, on_page - registered)


def test_user_kipris_key_from_connector_header_is_used_per_request(monkeypatch):
    # 서버에 KIPRIS 키가 없어도, 사용자가 커넥터 요청 헤더 x-api-key로 보낸 본인 키로 검색한다 (그 요청에만)
    from patent_law_mcp import net
    from patent_law_mcp.config import request_kipris_key

    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", "off")
    seen = []

    class Resp:
        status_code = 200
        text = "<response><header><resultCode>00</resultCode></header><body><items></items><count><totalCount>0</totalCount></count></body></response>"

        def raise_for_status(self):
            return None

    google = []

    class Blocked(Resp):
        status_code = 503
        text = "<html>Sorry</html>"

    def fake_get(url, **kw):
        if "patents.google.com" in url:  # 키가 없으면 Google Patents 검색으로 대신한다
            google.append(url)
            return Blocked()
        seen.append((kw.get("params") or {}).get("ServiceKey"))
        return Resp()

    monkeypatch.setattr(net, "http_get", fake_get)
    c = _client(monkeypatch, PATENT_LAW_MCP_ALLOW_ANONYMOUS="1")
    call = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_patents", "arguments": {"query": "떡"}}}

    no_key = c.post("/mcp", json=call, headers=HDR).json()["result"]
    assert "x-api-key" in json.dumps(no_key, ensure_ascii=False) and seen == [] and len(google) == 2  # 503이면 한 번 더 시도

    c.post("/mcp", json=call, headers={**HDR, "x-api-key": "user-key-123"})
    assert seen == ["user-key-123"]
    assert request_kipris_key.get() == ""  # 요청이 끝나면 비워짐

    c.post("/mcp", json=call, headers=HDR)  # 다음 사용자의 요청에는 남지 않음
    assert seen == ["user-key-123"]
