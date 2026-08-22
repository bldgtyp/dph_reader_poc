"""Orchestration: a parsed extraction → one honeybee `Model`, a report, and a verdict.

The order below is not arbitrary — each step depends on the one before:

1. **faces** → typed, boundary-conditioned, constructed (§3, §5)
2. **apertures** onto those faces (§4) — needs the faces, and the boundary conditions decide whether
   a host will accept one at all
3. one **`Room`** from the faces — a Room takes ownership, so nothing may touch a face afterwards
   without going through the Room
4. **thermal bridges** onto the Room's building segment (§6) — needs the Room
5. **spaces / TFA** (§7) — needs the Room and the group-1 faces
6. **site** (§8) — needs the `Model`

Three constraints hold throughout:

* **One non-solid `Room`, by design** (PRD §8.1). No adjacency solving, no watertight repair.
* **Never call `Model.from_dict` here.** ~100× the cost of writing — 36 s for 1441 faces on
  Chromium 88 — and this is a UI path (`HONEYBEE_STACK.md` §5).
* honeybee is imported **inside** functions. `boot.py` owns the import order (`honeybee_ph` last,
  for its `_extend_` hooks), and this module stays importable without the stack so the contract
  layer can be unit-tested on its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from . import HBJSON_SCHEMA_VERSION, __version__, apertures, bridges, constructions, facetypes, site, spaces
from .contract import Extraction, FaceRecord
from .report import OMITTED, SHADING_MARKER, TRANSLATED, WITH_NOTES, Report, verdict

#: `Face3D.area` against the collector's SketchUp-computed `area_m2`. A disagreement is almost
#: always a transform bug, which is exactly what this cross-check exists to catch.
AREA_TOLERANCE = 0.01

#: honeybee truncates identifiers at 100 characters, silently, and the contract's ids are
#: path-qualified and long. See `HONEYBEE_STACK.md` §4.
HONEYBEE_IDENTIFIER_MAX = 100


@dataclass(frozen=True)
class Translation:
    """What one run produces. `entry.translate_json` serialises exactly these three keys."""

    hbjson: str
    report: dict[str, Any]
    verdict: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"hbjson": self.hbjson, "report": self.report, "verdict": self.verdict}


def identifier(text: str) -> str:
    """honeybee's own rule, not a local copy of half of it.

    `honeybee.typing.valid_string` is *asserted* in every identifier setter, so the character class
    and the 100-character cap are not ours to redefine. A hand-rolled sanitiser matching only the
    character class lets a long name raise `AssertionError` from inside `Room()` — outside every
    per-entity guard, so the run dies with nothing named.
    """
    from honeybee.typing import clean_string

    return clean_string(text)


# ------------------------------------------------------------------------------------------------
# Faces
# ------------------------------------------------------------------------------------------------


def _build_face(record: FaceRecord, extraction: Extraction, report: Report) -> Any | None:
    """One contract face record → one honeybee `Face`, or `None` with a report entry saying why."""
    from honeybee.face import Face
    from ladybug_geometry.geometry3d.face import Face3D
    from ladybug_geometry.geometry3d.pointvector import Point3D

    if record.error is not None:
        report.add(record.id, "face", OMITTED, record.error)
        return None
    if len(record.outer_loop) < 3:
        report.add(record.id, "face", OMITTED, f"outer loop has {len(record.outer_loop)} points")
        return None

    group = record.area_group_int
    notes: list[str] = []

    if group in facetypes.WINDOW_GROUPS:
        report.add(record.id, "face", OMITTED, f"area group {group} is an aperture, not a face")
        return None
    if group in facetypes.BRIDGE_GROUPS:
        # Groups 15/16/17 are lengths on edges. A face carrying one means the collector filed a
        # record in the wrong list, which is a bug worth seeing rather than translating around.
        report.add(record.id, "face", OMITTED, f"area group {group} is a thermal bridge, not a face")
        return None

    mapping = facetypes.mapping_for(group)
    if mapping is None:
        notes.append(f"area group {record.area_group!r} has no mapping; honeybee assigns by tilt")
    elif mapping.note:
        notes.append(mapping.note)

    conflict = facetypes.zone_conflict(group, record.temp_zone)
    if conflict:
        # The free integrity check: `tempZone` is derived from the area group by PHPP's own table,
        # so a contradicting pair means the model is inconsistent. Report; never resolve.
        notes.append(conflict)
    if record.both_generations:
        notes.append(f"both *ID and *Auto carry values for: {', '.join(record.both_generations)}")

    try:
        boundary = [Point3D(*point) for point in record.outer_loop]
        holes = [[Point3D(*point) for point in loop] for loop in record.inner_loops] or None
        geometry = Face3D(boundary, holes=holes)
        face_type = facetypes.face_type_object(mapping.face_type if mapping else None)
        geometry, orientation = _orient(geometry, mapping.face_type if mapping else None)
        notes.extend(orientation)
        face = Face(identifier(record.id), geometry, face_type)
        boundary_condition = facetypes.boundary_object(mapping.boundary if mapping else None)
        if boundary_condition is not None:
            face.boundary_condition = boundary_condition
    except Exception as error:  # noqa: BLE001 -- reporting, not handling
        report.add(record.id, "face", OMITTED, f"{type(error).__name__}: {error}")
        return None

    face.display_name = record.desc_name or record.id
    notes.extend(_apply_construction(face, record, extraction, report))
    notes.extend(_degeneracies(geometry))

    if record.area_m2:
        difference = abs(geometry.area - record.area_m2)
        if difference / max(record.area_m2, 1e-9) > AREA_TOLERANCE:
            notes.append(
                f"area {round(geometry.area, 3)} m² disagrees with the collector's "
                f"{record.area_m2} m² — usually a transform bug"
            )

    report.add(
        record.id,
        "face",
        WITH_NOTES if notes else TRANSLATED,
        "; ".join(notes) or None,
        area_group=record.area_group,
        face_type=str(face.type),
        boundary_condition=str(face.boundary_condition),
    )
    return face


def _orient(geometry: Any, face_type: str | None) -> tuple[Any, list[str]]:
    """Wind the geometry to match the face type designPH's area group already decided.

    ⚠ honeybee's convention is that a `Floor` normal points **down** and a `RoofCeiling` normal
    points **up**; designPH's TFA faces are wound the other way, so `ValidateModel` rejected **40 of
    Adelphi's 41 Floors** as *"an upward-pointing Floor, which should be changed to a RoofCeiling"*.

    That is a genuine convention clash rather than a defect, and the resolution direction matters.
    The **area group is authoritative about what the surface is** (`DATA_CONTRACTS.md` §4.1) — it is
    PHPP's own classification, read from the model. honeybee is *inferring* type from geometry.
    Letting it win would quietly re-file a TFA marker as roof; flipping the winding keeps the
    classification and changes only the thing that carries no PHPP meaning. Reported either way.

    Nothing here touches an untyped face: with `face_type=None` honeybee assigns by tilt, and
    flipping the geometry first would change the answer it gives.
    """
    upward = geometry.normal.z > 0
    if face_type == "floor" and upward:
        return geometry.flip(), [
            "geometry flipped normal-down to match its Floor type (designPH winds TFA and slab faces up)"
        ]
    if face_type == "roof_ceiling" and not upward:
        return geometry.flip(), ["geometry flipped normal-up to match its RoofCeiling type"]
    return geometry, []


#: Two vertices closer than this are a degenerate edge. 1 mm — below any modelling intent, and
#: Adelphi's sliver triangle has a pair 0.42 mm apart.
DEGENERATE_EDGE_M = 0.001

#: A face smaller than this is a sliver rather than an envelope surface. 10 cm²; Adelphi's is 1.7.
SLIVER_AREA_M2 = 0.001


def _degeneracies(geometry: Any) -> list[str]:
    """Name the degenerate geometry a real designPH model contains. **Report, never repair.**

    Adelphi carries a 1.7 cm² sliver triangle and a 7-point face with a zero-width spur (two
    identical vertices with an 0.8 m out-and-back between them). Neither is a translator defect and
    neither is dropped: a classified face that vanished would break the one number a reader checks
    first, *82 of 82*, and 1.7 cm² changes no area total. But a translator has to **decide** about
    them rather than discover them at the far end of the pipeline, and the decision here is the
    house rule — carry the face, name the geometry, repair nothing (PRD §8.1, `DESIGNPH_DATA_MODEL`
    §8.6.2). The one exception is the TFA extrusion, which cannot proceed on them; `spaces` names
    what it drops.
    """
    notes: list[str] = []
    if geometry.area < SLIVER_AREA_M2:
        notes.append(f"degenerate: {geometry.area * 10000:.2f} cm² sliver, carried unrepaired")

    boundary = list(geometry.boundary)
    count = len(boundary)
    short = sum(
        1
        for index, point in enumerate(boundary)
        if point.distance_to_point(boundary[(index + 1) % count]) < DEGENERATE_EDGE_M
    )
    if short:
        notes.append(
            f"degenerate: {short} boundary edge(s) shorter than {DEGENERATE_EDGE_M * 1000:.0f} mm, "
            "carried unrepaired"
        )
    # ⚠ A *non-adjacent* coincident pair is the other shape real data takes, and short edges do not
    # find it: Adelphi's `face_3281_1710` has 7 points where vertices 2 and 4 are the same point
    # and vertex 3 runs 0.8 m out and straight back. Every edge of that spur is long.
    revisits = sum(
        1
        for index in range(count)
        for other in range(index + 2, count)
        if not (index == 0 and other == count - 1)
        and boundary[index].distance_to_point(boundary[other]) < DEGENERATE_EDGE_M
    )
    if revisits:
        notes.append(
            f"degenerate: the boundary revisits {revisits} point(s) — a zero-width spur or a "
            "self-touching loop, carried unrepaired"
        )
    return notes


def _apply_construction(face: Any, record: FaceRecord, extraction: Extraction, report: Report) -> list[str]:
    """Resolve the face's assembly and record which tier it came from."""
    resolution = constructions.resolve(extraction, record.assembly_ref)
    report.add(
        record.id,
        "assembly",
        TRANSLATED if resolution.construction is not None else OMITTED,
        resolution.detail,
        tier=resolution.tier,
        assembly_ref=record.assembly_ref,
        u_value=constructions.u_value_of(resolution),
        ph_values=resolution.ph_values or None,
    )
    if resolution.construction is None:
        # The face keeps honeybee's default construction. **Never substitute a plausible one** —
        # a fabricated U-value is indistinguishable from a real one downstream.
        return [f"no construction: {resolution.detail}"]
    face.properties.energy.construction = resolution.construction
    return []


