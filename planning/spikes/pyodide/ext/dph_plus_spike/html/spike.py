"""Phase 3 — the Python half of the Pyodide spike.

This module is the *only* Python in the spike, and it is deliberately host-agnostic: it is byte-for-byte
the same file whether it runs inside SketchUp's `HtmlDialog`, inside desktop Chrome via
`harness/harness.html`, or on plain CPython via `python -m spike`. That is the point. If a step
passes in Chrome and fails in SketchUp, the difference is the host, not this code — which is the one
distinction the phase exists to make.

Nothing here touches the DOM, `js`, `pyodide` or the filesystem. Every entry point takes plain data
and returns a JSON-safe `dict`, so the JS side never has to reach into a Python object.

Steps, matching `planning/PHASE-3_pyodide-spike.md`:

    step2_import_stack()          — import honeybee + honeybee-ph, timing each module
    step3_build_demo_model()      — a Room from a hard-coded box + one PH Space, round-tripped
    step4_build_model_from_faces()— the same, from face vertices handed across the Ruby↔JS bridge

Run on CPython for a library-level control (Phase 2 already did this; it is here so a failure in the
browser can be bisected in one command):

    .venv/bin/python planning/spikes/pyodide/ext/dph_plus_spike/html/spike.py
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
import json
import platform
import sys
import time
from typing import Any

#: The import order the spike times. `honeybee_ph` must come last: importing it runs the
#: `_extend_honeybee_ph` hooks that graft `.properties.ph` onto honeybee's own classes, so it is the
#: only import whose cost includes the monkey-patching that HBJSON round-tripping depends on.
IMPORT_SEQUENCE: tuple[str, ...] = (
    "ladybug_geometry.geometry3d.pointvector",
    "ladybug.location",
    "honeybee.room",
    "honeybee.model",
    "honeybee_energy.lib.constructionsets",
    "honeybee_ph.space",
    "honeybee_ph",
)

#: designPH area group → the attribute name of a honeybee face type on `honeybee.facetype.face_types`.
#: Area groups are PHPP Areas-worksheet rows and are the only classification designPH stores, so they
#: are what v1 will have to translate from. Groups absent here (2–7 windows, 15–17 thermal bridges)
#: are not faces and never reach this map; anything unmapped is left to honeybee's own tilt-based
#: auto-assignment. See `00_Context/DESIGNPH_DATA_MODEL.md` §5 and `bt_inspector`'s AREA_GROUPS.
#:
#: Names, not objects: `honeybee.face.Face` rejects a plain string with
#: `AssertionError: Wall is not a valid face type`, and this module must stay importable without
#: honeybee on the path (the CPython control run imports it before the wheels exist).
AREA_GROUP_FACE_TYPE: dict[int, str] = {
    1: "floor",  # Treated Floor Area
    8: "wall",  # External Wall - Ambient
    9: "wall",  # External Wall - Ground
    10: "roof_ceiling",  # Roof/Ceiling - Ambient
    11: "floor",  # Floor slab / Basement ceiling
}


class Timer:
    """Accumulates named wall-clock spans into a JSON-safe `dict` of milliseconds."""

    def __init__(self) -> None:
        self.spans: dict[str, float] = {}

    def time(self, label: str, action: Any) -> Any:
        start = time.perf_counter()
        try:
            return action()
        finally:
            self.spans[label] = round((time.perf_counter() - start) * 1000, 1)

    @property
    def total_ms(self) -> float:
        return round(sum(self.spans.values()), 1)


def runtime_info() -> dict[str, Any]:
    """Identify the interpreter, so a result file says *what* it was measured on."""
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "is_pyodide": sys.platform == "emscripten",
    }


# --------------------------------------------------------------------------------------------------
# Step 2 — the stack imports
# --------------------------------------------------------------------------------------------------


def step2_import_stack() -> dict[str, Any]:
    """Import the eight-wheel stack, timing each module, and report package versions.

    A failure here is reported rather than raised: the phase needs to know *which* import broke and
    with what message, and an exception crossing the Pyodide boundary loses the traceback.
    """
    timer = Timer()
    failed: dict[str, str] = {}
    for module in IMPORT_SEQUENCE:
        try:
            timer.time(module, lambda m=module: importlib.import_module(m))
        except Exception as error:  # noqa: BLE001 — reporting, not handling
            failed[module] = f"{type(error).__name__}: {error}"
            break

    # Read versions from installed dist-info, not from `__version__` — the ladybug/honeybee
    # packages do not define that attribute, and the point of the check is to prove *which* wheel
    # micropip actually put on the path.
    versions: dict[str, str] = {}
    for distribution in (
        "honeybee-core",
        "honeybee-energy",
        "honeybee-ph",
        "honeybee-standards",
        "ladybug-core",
        "ladybug-geometry",
        "ladybug-geometry-polyskel",
        "ph-units",
    ):
        try:
            versions[distribution] = metadata.version(distribution)
        except Exception:  # noqa: BLE001 — absence is the finding, not an error to raise
            versions[distribution] = "not installed"

    return {
        "ok": not failed,
        "failed": failed,
        "import_ms": timer.spans,
        "import_total_ms": timer.total_ms,
        "versions": versions,
        "runtime": runtime_info(),
    }


# --------------------------------------------------------------------------------------------------
# Steps 3 and 4 — build a model
# --------------------------------------------------------------------------------------------------


def _attach_ph_space(hb_room: Any, avg_ceiling_height: float) -> dict[str, Any]:
    """Give `hb_room` one PH `Space` derived from its own Floor faces.

    `Space.from_room` deliberately does not attach itself, so the caller does — which is also the
    step that proves `honeybee_ph`'s `_extend_` hooks actually landed on honeybee's `Room`.

    A Room with no Floor faces is a **normal outcome**, not an error: designPH area groups 1 and 11
    are the only ones that become floors, and a model whose classified faces are all walls and roof
    has nothing to derive a Space from. `Space.from_room` raises `ValueError` in that case, so it is
    caught and reported — hard rule 4, report rather than fail.
    """
    from honeybee_ph.space import Space

    try:
        space = Space.from_room(hb_room, avg_ceiling_height)
    except ValueError as error:
        return {"volumes": 0, "skipped": f"{type(error).__name__}: {error}"}

    space.name = "Spike Space"
    space.number = "101"
    hb_room.properties.ph.add_new_space(space)  # type: ignore[attr-defined]
    return {"volumes": len(space.volumes)}


def _finish(hb_room: Any, model_id: str, timer: Timer, extra: dict[str, Any]) -> dict[str, Any]:
    """Wrap one `Room` in a `Model`, serialise it, and round-trip it back.

    The round-trip is the actual assertion. `to_dict()` succeeding proves only that honeybee could
    write something; `Model.from_dict` succeeding proves the PH properties survived, which is the
    thing that would break if `_extend_honeybee_ph` had not run.
    """
    from honeybee.model import Model

    model = timer.time("Model()", lambda: Model(model_id, rooms=[hb_room], units="Meters"))
    model_dict = timer.time("to_dict", model.to_dict)
    payload = timer.time("json.dumps", lambda: json.dumps(model_dict))

    round_trip: dict[str, Any] = {"ok": False}
    try:
        reloaded = timer.time("from_dict", lambda: Model.from_dict(json.loads(payload)))
        round_trip = {
            "ok": True,
            "rooms": len(reloaded.rooms),
            "faces": len(reloaded.faces),
            "apertures": len(reloaded.apertures),
            "spaces": len(reloaded.rooms[0].properties.ph.spaces),  # 0 when no Floor face existed
        }
    except Exception as error:  # noqa: BLE001 — reporting, not handling
        round_trip = {"ok": False, "error": f"{type(error).__name__}: {error}"}

    return {
        "ok": round_trip["ok"],
        "hbjson": payload,
        "hbjson_bytes": len(payload.encode("utf-8")),
        "counts": {
            "rooms": len(model.rooms),
            "faces": len(hb_room.faces),
            "floor_area_m2": round(hb_room.floor_area, 3),
            "volume_m3": round(hb_room.volume, 3),
        },
        "round_trip": round_trip,
        "build_ms": timer.spans,
        "build_total_ms": timer.total_ms,
        **extra,
    }


def step3_build_demo_model(width: float = 6.0, depth: float = 9.0, height: float = 3.0) -> dict[str, Any]:
    """A single `Room.from_box` plus one PH `Space` — the smallest real model the stack can make.

    Phase 2 ran exactly this shape on CPython 3.14 and it round-tripped, so a failure here is a
    Pyodide failure, not a library one (Phase 3 plan, step 3).
    """
    from honeybee.room import Room

    timer = Timer()
    hb_room = timer.time(
        "Room.from_box",
        lambda: Room.from_box("Spike_Room", width, depth, height),
    )
    space = timer.time("Space.from_room", lambda: _attach_ph_space(hb_room, height))
    return _finish(hb_room, "Spike_Demo_Model", timer, {"ph_space": space})


def step4_build_model_from_faces(payload: dict[str, Any]) -> dict[str, Any]:
    """Build one non-solid `Room` from face vertices collected in Ruby.

    `payload` is what the bridge carries — see `main.rb`'s `collect_designph_faces`:

        {"model_name": str,
         "units": "Meters",
         "faces": [{"id": str, "area_group": int|str|None, "vertices": [[x, y, z], ...]}, ...]}

    One non-solid Room is the v1 output shape by design (PRD §8.1); this is not trying to solve
    adjacency. Faces that cannot be turned into geometry are **named in the report**, never dropped
    silently — hard rule 4.
    """
    from honeybee.face import Face
    from honeybee.facetype import face_types
    from honeybee.room import Room
    from ladybug_geometry.geometry3d.face import Face3D
    from ladybug_geometry.geometry3d.pointvector import Point3D

    timer = Timer()
    faces_in = payload.get("faces") or []
    hb_faces: list[Any] = []
    rejected: list[dict[str, Any]] = []

    def build_faces() -> None:
        for index, record in enumerate(faces_in):
            identifier = str(record.get("id") or f"face_{index}")
            vertices = record.get("vertices") or []
            if len(vertices) < 3:
                rejected.append({"id": identifier, "reason": f"only {len(vertices)} vertices"})
                continue
            # Type-check every attribute read — `areaGroupID` is a String on most faces in a real
            # model (hard rule 5, `DESIGNPH_DATA_MODEL.md` §5.4).
            raw_group = record.get("area_group")
            try:
                group = int(raw_group)
            except (TypeError, ValueError):
                group = -1
            face_type_name = AREA_GROUP_FACE_TYPE.get(group)
            face_type = getattr(face_types, face_type_name) if face_type_name else None
            try:
                geometry = Face3D([Point3D(*point) for point in vertices])
                hb_faces.append(Face(identifier, geometry, face_type))
            except Exception as error:  # noqa: BLE001 — reporting, not handling
                rejected.append({"id": identifier, "reason": f"{type(error).__name__}: {error}"})

    timer.time("Face3D+Face", build_faces)
    if not hb_faces:
        return {
            "ok": False,
            "error": "no face survived translation",
            "faces_in": len(faces_in),
            "rejected": rejected[:25],
            "rejected_count": len(rejected),
        }

    hb_room = timer.time("Room()", lambda: Room("Spike_designPH_Room", hb_faces))
    space = timer.time("Space.from_room", lambda: _attach_ph_space(hb_room, 2.5))
    result = _finish(
        hb_room,
        str(payload.get("model_name") or "Spike_designPH_Model"),
        timer,
        {
            "ph_space": space,
            "faces_in": len(faces_in),
            "faces_translated": len(hb_faces),
            "rejected": rejected[:25],
            "rejected_count": len(rejected),
        },
    )
    # A non-solid Room is expected here (PRD §8.1); record it rather than treating it as failure.
    result["is_solid"] = bool(hb_room.geometry.is_solid)
    return result


def run_all(face_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run steps 2–4 in order and return one result document."""
    result: dict[str, Any] = {"step2": step2_import_stack()}
    if result["step2"]["ok"]:
        result["step3"] = step3_build_demo_model()
        if face_payload:
            result["step4"] = step4_build_model_from_faces(face_payload)
    return result


