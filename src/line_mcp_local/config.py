from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or unsafe."""


def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_base: str
    api_token: str | None
    token_command: tuple[str, ...] | None
    aliases_file: str | None
    redaction_mode: str
    redactor_command: tuple[str, ...] | None
    timeout_seconds: float
    max_response_bytes: int

    @classmethod
    def from_env(cls) -> Settings:
        api_base = os.getenv("LINE_API_BASE", "").strip().rstrip("/")
        if not api_base:
            raise ConfigurationError("LINE_API_BASE is required")

        parsed = urlparse(api_base)
        is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https" and not is_loopback and not _truthy(
            "LINE_MCP_ALLOW_INSECURE_HTTP"
        ):
            raise ConfigurationError(
                "LINE_API_BASE must use HTTPS unless it is loopback; "
                "set LINE_MCP_ALLOW_INSECURE_HTTP=1 only for a trusted network"
            )

        api_token = os.getenv("LINE_API_TOKEN", "").strip() or None
        token_raw = os.getenv("LINE_API_TOKEN_COMMAND", "").strip()
        token_command = tuple(shlex.split(token_raw)) if token_raw else None
        if not api_token and not token_command:
            raise ConfigurationError(
                "Set LINE_API_TOKEN or LINE_API_TOKEN_COMMAND; secrets are never read from files"
            )

        redaction_mode = os.getenv("LINE_MCP_REDACTION_MODE", "basic").strip().lower()
        if redaction_mode not in {"basic", "external", "off"}:
            raise ConfigurationError(
                "LINE_MCP_REDACTION_MODE must be basic, external, or off"
            )
        redactor_raw = os.getenv("LINE_MCP_REDACTOR_COMMAND", "").strip()
        redactor_command = tuple(shlex.split(redactor_raw)) if redactor_raw else None
        if redaction_mode == "external" and not redactor_command:
            raise ConfigurationError(
                "LINE_MCP_REDACTOR_COMMAND is required when redaction mode is external"
            )

        return cls(
            api_base=api_base,
            api_token=api_token,
            token_command=token_command,
            aliases_file=os.getenv("LINE_MCP_ALIASES_FILE", "").strip() or None,
            redaction_mode=redaction_mode,
            redactor_command=redactor_command,
            timeout_seconds=float(os.getenv("LINE_MCP_TIMEOUT", "30")),
            max_response_bytes=int(os.getenv("LINE_MCP_MAX_RESPONSE_BYTES", "5242880")),
        )
