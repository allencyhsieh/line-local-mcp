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

## Reporting vulnerabilities

Please use GitHub's private vulnerability reporting feature. Do not include real
messages, tokens, contact names, endpoints, or database samples in a public issue.

