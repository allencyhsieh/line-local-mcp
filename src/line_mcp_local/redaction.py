from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator
from typing import Any


class RedactionError(RuntimeError):
    """Raised when data cannot be redacted safely."""


_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"(?i)\b(password|passwd|pwd|api[_ -]?key|access[_ -]?token|token|secret)"
        r"\b(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)([?&](?:access_token|api_key|token)=)[^&#\s]+"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
)


def basic_redact(value: str) -> str:
    result = value
    for index, pattern in enumerate(_PATTERNS):
        if index == 3:
            result = pattern.sub(r"\1\2⟦redacted:credential⟧", result)
        elif index == 4:
            result = pattern.sub(r"\1⟦redacted:url-token⟧", result)
        else:
            result = pattern.sub("⟦redacted:secret⟧", result)
    return result


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def _rebuild(value: Any, strings: Iterator[str]) -> Any:
    if isinstance(value, str):
        return next(strings)
    if isinstance(value, list):
        return [_rebuild(item, strings) for item in value]
    if isinstance(value, dict):
        return {key: _rebuild(item, strings) for key, item in value.items()}
    return value


class Redactor:
    def __init__(self, mode: str = "basic", command: tuple[str, ...] | None = None):
        self.mode = mode
        self.command = command

    def redact(self, data: Any) -> Any:
        if self.mode == "off":
            return data
        values = list(_strings(data))
        if not values:
            return data
        if self.mode == "basic":
            output = [basic_redact(value) for value in values]
        elif self.mode == "external":
            output = self._external(values)
        else:  # Defensive: Settings validates this before construction.
            raise RedactionError(f"unsupported redaction mode: {self.mode}")
        return _rebuild(data, iter(output))

    def _external(self, values: list[str]) -> list[str]:
        if not self.command:
            raise RedactionError("external redaction command is not configured")
        payload = "\n".join(values)
        expected_lines = sum(value.count("\n") for value in values) + len(values)
        try:
            result = subprocess.run(
                self.command,
                input=payload,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RedactionError(f"external redactor failed: {exc}") from exc
        if result.returncode not in {0, 1}:
            raise RedactionError(
                f"external redactor exited with status {result.returncode}"
            )
        lines = result.stdout.split("\n")
        if len(lines) != expected_lines:
            raise RedactionError(
                f"external redactor returned {len(lines)} lines; expected {expected_lines}"
            )
        iterator = iter(lines)
        return [
            "\n".join(next(iterator) for _ in range(value.count("\n") + 1))
            for value in values
        ]
