"""Area group → face type **and** boundary condition.

PRD §6 requires faces *with boundary conditions*. A model where every face defaults to `Outdoors` is
schema-valid and semantically wrong on exactly the surfaces PHPP treats differently — the
ground-coupled ones — so the table is exercised group by group rather than spot-checked.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from dph_translator import facetypes
from dph_translator.build import translate
from dph_translator.contract import parse

from . import synthetic as s


def faces_of(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    model = json.loads(translate(parse(document)).hbjson)
    return {face["identifier"]: face for face in model["rooms"][0]["faces"]}


@pytest.mark.parametrize(
    "group,face_type,boundary",
    [
        # ⚠ Group 1 gets no boundary condition from us, and honeybee's default for a Floor is
        # **Ground** — measured. A TFA marker therefore reads as ground-coupled envelope, which it
        # is not. Asserted so the day that default changes is a failing test, not a silent shift.
        (1, "Floor", "Ground"),
        (8, "Wall", "Outdoors"),  # external wall, ambient
        (9, "Wall", "Ground"),  # external wall, ground — zone B
        (10, "RoofCeiling", "Outdoors"),
        (11, "Floor", "Ground"),  # floor slab / basement ceiling — zone B
    ],
)
def test_the_mapped_groups(group: int, face_type: str, boundary: str) -> None:
    shape = s.floor if face_type == "Floor" else s.wall
    built = faces_of(s.document(faces=[shape("f", group)]))
    assert built["f"]["face_type"] == face_type
    assert built["f"]["boundary_condition"]["type"] == boundary


def test_a_tfa_marker_says_it_is_not_an_envelope_surface() -> None:
    """The note is the mitigation. Nothing in the POC consumes a group-1 face's boundary condition,
    but the HBJSON travels, and a reader would otherwise see a ground-coupled floor."""
    result = translate(parse(s.document(faces=[s.floor("f", 1)])))
    entry = result.report["entries"]["face"]["listed"][0]
    assert "not an envelope surface" in entry["reason"]


def test_group_18_is_adiabatic() -> None:
    """Decision D-5. A party wall to a heated neighbour is an equal-temperature boundary, so heat
    flow through it is zero. Adelphi carries 446.5 m² of it — this is not a rounding error."""
    built = faces_of(s.document(faces=[s.wall("f", 18)]))
    assert built["f"]["boundary_condition"]["type"] == "Adiabatic"


def test_user_defined_groups_are_outdoors_and_say_it_is_a_guess() -> None:
    """PHPP expects the *user* to zone groups 12–14, so `Outdoors` is the translator's assumption
    rather than designPH's data — and the report has to carry that distinction."""
    result = translate(parse(s.document(faces=[s.wall("f", 13)])))
    entry = result.report["entries"]["face"]["listed"][0]
    assert entry["outcome"] == "translated-with-notes"
    assert "user-defined slot" in entry["reason"]
    assert entry["boundary_condition"] == "Outdoors"


def test_an_unmapped_group_leaves_the_type_to_honeybee_and_says_so() -> None:
    """A face whose type we did not choose is a face whose PHPP row we cannot claim to know."""
    result = translate(parse(s.document(faces=[s.wall("f", 99)])))
    entry = result.report["entries"]["face"]["listed"][0]
    assert entry["outcome"] == "translated-with-notes"
    assert "no mapping" in entry["reason"]


@pytest.mark.parametrize("group", [2, 3, 4, 5, 6])
def test_an_aperture_group_arriving_as_a_face_is_refused(group: int) -> None:
    result = translate(parse(s.document(faces=[s.wall("f", group)])))
    entry = result.report["entries"]["face"]["listed"][0]
    assert entry["outcome"] == "reported-not-translated"
    assert "aperture, not a face" in entry["reason"]


@pytest.mark.parametrize("group", [15, 16, 17])
def test_a_thermal_bridge_group_arriving_as_a_face_is_refused(group: int) -> None:
    """Groups 15–17 are lengths on edges. A face carrying one means the collector filed a record in
    the wrong list — a bug worth seeing rather than translating around."""
    result = translate(parse(s.document(faces=[s.wall("f", group)])))
    assert "thermal bridge, not a face" in result.report["entries"]["face"]["listed"][0]["reason"]


