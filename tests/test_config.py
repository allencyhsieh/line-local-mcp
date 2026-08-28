import pytest

from line_mcp_local.config import ConfigurationError, Settings


def test_requires_api_base(monkeypatch):
    monkeypatch.delenv("LINE_API_BASE", raising=False)
    monkeypatch.setenv("LINE_API_TOKEN", "test")
    with pytest.raises(ConfigurationError, match="LINE_API_BASE"):
        Settings.from_env()


def test_rejects_plain_http_off_loopback(monkeypatch):
    monkeypatch.setenv("LINE_API_BASE", "http://archive.example")
    monkeypatch.setenv("LINE_API_TOKEN", "test")
    monkeypatch.delenv("LINE_MCP_ALLOW_INSECURE_HTTP", raising=False)
    with pytest.raises(ConfigurationError, match="HTTPS"):
        Settings.from_env()


def test_allows_loopback_http(monkeypatch):
    monkeypatch.setenv("LINE_API_BASE", "http://127.0.0.1:8765/")
    monkeypatch.setenv("LINE_API_TOKEN", "test")
    settings = Settings.from_env()
    assert settings.api_base == "http://127.0.0.1:8765"