# ------------------------------------------------------------------------------------------------
# The run
# ------------------------------------------------------------------------------------------------


def translate(extraction: Extraction) -> Translation:
    """Translate a parsed extraction into HBJSON plus a report and a verdict."""
    from honeybee.model import Model
    from honeybee.room import Room

    report = Report()
    faces: dict[str, Any] = {}
    tfa_faces: list[tuple[FaceRecord, Any]] = []

    for record in extraction.faces:
        face = _build_face(record, extraction, report)
        if face is None:
            continue
        faces[record.id] = face
        if record.area_group_int == spaces.TFA_GROUP:
            tfa_faces.append((record, face))

    _report_collisions(faces, report)
    _translate_apertures(extraction, faces, report)

    room = None
    model = None
    hbjson = ""
    space_outcome = spaces.Outcome()
    site_record: dict[str, Any] = {}

    if faces:
        model_name = identifier(extraction.model.file_name)
        # A `Room` takes ownership of its faces (it sets `face._parent`), so there is exactly one
        # per run and nothing may build a second from the same objects.
        room = Room(f"{model_name}_Room"[:HONEYBEE_IDENTIFIER_MAX], list(faces.values()))
        room.display_name = extraction.model.file_name
        _translate_bridges(extraction, room, report)
        space_outcome = spaces.derive(extraction, tfa_faces, room)
        _report_spaces(space_outcome, report)

        model = Model(model_name, rooms=[room], units="Meters")
        model.display_name = extraction.model.file_name
        site_record, site_notes = site.apply(model, extraction.model)
        for note in site_notes:
            report.note(note)
        hbjson = _serialise(model, report)
    else:
        report.note("no face translated, so no Room and no Model were built")
        for edge_record in extraction.edges:
            report.add(edge_record.id, "thermal_bridge", OMITTED, "no Room to attach a thermal bridge to")

    report.unclassified = _unclassified_block(extraction)
    report.summary = _summary(extraction, faces, report, space_outcome, site_record, hbjson)
    return Translation(hbjson=hbjson, report=report.to_dict(), verdict=_verdict(extraction, report, hbjson))