def test_a_contradicting_temperature_zone_is_reported_never_resolved() -> None:
    """`tempZone` is *derived* from the area group by PHPP's own summary table, so reading both is a
    free integrity check. A contradiction means the model is inconsistent."""
    document = s.document(faces=[s.wall("f", 8, temp_zone="B")])
    entry = translate(parse(document)).report["entries"]["face"]["listed"][0]
    assert entry["outcome"] == "translated-with-notes"
    assert "implies temp zone 'A'" in entry["reason"]
    # ...and the face is still translated with the group's own mapping, not the zone's. The
    # contradiction is information about the model, not an instruction to follow.
    assert entry["boundary_condition"] == "Outdoors"


def test_uppercase_I_and_lowercase_i_are_not_the_same_zone() -> None:
    """`'I'` is a real envelope surface facing a neighbour; `'i'` is designPH's marker for
    unclassified clutter. A case-insensitive compare conflates them."""
    assert facetypes.zone_conflict(18, "I") is None
    assert facetypes.zone_conflict(18, "i") is not None


def test_a_matching_zone_raises_no_note() -> None:
    assert facetypes.zone_conflict(9, "B") is None
    assert facetypes.zone_conflict(9, None) is None


# ------------------------------------------------------------------------------------------------
# Winding — the type designPH assigned wins over the type honeybee would infer
# ------------------------------------------------------------------------------------------------


def normal_of(result: Any, index: int = 0) -> list[float]:
    return json.loads(result.hbjson)["rooms"][0]["faces"][index]["geometry"]["plane"]["n"]


def test_a_floor_is_wound_normal_down_to_match_its_type() -> None:
    """⚠ honeybee's `ValidateModel` rejected **40 of Adelphi's 41 Floors** as *"an upward-pointing
    Floor, which should be changed to a RoofCeiling"*. designPH winds its TFA and slab faces up.

    The direction of the fix is the decision: the **area group is authoritative** about what the
    surface is — it is PHPP's own classification — while honeybee is inferring type from geometry.
    Letting honeybee win would quietly re-file a TFA marker as roof.
    """
    result = translate(parse(s.document(faces=[s.floor("up", 1)])))
    assert json.loads(result.hbjson)["rooms"][0]["faces"][0]["face_type"] == "Floor"
    assert normal_of(result)[2] == -1.0
    assert "flipped normal-down" in result.report["entries"]["face"]["listed"][0]["reason"]


def test_a_roof_is_wound_normal_up() -> None:
    downward = [(0.0, 0.0, 3.0), (0.0, 4.0, 3.0), (4.0, 4.0, 3.0), (4.0, 0.0, 3.0)]
    result = translate(parse(s.document(faces=[s.face("roof", 10, downward)])))
    assert normal_of(result)[2] == 1.0
    assert "flipped normal-up" in result.report["entries"]["face"]["listed"][0]["reason"]


def test_a_face_already_wound_correctly_is_left_alone() -> None:
    upward = [(0.0, 0.0, 3.0), (4.0, 0.0, 3.0), (4.0, 4.0, 3.0), (0.0, 4.0, 3.0)]
    result = translate(parse(s.document(faces=[s.face("roof", 10, upward)])))
    assert normal_of(result)[2] == 1.0
    assert "flipped" not in (result.report["entries"]["face"]["listed"][0].get("reason") or "")


def test_an_untyped_face_is_not_reoriented() -> None:
    """With no mapping honeybee assigns the type from the tilt — flipping first would change the
    answer it gives, so the geometry is left exactly as designPH wound it."""
    result = translate(parse(s.document(faces=[s.floor("unmapped", 12)])))
    assert normal_of(result)[2] == 1.0
    assert "flipped" not in (result.report["entries"]["face"]["listed"][0].get("reason") or "")