def _synthetic_payload(count: int) -> dict[str, Any]:
    """Mirror of `harness.html`'s `syntheticFaces()`, for the CPython control run only.

    The two exist separately on purpose: the browser needs its copy on the *JS* side so that step 4
    measures a payload actually crossing into Python, which is what the Ruby bridge will do. This
    one exists so the same work can be timed on CPython and the Pyodide slowdown factor stated as a
    number instead of guessed at. Keep them in step.
    """
    groups = [8, 8, 8, 10, 11, 1]
    faces = []
    for index in range(count):
        x, y = (index % 40) * 3.0, (index // 40) * 3.0
        z = (index % 7) * 0.5
        group: Any = groups[index % len(groups)]
        faces.append(
            {
                "id": f"synthetic_face_{index}",
                "area_group": str(group) if index % 3 == 0 else group,
                "vertices": [[x, y, z], [x + 2.8, y, z], [x + 2.8, y + 2.8, z], [x, y + 2.8, z]],
            }
        )
    return {"model_name": "Synthetic_Adelphi_Scale", "units": "Meters", "faces": faces}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CPython control run for the Pyodide spike")
    parser.add_argument("--faces", type=int, default=0, help="run step 4 on N synthetic faces")
    options = parser.parse_args()

    # Keeps the HBJSON out of stdout — only the verdict and the timings are interesting here.
    outcome = run_all(_synthetic_payload(options.faces) if options.faces else None)
    for data in outcome.values():
        data.pop("hbjson", None)
        data.pop("rejected", None)
    print(json.dumps(outcome, indent=2))
