"""DesignPH-PLUS POC -- the Python entry surface inside Pyodide.

Two jobs, and deliberately no more:

    import_stack()  -- import the 8-wheel stack in the ONE order that works, timing each module
    self_test()     -- prove the runtime can build and round-trip a model, and that the translator
                       seam is reachable

Everything the POC actually translates lives in the `dph_translator` package, which is unpacked
into site-packages beside the wheels. This module never imports it at module scope: the whole point
of `import_stack` is that the import ORDER is controlled and measured.

Both entry points return a **JSON string**, not a dict. `app.js` evaluates the call and parses the
text, so nothing but plain data crosses the wasm boundary -- no proxies to leak, and the same
serialisation format all the way out to Ruby.

Targets CPython 3.11 (Pyodide 0.24.1). Runs unmodified on native CPython 3.11 too, which is what
makes a failure attributable to the host rather than to the code.
"""

from __future__ import annotations

import importlib
import importlib.metadata as metadata
import json
import platform
import sys
import time
from collections.abc import Callable
from typing import Any

#: The import order. `honeybee_ph` **must come last**: importing it runs the `_extend_honeybee_ph`
#: hooks that graft `.properties.ph` onto honeybee's own classes, so anything imported after it
#: would be measuring a different runtime from the one the translator uses.
IMPORT_SEQUENCE: tuple[str, ...] = (
    "ladybug_geometry.geometry3d.pointvector",
    "ladybug.location",
    "honeybee.room",
    "honeybee.model",
    "honeybee_energy.lib.constructionsets",
    "honeybee_ph.space",
    "honeybee_ph",
)

#: Distributions whose versions are reported. Read from installed dist-info rather than a
#: `__version__` attribute -- the ladybug/honeybee packages do not define one, and the point of the
#: check is to prove *which* wheel actually landed on the path.
DISTRIBUTIONS: tuple[str, ...] = (
    "honeybee-core",
    "honeybee-energy",
    "honeybee-ph",
    "honeybee-standards",
    "ladybug-core",
    "ladybug-geometry",
    "ladybug-geometry-polyskel",
    "ph-units",
)


class Timer:
    """Accumulates named wall-clock spans into a JSON-safe dict of milliseconds."""

    def __init__(self) -> None:
        self.spans: dict[str, float] = {}

    def time(self, label: str, action: Callable[[], Any]) -> Any:
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


#: The first `import_stack()` result, memoised. `app.js` calls it once during boot and `self_test`
#: reports on it afterwards; without this the second call re-times *cached* imports and reports
#: 0.0 ms, which reads as "the stack imported instantly" rather than "this is not a measurement".
_IMPORT_RESULT: str | None = None


def import_stack() -> str:
    """Import the stack in `IMPORT_SEQUENCE` order, timing each module.

    Only the **first** call measures anything; later calls replay that result (see `_IMPORT_RESULT`).

    A failure is reported rather than raised: the caller needs to know *which* import broke and
    with what message, and an exception crossing the Pyodide boundary loses its traceback.
    """
    global _IMPORT_RESULT
    if _IMPORT_RESULT is not None:
        return _IMPORT_RESULT

    timer = Timer()
    failed: dict[str, str] = {}
    for module in IMPORT_SEQUENCE:
        try:
            timer.time(module, lambda m=module: importlib.import_module(m))
        except Exception as error:  # noqa: BLE001 -- reporting, not handling
            failed[module] = f"{type(error).__name__}: {error}"
            break

    versions: dict[str, str] = {}
    for distribution in DISTRIBUTIONS:
        try:
            versions[distribution] = metadata.version(distribution)
        except Exception:  # noqa: BLE001 -- absence is the finding, not an error to raise
            versions[distribution] = "not installed"

    _IMPORT_RESULT = json.dumps(
        {
            "ok": not failed,
            "failed": failed,
            "import_ms": timer.spans,
            "import_total_ms": timer.total_ms,
            "versions": versions,
            "runtime": runtime_info(),
        }
    )
    return _IMPORT_RESULT


