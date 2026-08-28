# Security

This server exposes private chat history to an AI host. Treat it as a privileged
local component.

## Supported deployment

- Use the `stdio` transport. It does not open a listening network port.
- Put the archive API behind loopback, a private overlay network, or equivalent
  access controls.
- Use a read-only archive API token.
- Keep tokens in a password manager or credential command, not in a repository.
- Leave redaction enabled. Use `external` mode for organization-specific rules.

The built-in redactor catches common credential shapes but cannot recognize every
secret. It is a safety net, not a data-loss-prevention guarantee.

## Attachments bypass the redactor

`line_read_media` decodes text-like attachments and passes them through the redactor,
but images and other binary payloads are returned as opaque bytes that no text scanner
can inspect. A password in a screenshot reaches the model unmasked.

Consequences to weigh before enabling media:

- Redaction mode `external` does not cover image or binary attachment content.
- `LINE_MCP_MEDIA_MIME_ALLOW` is the real control. Keep it narrow; `*` allows the
  archive to hand the model any file type it holds.
- Set `LINE_MCP_MEDIA_MODE=metadata` to let the model see that an attachment exists
  without loading it, or `off` to remove both attachment tools.
- Attachment bytes are held in memory and returned inline. Nothing is written to disk,
  so nothing needs to be cleaned up afterwards—but the bytes do enter the MCP host's
  conversation history like any other tool result.

## Reporting vulnerabilities

Please use GitHub's private vulnerability reporting feature. Do not include real
messages, tokens, contact names, endpoints, or database samples in a public issue.

