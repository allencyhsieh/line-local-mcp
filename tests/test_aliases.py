import json

import pytest

from line_mcp_local.aliases import AliasFileError, ContactAliases


def test_alias_resolves_to_canonical_and_keeps_requested_first(tmp_path):
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"New Name": ["Old Name"]}), encoding="utf-8")
    aliases = ContactAliases.load(str(path))

    resolved = aliases.resolve("Old Name")

    assert resolved.canonical == "New Name"
    assert resolved.candidates == ("Old Name", "New Name")


def test_duplicate_alias_is_rejected():
    with pytest.raises(AliasFileError):
        ContactAliases({"One": ("Shared",), "Two": ("Shared",)})

