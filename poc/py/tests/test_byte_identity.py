"""The canonicaliser behind POC-4's cross-host check.

`byte_identity.py` decides whether two hosts produced the same model, and the plan asked for that
in the strongest form: byte-identical output. **The stack cannot deliver it** — honeybee-ph mints a
fresh `uuid4` per newly constructed PH object (152 distinct on Adelphi) and honeybee-energy
orders four of its lists out of a `set`, so three consecutive runs on ONE CPython give three
different hashes. The gate is therefore canonical equivalence, and a canonicaliser is only worth
having if it cannot hide a real difference.

That is what this file pins down. Two rules carry all the weight:

* **UUIDs are numbered, not blanked.** Blanking would erase aliasing, and aliasing is where the
  interesting defects live — a segment pointing at the wrong site is a difference between two
  *fields*, not between two values.
* **Only four named lists are sorted.** ⚠ A blanket `sort every list` would reorder `boundary`
  vertices, which is what defines a face's orientation, and two walls facing opposite ways would
  canonicalise identical. That is the failure this suite exists to make impossible.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "poc/tools/byte_identity.py"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("byte_identity_under_test", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(tool: ModuleType, document: Any) -> str:
    return json.dumps(tool.canonicalise(document), sort_keys=True)


UUID_A = "a17ad9f0-ba55-48b0-843a-8f671b34df6b"
UUID_B = "7bd63f4a-d118-44a0-b65e-216bd46d909c"
UUID_C = "db35a66d-5015-4f02-b190-ff57eba9abbb"


def test_a_fresh_set_of_uuids_canonicalises_the_same(tool: ModuleType) -> None:
    """The whole point: two runs differing only in their minted identifiers are the same model."""
    first = {"identifier": UUID_A, "site": {"identifier": UUID_C}}
    second = {"identifier": UUID_B, "site": {"identifier": UUID_A}}
    assert digest(tool, first) == digest(tool, second)


def test_aliasing_survives_canonicalisation(tool: ModuleType) -> None:
    """Two fields sharing one uuid is a different document from two fields with distinct ones.

    This is what numbering buys over blanking, and it is the difference between a canonicaliser and
    a shredder.
    """
    shared = {"a": UUID_A, "b": UUID_A}
    distinct = {"a": UUID_A, "b": UUID_B}
    assert digest(tool, shared) != digest(tool, distinct)


def test_a_cross_reference_pointing_elsewhere_is_a_difference(tool: ModuleType) -> None:
    """The defect this has to catch: an object referring to the wrong other object.

    ⚠ Note what is NOT a difference — `{a: X, b: Y}` versus `{a: Y, b: X}` canonicalise the same,
    because the numbering is positional and both are just two freshly minted identifiers. That is
    correct: which uuid4 came out of the generator first says nothing about the model. What must
    survive is a *reference* changing target, and it does.
    """
    document = {"site": {"identifier": UUID_A}, "climate": {"identifier": UUID_B}}
    to_site = dict(document, segment={"site_id": UUID_A})
    to_climate = dict(document, segment={"site_id": UUID_B})
    assert digest(tool, to_site) != digest(tool, to_climate)


def test_a_non_uuid_string_is_untouched(tool: ModuleType) -> None:
    """Face names, assembly names and area groups are user data and must compare literally."""
    assert digest(tool, {"display_name": "104C HALL"}) != digest(tool, {"display_name": "104C hall"})
    # A near-miss must not be swallowed: one character short of a uuid4 is not a uuid4.
    nearly = UUID_A[:-1]
    assert nearly in digest(tool, {"identifier": nearly})


def test_the_four_energy_lists_are_order_insensitive(tool: ModuleType) -> None:
    for path in tool.UNORDERED_PATHS:
        document: Any = {"x": 1}
        cursor = document
        parts = path.split(".")
        for key in parts[:-1]:
            cursor[key] = {}
            cursor = cursor[key]
        cursor[parts[-1]] = [{"identifier": "b"}, {"identifier": "a"}]

        reversed_document = json.loads(json.dumps(document))
        target = reversed_document
        for key in parts[:-1]:
            target = target[key]
        target[parts[-1]].reverse()

        assert digest(tool, document) == digest(tool, reversed_document), path


def test_geometry_order_is_NOT_sorted(tool: ModuleType) -> None:
    """⚠ The rule that makes the canonicaliser safe.

    `boundary` vertex order defines a face's orientation. A canonicaliser that sorted every list
    would report a wall and its mirror image as the same object — a silent failure in the one check
    whose job is to catch silent failures.
    """
    clockwise = {"geometry": {"boundary": [[0, 0, 0], [1, 0, 0], [1, 1, 0]]}}
    widdershins = {"geometry": {"boundary": [[1, 1, 0], [1, 0, 0], [0, 0, 0]]}}
    assert digest(tool, clockwise) != digest(tool, widdershins)


def test_room_and_aperture_order_is_NOT_sorted(tool: ModuleType) -> None:
    """Nothing outside the four named paths is reordered, however list-like it looks."""
    assert digest(tool, {"rooms": ["a", "b"]}) != digest(tool, {"rooms": ["b", "a"]})
    assert digest(tool, {"apertures": ["a", "b"]}) != digest(tool, {"apertures": ["b", "a"]})
    # Same key name, wrong parent: `materials` is only unordered under `properties.energy`.
    assert digest(tool, {"materials": ["a", "b"]}) != digest(tool, {"materials": ["b", "a"]})


def test_a_float_difference_still_shows(tool: ModuleType) -> None:
    """Everything a HOST could plausibly change has to survive — that is what is being measured."""
    assert digest(tool, {"area": 12.34}) != digest(tool, {"area": 12.340000000000001})


def test_identity_needs_two_hosts(tool: ModuleType) -> None:
    """⚠ A single leg is trivially self-consistent, and a run of failures has one distinct digest —
    none. Both would read as a pass if `identical` only counted distinct values."""
    leg = tool.Leg(host="cpython3.11", digest="d", canonical="c", size=1)
    other = tool.Leg(host="chromium88", digest="e", canonical="c", size=1)
    failed = tool.Leg(host="chromium88", digest=None, canonical=None, size=0, detail="boom")

    assert not tool.Outcome("solo", [leg]).identical
    assert not tool.Outcome("all-failed", [failed, failed]).identical
    assert not tool.Outcome("half-failed", [leg, failed]).identical
    assert tool.Outcome("agreeing", [leg, other]).identical
    # Canonical agreement is the gate; raw agreement is reported separately and is expected to be
    # false for as long as upstream mints uuids per run.
    assert not tool.Outcome("agreeing", [leg, other]).byte_identical
