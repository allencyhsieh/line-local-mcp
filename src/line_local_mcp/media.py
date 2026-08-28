from __future__ import annotations

import base64
import mimetypes
import posixpath
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import quote

from mcp.types import (
    BlobResourceContents,
    ContentBlock,
    EmbeddedResource,
    ImageContent,
    TextContent,
)

from .redaction import Redactor

MEDIA_MODES = ("off", "metadata", "full")

DEFAULT_MIME_ALLOW = (
    "image/*",
    "text/*",
    "application/json",
    "application/pdf",
    "application/xml",
)

_OPAQUE_MIME = "application/octet-stream"

# Textual payloads are decoded and passed through the redactor. Everything else
# is returned as opaque bytes that no redactor can inspect.
_TEXTUAL_MIMES = frozenset(
    {
        "application/csv",
        "application/javascript",
        "application/json",
        "application/sql",
        "application/x-yaml",
        "application/xml",
        "application/yaml",
    }
)

MEDIA_ID_MAX_LENGTH = 512


class MediaError(RuntimeError):
    """Raised when attachment bytes cannot be returned under the current policy."""


def normalize_media_id(value: str) -> str:
    media_id = value.strip()
    if not media_id:
        raise ValueError("media_id must not be empty")
    if len(media_id) > MEDIA_ID_MAX_LENGTH:
        raise ValueError(f"media_id must be at most {MEDIA_ID_MAX_LENGTH} characters")
    if any(character.isspace() or ord(character) < 0x20 for character in media_id):
        raise ValueError("media_id must not contain whitespace or control characters")
    return media_id


def parse_filename(content_disposition: str | None) -> str | None:
    """Extract a safe basename from a Content-Disposition header."""
    if not content_disposition:
        return None
    message = EmailMessage()
    message["Content-Disposition"] = content_disposition
    raw = message.get_filename()
    if not raw:
        return None
    name = posixpath.basename(raw.replace("\\", "/")).strip()
    if name in {"", ".", ".."}:
        return None
    return name


def normalize_mime(content_type: str | None, filename: str | None = None) -> str:
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime in {"", _OPAQUE_MIME} and filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed.lower()
    return mime or _OPAQUE_MIME


def mime_allowed(mime: str, allow: tuple[str, ...]) -> bool:
    for pattern in allow:
        if pattern in {"*", "*/*", mime}:
            return True
        if pattern.endswith("/*") and mime.startswith(pattern[:-1]):
            return True
    return False


def is_textual(mime: str) -> bool:
    return mime.startswith("text/") or mime in _TEXTUAL_MIMES or mime.endswith(("+json", "+xml"))


@dataclass(frozen=True)
class MediaPayload:
    media_id: str
    mime: str
    filename: str | None
    data: bytes

    @property
    def uri(self) -> str:
        return "line-archive://media/" + quote(self.media_id, safe="")


def to_content_blocks(
    payload: MediaPayload, redactor: Redactor, allow: tuple[str, ...]
) -> list[ContentBlock]:
    """Render one attachment as MCP content, refusing MIME types outside the allow list."""
    if not mime_allowed(payload.mime, allow):
        raise MediaError(
            f"attachment {payload.media_id!r} has MIME type {payload.mime!r}, which is not in "
            "LINE_MCP_MEDIA_MIME_ALLOW"
        )

    summary = {
        "media_id": payload.media_id,
        "mime": payload.mime,
        "bytes": len(payload.data),
        "filename": payload.filename or "(none)",
    }
    described = redactor.redact(summary)
    header = TextContent(
        type="text",
        text="LINE attachment "
        + ", ".join(f"{key}={described[key]}" for key in ("media_id", "filename", "mime", "bytes")),
    )

    if payload.mime.startswith("image/"):
        body: ContentBlock = ImageContent(
            type="image",
            data=base64.b64encode(payload.data).decode("ascii"),
            mimeType=payload.mime,
        )
    elif is_textual(payload.mime):
        body = TextContent(
            type="text",
            text=redactor.redact(payload.data.decode("utf-8", errors="replace")),
        )
    else:
        body = EmbeddedResource(
            type="resource",
            resource=BlobResourceContents(
                uri=payload.uri,
                mimeType=payload.mime,
                blob=base64.b64encode(payload.data).decode("ascii"),
            ),
        )
    return [header, body]