def _report_collisions(faces: dict[str, Any], report: Report) -> None:
    """Two faces cannot share an identifier — and honeybee truncates at 100 characters silently,
    which the contract's path-qualified ids are long enough to hit."""
    seen: dict[str, list[str]] = {}
    for record_id, face in faces.items():
        seen.setdefault(face.identifier, []).append(record_id)
    for cleaned, sources in seen.items():
        if len(sources) > 1:
            report.add(
                cleaned,
                "identifier_collision",
                OMITTED,
                f"{len(sources)} faces clean to one identifier "
                f"(honeybee truncates at {HONEYBEE_IDENTIFIER_MAX} characters)",
                sources=sources,
            )


def _translate_apertures(extraction: Extraction, faces: dict[str, Any], report: Report) -> None:
    for record in extraction.windows:
        if record.host_resolution != "glued_to" or record.host_face_id is None:
            report.add(
                record.id,
                "aperture",
                OMITTED,
                "no host: `glued_to` did not resolve",
                designph_name=record.designph_name,
            )
            continue
        host = faces.get(record.host_face_id)
        if host is None:
            # Legal contract data (§4): the host may be an unclassified face, which never shipped
            # as geometry. Report, do not crash on the dangling join.
            report.add(
                record.id,
                "aperture",
                OMITTED,
                f"host {record.host_face_id} is not among the translated faces (unclassified host)",
                designph_name=record.designph_name,
            )
            continue

        aperture, outcome, detail = apertures.build(record, host, extraction.libraries)
        if aperture is None:
            report.add(record.id, "aperture", OMITTED, detail.pop("reason", None), **detail)
            continue
        attached, reason = apertures.attach(host, aperture)
        if not attached:
            report.add(record.id, "aperture", OMITTED, reason, **detail)
            continue
        report.add(record.id, "aperture", outcome, detail.pop("reason", None), **detail)


