"""Shared fixtures.

The stub extraction lives in the **extension tree**, not here: it is shipped inside the `.rbz` and
read by `collector.rb` at runtime. Tests read that same file rather than a copy, so a change to
what SketchUp sends cannot pass the suite while breaking the dialog.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
STUB_EXTRACTION = REPO / "poc" / "ext" / "dph_plus_poc" / "fixtures" / "stub_extraction.json"


@pytest.fixture(scope="session")
def stub_extraction() -> dict[str, Any]:
    return json.loads(STUB_EXTRACTION.read_text())


@pytest.fixture
def minimal_extraction() -> dict[str, Any]:
    """The smallest document that translates: one classified horizontal face."""
    return {
        "contract_version": 2,
        "generated_by": "tests",
        "model": {"file_name": "minimal"},
        "faces": [
            {
                "id": "face_a",
                "area_group": 1,
                "outer_loop": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            }
        ],
    }
