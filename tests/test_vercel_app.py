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