def _translate_bridges(extraction: Extraction, room: Any, report: Report) -> None:
    for record in extraction.edges:
        bridge, outcome, detail = bridges.build(record, extraction)
        if bridge is None:
            report.add(record.id, "thermal_bridge", OMITTED, detail.pop("reason", None), **detail)
            continue
        bridges.attach(room, bridge)
        report.add(record.id, "thermal_bridge", outcome, detail.pop("reason", None), **detail)


def _report_spaces(outcome: spaces.Outcome, report: Report) -> None:
    for face_id, reason in outcome.not_derived:
        report.add(face_id, "tfa", OMITTED, reason)
    # A face that contributed *after being changed* is not an omission and is not a clean pass
    # either. It gets its own line, because a repair nobody can see is a repair nobody can dispute.
    for face_id, reason in outcome.adjusted:
        report.add(face_id, "tfa", WITH_NOTES, reason)
    for note in outcome.notes:
        report.note(note)


def _unclassified_block(extraction: Extraction) -> dict[str, Any]:
    """Contract §6 passes through verbatim: every DesignPH-tagged omitted face is **named**."""
    return {
        "tagged_faces": [
            {"id": face.id, "area_group": face.area_group, "tag": face.tag}
            for face in extraction.unclassified
        ],
        "tagged_face_count": len(extraction.unclassified),
        "untagged_by_tag": dict(extraction.untagged_by_tag),
    }


def _serialise(model: Any, report: Report) -> str:
    """`Model.to_dict` → JSON, with the two stamps the raw output does not carry.

    * `version`: honeybee leaves it `null` because `honeybee-schema` is deliberately **not**
      installed (in this venv or in the Pyodide payload). Decision D-2 stamps the constant we
      validate against instead of inventing a lookup.
    * `user_data`: the shading disclosure travels **inside the HBJSON**, so the model cannot be
      passed on without it. Verified to survive `to_dict`/`from_dict` (decision D-3).
    """
    model.user_data = {
        "dph_plus": {
            "shading": SHADING_MARKER,
            "translator_version": __version__,
            "report": "see <name>.report.json",
        }
    }
    payload = model.to_dict()
    payload["version"] = HBJSON_SCHEMA_VERSION
    text: str = json.dumps(payload)
    report.note(f"HBJSON stamped as schema version {HBJSON_SCHEMA_VERSION}")
    return text


