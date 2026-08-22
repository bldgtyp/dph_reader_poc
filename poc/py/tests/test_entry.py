"""The seam itself: `translate_json(str) -> str`.

Everything here is about the *contract of the call*, not the translation. The dialog has no way to
recover from an exception crossing the wasm boundary -- the traceback is lost and the banner has
nothing to show -- so `translate_json` must return a well-formed result for every input, including
garbage.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from dph_translator import entry


def test_returns_the_three_agreed_keys(stub_extraction: dict[str, Any]) -> None:
    result = json.loads(entry.translate_json(json.dumps(stub_extraction)))
    assert set(result) == {"hbjson", "report", "verdict"}
    assert result["verdict"]["passed"] is True
    assert json.loads(result["hbjson"])["type"] == "Model"


@pytest.mark.parametrize(
    "payload,expected_label",
    [
        ("not json at all", "payload is JSON"),
        ('{"contract_version": 99, "faces": []}', "payload matches the contract"),
        ('{"contract_version": 2}', "payload matches the contract"),
        ("[]", "payload matches the contract"),
    ],
)
def test_bad_input_returns_a_verdict_rather_than_raising(payload: str, expected_label: str) -> None:
    result = json.loads(entry.translate_json(payload))
    assert set(result) == {"hbjson", "report", "verdict"}
    assert result["verdict"]["passed"] is False
    assert result["verdict"]["checks"][0]["label"] == expected_label
    assert result["hbjson"] == ""


def test_the_result_survives_a_json_round_trip(stub_extraction: dict[str, Any]) -> None:
    """The result crosses wasm → JS → Ruby as a string and is parsed twice on the way. Anything
    that is not JSON-serialisable would fail at the far end, where it is hardest to diagnose."""
    text = entry.translate_json(json.dumps(stub_extraction))
    assert json.dumps(json.loads(text)) == text
