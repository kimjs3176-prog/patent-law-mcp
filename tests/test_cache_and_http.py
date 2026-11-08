import pytest
from starlette.testclient import TestClient

from patent_law_mcp import cache
from patent_law_mcp.http_app import build_http_app, configure_security, serve_http
from patent_law_mcp.server import mcp
from patent_law_mcp.tools.kipris_connector import fetch_patent_smart
from conftest import fixture_text


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    path = tmp_path / "c.sqlite3"
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", str(path))
    return path


def test_cache_roundtrip_and_ttl(cache_file, monkeypatch):
    cache.put("ns", "k", {"found": True, "v": 1})
    hit = cache.get("ns", "k")
    assert hit["v"] == 1 and hit["cache"]["hit"] is True
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE_TTL_HOURS", "0")
    assert cache.get("ns", "k") is None


def test_cache_off(monkeypatch):
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", "off")
    cache.put("ns", "k", {"v": 1})
    assert cache.get("ns", "k") is None


def test_fetch_uses_cache_and_skips_failures(cache_file, fake_http):
    fake_http.routes["KR101070281B1"] = (200, fixture_text("google_registration.html"))
    assert fetch_patent_smart("10-1070281")["found"]
    again = fetch_patent_smart("10-1070281")
    assert again["cache"]["hit"] is True and len(fake_http.calls) == 1
    fetch_patent_smart("10-1070281", refresh=True)
    assert len(fake_http.calls) == 2
    fetch_patent_smart("10-9999999")
    fetch_patent_smart("10-9999999")
    assert len(fake_http.calls) == 4  # 실패는 저장하지 않으므로 다시 조회


def test_http_requires_token_and_accepts_valid_one():
    configure_security(mcp, "127.0.0.1", [])
    app = build_http_app(mcp, "s3cret")
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
    headers = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        assert client.post("/mcp", json=init, headers=headers).status_code == 401
        assert client.post("/mcp", json=init, headers={**headers, "authorization": "Bearer wrong"}).status_code == 401
        ok = client.post("/mcp", json=init, headers={**headers, "authorization": "Bearer s3cret"})
        assert ok.status_code == 200 and "patent-law-mcp" in ok.text


def test_external_bind_without_token_is_refused(monkeypatch):
    monkeypatch.delenv("PATENT_LAW_MCP_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="PATENT_LAW_MCP_TOKEN"):
        serve_http(mcp, "0.0.0.0", 8000, [])
