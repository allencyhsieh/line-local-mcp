import base64

import pytest
from mcp.types import EmbeddedResource, ImageContent, TextContent

from line_local_mcp.media import (
    DEFAULT_MIME_ALLOW,
    MediaError,
    MediaPayload,
    is_textual,
    mime_allowed,
    normalize_media_id,
    normalize_mime,
    parse_filename,
    to_content_blocks,
)
from line_local_mcp.redaction import Redactor


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('attachment; filename="report.pdf"', "report.pdf"),
        ("attachment; filename*=UTF-8''%E5%9C%96%E7%89%87.png", "圖片.png"),
        ('attachment; filename="../../etc/passwd"', "passwd"),
        ('attachment; filename="..\\\\..\\\\secret"', "secret"),
        ('attachment; filename=".."', None),
        ("attachment", None),
        (None, None),
    ],
)
def test_parse_filename_returns_a_safe_basename(value, expected):
    assert parse_filename(value) == expected


@pytest.mark.parametrize(
    ("content_type", "filename", "expected"),
    [
        ("image/PNG; charset=binary", None, "image/png"),
        ("application/octet-stream", "invoice.pdf", "application/pdf"),
        ("", "notes.txt", "text/plain"),
        ("application/octet-stream", "blob.unknown", "application/octet-stream"),
        (None, None, "application/octet-stream"),
    ],
)
def test_normalize_mime_falls_back_to_the_filename(content_type, filename, expected):
    assert normalize_mime(content_type, filename) == expected


@pytest.mark.parametrize(
    ("mime", "allowed"),
    [
        ("image/png", True),
        ("text/csv", True),
        ("application/pdf", True),
        ("application/zip", False),
        ("application/x-msdownload", False),
    ],
)
def test_default_allow_list_covers_readable_types_only(mime, allowed):
    assert mime_allowed(mime, DEFAULT_MIME_ALLOW) is allowed


def test_wildcard_allow_list_permits_everything():
    assert mime_allowed("application/x-msdownload", ("*",))


@pytest.mark.parametrize(
    "mime", ["text/plain", "application/json", "application/ld+json", "image/svg+xml"]
)
def test_textual_mimes_are_decoded(mime):
    assert is_textual(mime)


def test_binary_mimes_are_not_decoded():
    assert not is_textual("application/pdf")


@pytest.mark.parametrize("value", ["", "   ", "a b", "line\nbreak", "x" * 513])
def test_normalize_media_id_rejects_unusable_identifiers(value):
    with pytest.raises(ValueError):
        normalize_media_id(value)


def test_normalize_media_id_keeps_opaque_identifiers():
    assert normalize_media_id("  msg_42:1/image.png  ") == "msg_42:1/image.png"


def test_image_payload_becomes_viewable_image_content():
    payload = MediaPayload("m1", "image/png", "shot.png", b"\x89PNG\r\n\x1a\n")
    header, body = to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)

    assert isinstance(header, TextContent)
    assert "bytes=8" in header.text
    assert isinstance(body, ImageContent)
    assert base64.b64decode(body.data) == payload.data


def test_text_payload_is_decoded_and_redacted():
    payload = MediaPayload("m2", "text/plain", "notes.txt", b"token=" + b"a" * 30)
    _, body = to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)

    assert isinstance(body, TextContent)
    assert "aaaa" not in body.text
    assert "⟦redacted:" in body.text


def test_invalid_utf8_text_is_replaced_not_raised():
    payload = MediaPayload("m3", "text/plain", "broken.txt", b"ok\xff\xfe")
    _, body = to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)
    assert body.text.startswith("ok")


def test_binary_payload_becomes_embedded_resource_with_stable_uri():
    payload = MediaPayload("msg 7/1", "application/pdf", "invoice.pdf", b"%PDF-1.7")
    _, body = to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)

    assert isinstance(body, EmbeddedResource)
    assert str(body.resource.uri) == "line-archive://media/msg%207%2F1"
    assert base64.b64decode(body.resource.blob) == payload.data


def test_disallowed_mime_is_refused_before_any_bytes_are_encoded():
    payload = MediaPayload("m4", "application/zip", "bundle.zip", b"PK\x03\x04")
    with pytest.raises(MediaError, match="LINE_MCP_MEDIA_MIME_ALLOW"):
        to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)


def test_header_metadata_is_redacted_too():
    payload = MediaPayload("m5", "text/plain", "password=hunter2.txt", b"hi")
    header, _ = to_content_blocks(payload, Redactor("basic"), DEFAULT_MIME_ALLOW)
    assert "hunter2" not in header.text
