from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings
from .redaction import Redactor


class LineApiError(RuntimeError):
    """Raised when the local LINE archive API cannot answer safely."""


class LineArchiveClient:
    def __init__(self, settings: Settings, redactor: Redactor):
        self.settings = settings
        self.redactor = redactor

    def _token(self) -> str:
        if self.settings.api_token:
            return self.settings.api_token
        if not self.settings.token_command:
            raise LineApiError("no token source is configured")
        try:
            result = subprocess.run(
                self.settings.token_command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LineApiError(f"token command failed: {exc}") from exc
        token = result.stdout.strip()
        if result.returncode != 0 or not token:
            raise LineApiError("token command did not return a token")
        return token

    def request(
        self, method: str, path: str, params: dict[str, str | int] | None = None
    ) -> Any:
        url = self.settings.api_base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(
            url,
            method=method,
            data=b"" if method == "POST" else None,
            headers={"Authorization": f"Bearer {self._token()}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > self.settings.max_response_bytes:
                    raise LineApiError("LINE API response exceeds configured size limit")
                raw = response.read(self.settings.max_response_bytes + 1)
                if len(raw) > self.settings.max_response_bytes:
                    raise LineApiError("LINE API response exceeds configured size limit")
        except urllib.error.HTTPError as exc:
            raise LineApiError(f"LINE API returned HTTP {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            raise LineApiError(f"cannot reach LINE API: {exc.reason}") from exc
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LineApiError("LINE API returned invalid JSON") from exc
        return self.redactor.redact(data)