#: The smallest payload that exercises the translator seam: one horizontal face, one classified
#: area group. Not evidence about anything -- it proves the entry point is reachable and returns
#: the agreed shape, nothing more.
_SEAM_PROBE: dict[str, Any] = {
    "contract_version": 2,
    "generated_by": "boot.self_test",
    "model": {"file_name": "self_test"},
    "faces": [
        {
            "id": "self_test_floor",
            "area_group": 1,
            "outer_loop": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0]],
        }
    ],
}


def _round_trip_demo_model() -> dict[str, Any]:
    """`Room.from_box` out to HBJSON and back.

    `to_dict()` succeeding proves only that honeybee could write something. `Model.from_dict`
    succeeding proves the PH properties survived, which is the thing that would break if
    `_extend_honeybee_ph` had not run -- so the round trip is the actual assertion.
    """
    from honeybee.model import Model
    from honeybee.room import Room

    timer = Timer()
    room = timer.time("Room.from_box", lambda: Room.from_box("POC_Self_Test", 6.0, 9.0, 3.0))
    model = timer.time("Model()", lambda: Model("POC_Self_Test", rooms=[room], units="Meters"))
    payload = timer.time("to_dict+dumps", lambda: json.dumps(model.to_dict()))
    reloaded = timer.time("from_dict", lambda: Model.from_dict(json.loads(payload)))
    return {
        "ok": True,
        "rooms": len(reloaded.rooms),
        "faces": len(reloaded.faces),
        "hbjson_bytes": len(payload.encode("utf-8")),
        "build_ms": timer.spans,
    }


def _translator_seam() -> dict[str, Any]:
    """Prove `dph_translator.entry.translate_json` is importable and honours its contract."""
    import dph_translator.entry as entry

    result = json.loads(entry.translate_json(json.dumps(_SEAM_PROBE)))
    missing = [key for key in ("hbjson", "report", "verdict") if key not in result]
    return {
        "ok": not missing,
        "missing_keys": missing,
        "version": getattr(entry, "__version__", "unknown"),
        "hbjson_bytes": len(str(result.get("hbjson", "")).encode("utf-8")),
    }


def self_test() -> str:
    """Boot checks, as one verdict document. Returns a JSON string."""
    # The verdict shape is `dph_translator.report`'s to define -- the banner, the message box and
    # the Chromium harness all render it. Building it by hand here would put a second, unenforced
    # implementation inside the same `.rbz`. Imported late: the translator is unpacked into
    # site-packages during boot, after this module is written to the filesystem.
    from dph_translator.report import verdict

    steps: dict[str, Any] = {"imports": json.loads(import_stack())}
    if steps["imports"]["ok"]:
        for name, action in (
            ("model_round_trip", _round_trip_demo_model),
            ("translator_seam", _translator_seam),
        ):
            try:
                steps[name] = action()
            except Exception as error:  # noqa: BLE001 -- reporting, not handling
                steps[name] = {"ok": False, "error": f"{type(error).__name__}: {error}"}

    round_trip = steps.get("model_round_trip", {})
    seam = steps.get("translator_seam", {})
    return json.dumps(
        {
            "steps": steps,
            "verdict": verdict(
                [
                    (
                        "stack imports",
                        steps["imports"]["ok"],
                        "{} ms".format(steps["imports"]["import_total_ms"]),
                    ),
                    (
                        "builds and reloads a model",
                        bool(round_trip.get("ok")),
                        str(round_trip.get("error", "")),
                    ),
                    ("translator seam reachable", bool(seam.get("ok")), str(seam.get("error", ""))),
                ]
            ),
        }
    )


if __name__ == "__main__":
    # Native CPython control run: same code path, a host that is not a browser.
    print(self_test())
