from typing import Any

import pytest
from mcp import Client

from line_mcp_local.aliases import ContactAliases
from line_mcp_local.config import Settings
from line_mcp_local.server import create_server


class FakeClient:
    def __init__(self):
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(self, method, path, params=None):
        self.calls.append((method, path, params))
        if path == "/chat" and params["name"] == "Old Name":
            return {"error": "not found"}
        if path == "/chat":
            return {"messages": [{"text": "hello"}]}
        return {"ok": True}


@pytest.fixture
def settings():
    return Settings(
        api_base="http://127.0.0.1:8765",
        api_token="test",
        token_command=None,
        aliases_file=None,
        redaction_mode="basic",
        redactor_command=None,
        timeout_seconds=30,
        max_response_bytes=1024,
    )


@pytest.mark.asyncio
async def test_server_exposes_only_expected_read_tools(settings):
    server = create_server(settings, FakeClient(), ContactAliases())
    async with Client(server) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert names == {
        "line_health",
        "line_stats",
        "line_sync",
        "line_list_chats",
        "line_list_recent_messages",
        "line_list_unread",
        "line_search_messages",
        "line_resolve_contact",
        "line_get_messages",
    }
    assert not any("send" in name or "delete" in name for name in names)


@pytest.mark.asyncio
async def test_get_messages_falls_back_from_old_to_canonical_name(settings):
    fake = FakeClient()
    server = create_server(settings, fake, ContactAliases({"New Name": ("Old Name",)}))
    async with Client(server) as client:
        result = await client.call_tool(
            "line_get_messages", {"contact": "Old Name", "limit": 5}
        )
    assert not result.is_error
    assert [call[2]["name"] for call in fake.calls] == ["Old Name", "New Name"]

