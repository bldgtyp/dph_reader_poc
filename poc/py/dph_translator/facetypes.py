"""designPH area group → honeybee face type **and** boundary condition.

One table, one place. The two belong together because they come from the same source — the PHPP
`Areas` worksheet row — and splitting them is how a model ends up schema-valid and semantically
wrong on exactly the surfaces PHPP treats differently.

**Boundary conditions are mapped explicitly, never defaulted** (PRD §6). A model where every face
falls through to `Outdoors` looks fine to a validator and is wrong about every ground-coupled
surface in the building.

Sources: `00_Context/DATA_CONTRACTS.md` §4.1 (face types, observed on Adelphi's 82 faces),
`00_Context/DESIGNPH_DATA_MODEL.md` §5.3.1 (temperature zones, from `Areas!K8:N27` directly),
`planning/POC/POC-3_python-translator.md` §3 and decisions D-4/D-5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Area groups that are *apertures* in PHPP and must never arrive as a face record.
WINDOW_GROUPS = frozenset({2, 3, 4, 5, 6})

#: Area groups that are *thermal bridges*, measured as lengths on `Sketchup::Edge`. A face carrying
#: one means the collector put a record in the wrong list.
BRIDGE_GROUPS = frozenset({15, 16, 17})


@dataclass(frozen=True)
class GroupMapping:
    """What one PHPP area group means for a honeybee `Face`.

    `face_type` and `boundary` are **attribute names** on `honeybee.facetype.face_types` and
    `honeybee.boundarycondition.boundary_conditions`. Names, not objects, so this module stays
    importable without the stack on the path — the contract layer is unit-tested without it.

    `face_type=None` means "let honeybee auto-assign from the tilt", which is a legitimate outcome
    and always carries a `note`: a face whose type we did not choose is a face whose PHPP row we
    cannot claim to know.
    """

    label: str
    face_type: str | None
    boundary: str | None
    zone: str | None
    note: str | None = None


#: The whole basis for face typing. designPH stores no other classification.
AREA_GROUPS: dict[int, GroupMapping] = {
    1: GroupMapping(
        "Treated Floor Area",
        "floor",
        None,
        "TFA",
        # A TFA face is a floor-area marker, not an envelope surface: no boundary condition is
        # *right* for it, so none is assigned and honeybee's default stands. Its real job is §7.
        #
        # ⚠ And honeybee's default for a `Floor` turns out to be **`Ground`**, not `Outdoors` —
        # measured, not assumed. So a TFA marker inside the Room reads downstream as a
        # ground-coupled envelope surface, which PHPP would never call it. Harmless for the POC
        # (nothing consumes the BC of a group-1 face) and a real v1 question: TFA faces probably
        # should not be in the envelope Room at all.
        "TFA marker: floor-area only; no boundary condition assigned, so honeybee defaults it to "
        "Ground — it is not an envelope surface and should not be read as one",
    ),
    7: GroupMapping(
        "External Door",
        None,
        "outdoors",
        "A",
        "external door: no face-type mapping, honeybee assigns by tilt",
    ),
    8: GroupMapping("External Wall - Ambient", "wall", "outdoors", "A"),
    9: GroupMapping("External Wall - Ground", "wall", "ground", "B"),
    10: GroupMapping("Roof/Ceiling - Ambient", "roof_ceiling", "outdoors", "A"),
    11: GroupMapping("Floor slab / Basement ceiling", "floor", "ground", "B"),
    12: GroupMapping(
        "User-defined surface 1",
        None,
        "outdoors",
        "X",
        "user-defined slot: PHPP expects the user to zone it, so Outdoors is a guess",
    ),
    13: GroupMapping(
        "User-defined surface 2",
        None,
        "outdoors",
        "X",
        "user-defined slot: PHPP expects the user to zone it, so Outdoors is a guess",
    ),
    14: GroupMapping(
        "User-defined surface 3",
        None,
        "outdoors",
        "X",
        "user-defined slot: PHPP expects the user to zone it, so Outdoors is a guess",
    ),
    18: GroupMapping(
        "Building element towards neighbour",
        None,
        "adiabatic",
        "I",
        # Decision D-5. A party wall to a heated neighbour is an equal-temperature boundary, so the
        # heat flow through it is zero — which is what `Adiabatic` models and what PHPP assumes.
        # Adelphi carries 446.5 m² of it; getting this wrong is not a rounding error.
        "towards neighbour: Adiabatic assumes the neighbour is at equal temperature (D-5)",
    ),
}


def mapping_for(group: int | None) -> GroupMapping | None:
    """The mapping for a coalesced area group, or `None` if there is none."""
    return AREA_GROUPS.get(group) if group is not None else None


def zone_conflict(group: int | None, temp_zone: Any) -> str | None:
    """Does the face's stored temperature zone contradict its area group?

    `tempZone` is **derived** from the area group by PHPP's own summary table, so reading both gives
    a free integrity check. A contradicting pair means the model is inconsistent — **report it,
    never silently resolve it** (`DESIGNPH_DATA_MODEL.md` §5.3.1).

    ⚠ Case matters and the difference is real: `'I'` is an envelope surface facing a neighbour,
    `'i'` is designPH's marker for unclassified clutter. A case-insensitive compare conflates them.
    """
    mapping = mapping_for(group)
    if mapping is None or mapping.zone is None or not isinstance(temp_zone, str):
        return None
    found = temp_zone.strip()
    if not found or found == mapping.zone:
        return None
    return f"area group {group} implies temp zone {mapping.zone!r}, the face carries {found!r}"


def face_type_object(name: str | None) -> Any:
    """`honeybee.facetype.face_types.<name>`, or `None` to auto-assign.

    `Face(identifier, geometry, "Wall")` raises `AssertionError: Wall is not a valid face type` —
    honeybee wants the object.
    """
    if name is None:
        return None
    from honeybee.facetype import face_types

    return getattr(face_types, name)


def boundary_object(name: str | None) -> Any:
    """`honeybee.boundarycondition.boundary_conditions.<name>`, or `None` to leave the default."""
    if name is None:
        return None
    from honeybee.boundarycondition import boundary_conditions

    return getattr(boundary_conditions, name)
