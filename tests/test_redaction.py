import pytest

from line_local_mcp.redaction import RedactionError, Redactor, basic_redact


@pytest.mark.parametrize(
    "value",
    [
        "password=hunter2",
        "Authorization: " + "Bearer " + ("a" * 26),
        "token=" + ("b" * 26),
        "https://example.test/?access_token=" + ("c" * 26),
        "ghp_" + ("d" * 30),
    ],
)
def test_basic_redactor_masks_common_secrets(value):
    assert value != basic_redact(value)
    assert "⟦redacted:" in basic_redact(value)


def test_redacts_nested_values_but_not_keys():
    data = {"message": ["password=hunter2"], "password=hunter2": 1}
    result = Redactor("basic").redact(data)
    assert result["message"] == ["password=⟦redacted:credential⟧"]
    assert result["password=hunter2"] == 1


def test_external_redactor_fails_closed_on_wrong_line_count():
    redactor = Redactor(
        "external", ("python3", "-c", "import sys; sys.stdout.write('one line')")
    )
    with pytest.raises(RedactionError, match="expected"):
        redactor.redact({"a": "one", "b": "two"})
