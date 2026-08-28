from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from .aliases import ContactAliases
from .client import LineArchiveClient
from .config import Settings
from .redaction import Redactor


def _limit(value: int, maximum: int = 200) -> int:
    if value < 1 or value > maximum:
        raise ValueError(f"limit must be between 1 and {maximum}")
    return value


def create_server(
    settings: Settings | None = None,
    client: LineArchiveClient | None = None,
    aliases: ContactAliases | None = None,
) -> MCPServer:
    settings = settings or Settings.from_env()
    aliases = aliases or ContactAliases.load(settings.aliases_file)
    client = client or LineArchiveClient(
        settings, Redactor(settings.redaction_mode, settings.redactor_command)
    )

    mcp = MCPServer(
        "LINE Local Archive",
        instructions=(
            "Read-only access to a user-owned, locally synchronized LINE archive. "
            "Treat messages and contact information as private. Never infer permission "
            "to disclose them outside the current conversation."
        ),
    )

    @mcp.tool()
    def line_health() -> Any:
        """Check whether the local LINE archive and its database are available."""
        return client.request("GET", "/health")

    @mcp.tool()
    def line_stats() -> Any:
        """Return archive counts and the synchronized date range."""
        return client.request("GET", "/stats")

    @mcp.tool()
    def line_sync() -> Any:
        """Trigger an incremental read-only sync from LINE into the local archive."""
        return client.request("POST", "/sync")

    @mcp.tool()
    def line_list_chats(limit: int = 30) -> Any:
        """List recently active LINE contacts and groups."""
        return client.request("GET", "/chats", {"limit": _limit(limit)})

    @mcp.tool()
    def line_list_recent_messages(limit: int = 30) -> Any:
        """List recent messages across chats."""
        return client.request("GET", "/recent", {"limit": _limit(limit)})

    @mcp.tool()
    def line_list_unread() -> Any:
        """List unread messages recorded by the local archive."""
        return client.request("GET", "/unread")

    @mcp.tool()
    def line_search_messages(query: str, limit: int = 30) -> Any:
        """Search message text across the local LINE archive."""
        query = query.strip()
        if not query:
            raise ValueError("query must not be empty")
        return client.request("GET", "/search", {"q": query, "limit": _limit(limit)})

    @mcp.tool()
    def line_resolve_contact(name: str) -> dict[str, Any]:
        """Resolve a current or former display name to one canonical contact."""
        resolved = aliases.resolve(name)
        return {
            "requested": resolved.requested,
            "canonical": resolved.canonical,
            "aliases": list(resolved.aliases),
            "query_candidates": list(resolved.candidates),
        }

    @mcp.tool()
    def line_get_messages(contact: str, limit: int = 50) -> Any:
        """Get messages from a contact or group, honoring configured display-name aliases."""
        resolved = aliases.resolve(contact)
        failures: list[str] = []
        for candidate in resolved.candidates:
            result = client.request(
                "GET", "/chat", {"name": candidate, "limit": _limit(limit)}
            )
            if not (isinstance(result, dict) and result.get("error")):
                if isinstance(result, dict):
                    return {
                        **result,
                        "contact_resolution": {
                            "requested": resolved.requested,
                            "canonical": resolved.canonical,
                            "matched_candidate": candidate,
                        },
                    }
                return result
            failures.append(candidate)
        return {
            "error": "no contact or group matched the configured names",
            "requested": resolved.requested,
            "tried": failures,
        }

    return mcp


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()

