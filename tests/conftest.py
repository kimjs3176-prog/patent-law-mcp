from pathlib import Path

import httpx
import pytest

from patent_law_mcp import net
from patent_law_mcp.tools import kipris_connector

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """테스트는 네트워크를 쓰지 않는다. 각 테스트가 fake_http로 응답을 지정한다."""
    monkeypatch.delenv("KIPRIS_API_KEY", raising=False)
    monkeypatch.delenv("PATENT_LAW_MCP_POLICY_FILE", raising=False)
    monkeypatch.delenv("LAW_OC", raising=False)
    monkeypatch.delenv("PATENT_LAW_MCP_PROFILE", raising=False)
    monkeypatch.setenv("PATENT_LAW_MCP_CACHE", "off")
    monkeypatch.setattr(kipris_connector, "RETRY_DELAY_SECONDS", 0)

    def blocked(url, **kwargs):
        raise AssertionError(f"예상하지 못한 네트워크 호출: {url}")

    monkeypatch.setattr(net, "http_get", blocked)


@pytest.fixture
def fake_http(monkeypatch):
    """URL 일부 문자열 -> (status, body) 응답표. 호출 내역은 calls에 남는다."""
    routes = {}
    calls = []

    def handler(url, **kwargs):
        calls.append((url, kwargs.get("params")))
        for key, (status, body) in routes.items():
            if key in url:
                content = body if isinstance(body, bytes) else body.encode("utf-8")
                return httpx.Response(status, content=content, request=httpx.Request("GET", url))
        raise httpx.ConnectError("no route", request=httpx.Request("GET", url))

    monkeypatch.setattr(net, "http_get", handler)
    handler.routes = routes
    handler.calls = calls
    return handler
