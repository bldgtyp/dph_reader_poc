"""TFA → PH `Space`s. Filter, attempt, report — and never project or repair.

**TFA is a headline Passive House number.** Phase 3's run produced *no* `Space` at all from a real
model and nothing said so; that silent zero is the failure this module exists to prevent. Its
contribution to v1 is not a clever derivation, it is a **measurement of how much TFA area the honest
strategy loses on real models** — which is what §7 of the results table will carry.

`Space.from_room` has two failure modes and both fire on real data
(`00_Context/HONEYBEE_STACK.md` §4):

1. `Honeybee Room '…' has no Floor faces` — normal. A wall-and-roof selection has no TFA.
2. `Floor face '…' must be horizontal for World-Z extrusion` — **this one fired on Adelphi.**

The strategy, in order:

* candidates are **area group 1 only** (decision D-4). Group 11 is envelope floor slab, not TFA.
* ⚠ `tfa_rf` **absent means weighting factor 1.0, not exclusion.** On Adelphi only 7 of ~40 group-1
  faces carry `TFA_rf`; filtering on its presence would silently collapse the number.
* horizontality is tested **before** honeybee is asked, with **honeybee's own predicate at
  honeybee's own tolerance**, so a face that would raise becomes a named report entry instead.
* a face whose z-spread is below `FLATTEN_TOLERANCE_M` is **flattened to its mean z and reported**.
* the extrusion runs on a **throwaway Room** built from the surviving faces — never on the real one,
  whose group-11 slab Floor faces would contaminate it.
* if honeybee refuses anyway, the face it **names** is dropped and the extrusion retried. One face
  must never cost the room.

⚠ **The pre-filter that shipped first measured the wrong quantity**, and it is the sharpest lesson
on this project. `abs(normal.z − 1) < 0.01` reads as a horizontality test and is not one:
`Face3D.is_horizontal` tests **z-extent**, at **1e-7 m**. Two of Adelphi's 40 TFA faces have a 12 µm
z-spread with `normal.z = 0.999999999998` — they sailed through the guard, raised inside
`Space.from_room`, and because that raises for the whole room, **all 40 faces and 368 m² were lost**.
A pre-filter must use the same predicate as the thing it protects; getting a tolerance wrong is
recoverable, measuring a different quantity is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contract import Extraction, FaceRecord, as_float

#: The tolerance `honeybee_ph.space.Space.from_room` passes to `Face3D.is_horizontal` — read off the
#: library, not chosen. A tenth of a micron; **no CAD model is flat to it.**
SPACE_FROM_ROOM_TOLERANCE = 1e-7

#: How much z-spread is *noise* rather than slope. Below this a TFA face is flattened to its mean z
#: and the flattening is reported; above it the face is refused and named. 1 mm is well inside any
#: modelling tolerance and far outside honeybee's 1e-7 — the gap between the two is exactly the
#: population this module exists to rescue. Projecting a genuinely sloped floor would be fabrication.
FLATTEN_TOLERANCE_M = 0.001

#: `vent_ud` carries the room height designPH will hand PHPP — already SI (metres).
ROOM_HEIGHT_TOKEN = "room_height"
DEFAULT_CEILING_HEIGHT_M = 2.5

TFA_GROUP = 1


@dataclass
class Outcome:
    """What the space derivation managed, and precisely what it did not."""

    space: Any | None = None
    ceiling_height_m: float = DEFAULT_CEILING_HEIGHT_M
    covered_m2: float = 0.0
    lost_m2: float = 0.0
    #: `(face id, reason)` for every TFA face that did not contribute. Named, per hard rule 4.
    not_derived: list[tuple[str, str]] = field(default_factory=list)
    #: `(face id, reason)` for every face that contributed **after being changed**. Also named:
    #: a repair nobody can see is a repair nobody can disagree with.
    adjusted: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class _Candidate:
    """One TFA face on its way into the extrusion, with the geometry actually used."""

    record: FaceRecord
    identifier: str
    geometry: Any

    @property
    def area(self) -> float:
        area: float = self.geometry.area
        return area


def ceiling_height(extraction: Extraction, outcome: Outcome) -> float:
    """Average clear height, from `vent_ud`.

    Multiple rows are possible. The plan's rule is explicit: **report and use the first** — picking
    an average would invent a building that does not exist.
    """
    table = extraction.tables.get("vent_ud")
    if table is None:
        outcome.notes.append("no `vent_ud` table; using the default ceiling height")
        return DEFAULT_CEILING_HEIGHT_M
    records = table.records()
    if not records:
        outcome.notes.append("`vent_ud` has no rows; using the default ceiling height")
        return DEFAULT_CEILING_HEIGHT_M
    if len(records) > 1:
        outcome.notes.append(f"`vent_ud` has {len(records)} rows; using the first")
    height = as_float(records[0].get(ROOM_HEIGHT_TOKEN))
    if height is None or height <= 0:
        outcome.notes.append(f"`vent_ud.{ROOM_HEIGHT_TOKEN}` is not a usable height")
        return DEFAULT_CEILING_HEIGHT_M
    return height


def _flatten(geometry: Any) -> Any:
    """The same polygon, every vertex at the boundary's mean z.

    Noise removal within a stated threshold, never repair: the caller has already established that
    the whole face lives inside `FLATTEN_TOLERANCE_M`, and it reports each one it does this to.
    Holes travel with it — a TFA face with a stair opening is ordinary.
    """
    from ladybug_geometry.geometry3d.face import Face3D
    from ladybug_geometry.geometry3d.pointvector import Point3D

    z = sum(point.z for point in geometry.boundary) / len(geometry.boundary)

    def flat(loop: Any) -> list[Any]:
        return [Point3D(point.x, point.y, z) for point in loop]

    holes = [flat(hole) for hole in geometry.holes] if geometry.has_holes else None
    return Face3D(flat(geometry.boundary), holes=holes)


def _classify(record: FaceRecord, face: Any, outcome: Outcome) -> _Candidate | None:
    """One TFA face → a usable candidate, or `None` with the loss recorded and named."""
    geometry = face.geometry
    if geometry.is_horizontal(SPACE_FROM_ROOM_TOLERANCE):
        return _Candidate(record, face.identifier, geometry)

    spread = geometry.max.z - geometry.min.z
    if spread <= FLATTEN_TOLERANCE_M:
        outcome.adjusted.append(
            (
                record.id,
                f"flattened to its mean z for the TFA extrusion: {spread * 1000:.3f} mm z-spread, "
                f"below the {FLATTEN_TOLERANCE_M * 1000:.0f} mm noise threshold and above "
                f"honeybee's {SPACE_FROM_ROOM_TOLERANCE:g} m. The exported envelope face is "
                "unchanged",
            )
        )
        return _Candidate(record, face.identifier, _flatten(geometry))

    # The silent-loss guard. Every one of these is named, and the area is counted, because "TFA is
    # 40 m² short" is a question somebody has to be able to ask.
    outcome.not_derived.append(
        (
            record.id,
            f"TFA face has a {spread * 1000:.1f} mm z-spread, over the "
            f"{FLATTEN_TOLERANCE_M * 1000:.0f} mm flattening limit; World-Z extrusion would raise",
        )
    )
    outcome.lost_m2 += geometry.area
    return None


def _refused(error: Exception, candidates: list[_Candidate]) -> _Candidate | None:
    """The candidate honeybee named in its own error message, if it named one.

    Every `Space.from_room` refusal quotes the offending `floor_face.identifier`, which is what makes
    dropping one face cheaper than losing the room. A refusal that names nobody is not guessed at.
    """
    message = str(error)
    for candidate in candidates:
        if f"'{candidate.identifier}'" in message:
            return candidate
    return None


def weighting_factor(record: FaceRecord) -> float:
    """`TFA_rf`, defaulting to **1.0 when absent**.

    The default is the whole point. Treating absence as exclusion would drop 33 of Adelphi's ~40
    TFA faces and report a plausible, badly wrong number.
    """
    factor = as_float(record.tfa_rf)
    return 1.0 if factor is None else factor


def derive(
    extraction: Extraction,
    tfa_faces: list[tuple[FaceRecord, Any]],
    room: Any,
) -> Outcome:
    """Build one PH `Space` from the model's group-1 faces and attach it to `room`.

    `tfa_faces` is `(record, honeybee Face)` for every translated area-group-1 face.
    """
    outcome = Outcome()
    outcome.ceiling_height_m = ceiling_height(extraction, outcome)
    if not tfa_faces:
        outcome.notes.append(f"no area-group-{TFA_GROUP} faces in the model")
        return outcome

    candidates = [
        candidate
        for candidate in (_classify(record, face, outcome) for record, face in tfa_faces)
        if candidate is not None
    ]
    if not candidates:
        outcome.notes.append("no horizontal TFA face survived the filter; no Space derived")
        return outcome

    space = _extrude(candidates, room, outcome)
    outcome.covered_m2 = sum(candidate.area for candidate in candidates)
    if space is None:
        return outcome

    space.name = f"{room.display_name} TFA"
    space.number = "1"
    _apply_weighting(space, candidates)
    room.properties.ph.add_new_space(space)
    outcome.space = space
    return outcome


def _extrude(candidates: list[_Candidate], room: Any, outcome: Outcome) -> Any | None:
    """`Space.from_room` on a throwaway Room, dropping whichever face honeybee names.

    ⚠ **One face must never cost the room.** `Space.from_room` raises for the *whole* room, so the
    first run lost all 40 of Adelphi's TFA faces to the 2 that were actually at fault. The pre-filter
    now uses honeybee's own predicate, so this loop should not fire at all — but the extrusion has
    failure modes the filter cannot see (a sliver that will not close into a solid, for one, and
    Adelphi contains a 1.7 cm² triangle with two vertices 0.42 mm apart), and every one of them names
    its face. Bounded by construction: each pass drops exactly one candidate.
    """
    from honeybee.face import Face
    from honeybee.facetype import face_types
    from honeybee.room import Room
    from honeybee_ph.space import Space

    while candidates:
        # A throwaway Room, from **fresh Faces**: `Room.__init__` re-parents whatever it is given,
        # so handing it the real Room's faces would silently steal them. Floor type is set
        # explicitly because `from_room` reads `room.floors`, and these are group-1 by definition.
        scratch = Room(
            f"{room.identifier}_tfa_scratch"[:100],
            [Face(candidate.identifier, candidate.geometry, face_types.floor) for candidate in candidates],
        )
        try:
            return Space.from_room(scratch, outcome.ceiling_height_m)
        except (ValueError, AssertionError) as error:
            refused = _refused(error, candidates)
            if refused is None:
                # Unattributable: honeybee refused without naming a face, so there is nothing to
                # drop and nothing to guess. Every candidate is reported lost.
                outcome.notes.append(f"Space.from_room refused the TFA faces: {error}")
                for candidate in candidates:
                    outcome.not_derived.append((candidate.record.id, f"Space.from_room raised: {error}"))
                    outcome.lost_m2 += candidate.area
                candidates.clear()
                return None
            candidates.remove(refused)
            outcome.not_derived.append((refused.record.id, f"Space.from_room refused this face: {error}"))
            outcome.lost_m2 += refused.area

    outcome.notes.append("every TFA face was refused individually; no Space derived")
    return None


def _apply_weighting(space: Any, candidates: list[_Candidate]) -> None:
    """Carry each face's `TFA_rf` onto the space's floor segments.

    Matching is by **area**, because `Space.from_room` builds its own segments and does not carry
    our identifiers through. A face whose area matches nothing keeps the default 1.0 — which is the
    same answer as an absent `TFA_rf`, so nothing is lost by the fallback.
    """
    factors = {round(candidate.area, 4): weighting_factor(candidate.record) for candidate in candidates}
    for volume in space.volumes:
        for segment in volume.floor.floor_segments:
            segment.weighting_factor = factors.get(round(segment.floor_area, 4), 1.0)