def _summary(
    extraction: Extraction,
    faces: dict[str, Any],
    report: Report,
    space_outcome: spaces.Outcome,
    site_record: dict[str, Any],
    hbjson: str,
) -> dict[str, Any]:
    tiers: dict[str, int] = {}
    for entry in report.entries:
        if entry.kind == "assembly":
            tier = str(entry.detail.get("tier"))
            tiers[tier] = tiers.get(tier, 0) + 1
    return {
        "translator_version": __version__,
        "hbjson_schema_version": HBJSON_SCHEMA_VERSION,
        "generated_by": extraction.generated_by,
        "model": extraction.model.file_name,
        "designph_versions": list(extraction.model.designph_versions),
        "faces": {
            "in": len(extraction.faces),
            "translated": len(faces),
            "reported": report.count("face", OMITTED),
        },
        "apertures": {
            "in": len(extraction.windows),
            "translated": report.count("aperture") - report.count("aperture", OMITTED),
            "reported": report.count("aperture", OMITTED),
        },
        "thermal_bridges": {
            "in": len(extraction.edges),
            "translated": report.count("thermal_bridge") - report.count("thermal_bridge", OMITTED),
            "reported": report.count("thermal_bridge", OMITTED),
        },
        "spaces": {
            "derived": 1 if space_outcome.space else 0,
            "ceiling_height_m": round(space_outcome.ceiling_height_m, 3),
        },
        # TFA is a headline number; its coverage is stated whether or not anything went wrong.
        "tfa_m2_covered": round(space_outcome.covered_m2, 3),
        "tfa_m2_lost": round(space_outcome.lost_m2, 3),
        "assembly_tiers": tiers,
        # designPH's own frame/glazing libraries, carried inline in the model. The entry counts are
        # here because "the library named 3 of 46 frame ids" is a different situation from "there is
        # no library", and only one of them is a reason to go looking for the CSVs.
        "libraries": {
            name: {"entries": len(library.names), "sources": library.sources}
            for name, library in sorted(extraction.libraries.items())
        },
        "tables_present": sorted(extraction.tables),
        "tables_undecodable": sorted(extraction.table_errors),
        "site": site_record,
        "collector_counts": dict(extraction.counts),
        "hbjson_bytes": len(hbjson.encode("utf-8")),
    }


def _verdict(extraction: Extraction, report: Report, hbjson: str) -> dict[str, Any]:
    """Grade it.

    A model designPH never classified is **not** a translator failure — POC-5 sweeps the corpus on
    these verdicts, and a legitimately empty model has to stay distinguishable from a broken run.
    What fails is an entity that should have translated and did not, and an identifier collision,
    which silently merges two envelope surfaces.
    """
    faces_in = len(extraction.faces)
    rejected = report.count("face", OMITTED)
    collisions = report.count("identifier_collision")
    checks = [
        (
            "classified faces translated",
            rejected == 0,
            f"{faces_in - rejected} of {faces_in}, {rejected} reported",
        ),
        ("model serialises", bool(hbjson) or not faces_in, f"{len(hbjson.encode('utf-8'))} bytes"),
        ("no identifier collision", collisions == 0, f"{collisions} collision(s)"),
        ("every entity accounted for", _complete(extraction, report), "report completeness"),
    ]
    return verdict(checks, omissions=report.has_omissions)


def _complete(extraction: Extraction, report: Report) -> bool:
    """The completeness invariant, as a check the run itself makes.

    Every face, edge and window must appear in `entries` exactly once. `tables` and `unclassified`
    are covered by the summary and the passthrough block, not by entries.
    """
    expected = {record.id for record in extraction.faces}
    expected |= {record.id for record in extraction.edges}
    expected |= {record.id for record in extraction.windows}
    seen = {entry.id for entry in report.entries if entry.kind in ("face", "aperture", "thermal_bridge")}
    return expected <= seen
