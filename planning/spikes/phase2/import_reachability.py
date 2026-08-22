# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Phase 2 — is an impure dependency actually *reachable*?

`purity_audit.py` answers the packaging question: what does the dependency metadata drag in.
This script answers the question that actually decides Phase 3's scope: **does anything on the
model-building path import it.**

The two answers differ sharply. `honeybee-core` hard-declares `honeybee-schema`, which drags
`pydantic` and its Rust `pydantic-core` — yet nothing outside `honeybee_energy/cli/` ever imports
it. `PHX` hard-declares `lxml` and `xlwings`, yet the whole HBJSON → PhxProject → WUFI/METr write
path imports neither. A metadata-only audit would have written both subtrees off.

Two passes, because either alone is weak evidence:

1. **Static** — unzip each wheel and record every import of a named impure module, tagged
   ``top-level`` (executes on import of that module) or ``guarded`` (inside a function, a class, or
   an ``if __name__`` block, so it executes only if that code path is called).
2. **Empirical** — install the pins into a throwaway venv with ``--no-deps`` so *none* of the impure
   packages exist, then run the real conversion. Anything genuinely required fails loudly with
   ``ModuleNotFoundError``; nothing is left to inference.

Usage:
    uv run planning/spikes/phase2/import_reachability.py \
        --md planning/RESULTS/PHASE-2_import-reachability.md
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

#: Where `purity_audit.py` writes the closure these pins came from. Checked at startup so the two
#: scripts cannot silently drift apart the next time the audit is re-run against newer releases.
CLOSURE_JSON = Path(__file__).resolve().parents[2] / "RESULTS" / "baselines" / "phase2_closure.json"

#: The Phase 2 closure, pinned to the versions the audit resolved. Deliberately explicit rather than
#: read from `CLOSURE_JSON`: the probe's whole value is that it installs these and *nothing else*, so
#: a resolver must not be allowed to add to the list. `check_pins_against_closure` keeps them honest.
PINS = [
    "honeybee-core==1.64.65",
    "honeybee-energy==1.123.23",
    "honeybee-ph==1.33.48",
    "honeybee-standards==2.0.7",
    "ladybug-core==0.44.56",
    "ladybug-geometry==1.35.3",
    "ladybug-geometry-polyskel==1.7.52",
    "ph-units==1.5.38",
    "PHX==1.56.88",
]

#: Everything in the closure that is not a pure wheel, plus the pure-but-unwanted extras that only
#: arrive as transitive baggage. If one of these is never imported, it never needs to ship.
IMPURE = [
    "appscript", "click", "honeybee_schema", "lxml", "numpy", "psutil",
    "pydantic", "pydantic_core", "pywin32", "rich", "win32com", "xlwings",
]

IMPORT_RE = re.compile(r"^(?P<indent>[ \t]*)(?:from\s+(?P<from>[\w.]+)\s+import|import\s+(?P<im>[\w.]+))")

#: Exercises the full v1-and-beyond write path: build a Honeybee model, attach the PH extension,
#: convert to a PhxProject, and emit both WUFI-Passive XML and METr JSON.
PROBE = r"""
import json, sys
from honeybee.model import Model
from honeybee.room import Room
import honeybee_ph  # registers the .ph property extension
from PHX.from_HBJSON import create_project
from PHX.to_METr_JSON import metr_builder
from PHX.to_WUFI_XML import xml_builder

model = Model("purity_probe", [Room.from_box("probe_room", 6, 4, 3)], units="Meters")
assert Model.from_dict(model.to_dict()).identifier == model.identifier, "HBJSON round-trip failed"

phx = create_project.convert_hb_model_to_PhxProject(model)
wufi = xml_builder.generate_WUFI_XML_from_object(phx)
metr = metr_builder.generate_metr_json_text(phx)
assert wufi.startswith("<?xml"), "WUFI XML did not start with a declaration"
assert isinstance(json.loads(metr), dict), "METr JSON did not parse as an object"

print(json.dumps({
    "python": sys.version.split()[0],
    "hbjson_faces": len(model.to_dict()["rooms"][0]["faces"]),
    "phx_variants": len(phx.variants),
    "wufi_xml_chars": len(wufi),
    "metr_json_chars": len(metr),
    "impure_modules_loaded": sorted(m for m in IMPURE_NAMES if m in sys.modules),
}))
"""


def check_pins_against_closure(pins: list[str], closure_json: Path) -> list[str]:
    """Return a human-readable list of disagreements between *pins* and the audit's resolved closure.

    Empty means they agree. A package the audit resolved but that is not pinned here is *not* a
    disagreement — the pins are deliberately the reachable subset, not the whole closure.
    """
    if not closure_json.exists():
        return [f"{closure_json.name} not found — run purity_audit.py first to cross-check the pins"]

    resolved = {
        name: pkg["version"]
        for name, pkg in json.loads(closure_json.read_text())["packages"].items()
    }
    problems = []
    for pin in pins:
        name, _, version = pin.partition("==")
        canonical = name.lower().replace("_", "-").replace(".", "-")
        if canonical not in resolved:
            problems.append(f"{name} is pinned here but absent from the resolved closure")
        elif resolved[canonical] != version:
            problems.append(f"{name}: pinned {version}, audit resolved {resolved[canonical]}")
    return problems


def scan_wheels(wheel_dir: Path, impure: list[str]) -> dict[str, dict[str, list[str]]]:
    """``{wheel: {"module:impure": ["top-level" | "guarded", ...]}}`` for every impure import found."""
    found: dict[str, dict[str, list[str]]] = {}
    for wheel in sorted(wheel_dir.glob("*.whl")):
        hits: dict[str, list[str]] = defaultdict(list)
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if not name.endswith(".py"):
                    continue
                source = archive.read(name).decode("utf-8", "replace")
                for line in source.splitlines():
                    match = IMPORT_RE.match(line)
                    if not match:
                        continue
                    module = (match["from"] or match["im"]).split(".")[0]
                    if module in impure:
                        kind = "top-level" if not match["indent"] else "guarded"
                        hits[f"{name}:{module}"].append(kind)
        found[wheel.name] = dict(hits)
    return found


def run_empirical_probe(pins: list[str], python_version: str) -> dict[str, object]:
    """Install *pins* with ``--no-deps`` into a throwaway venv and run the conversion probe there."""
    with tempfile.TemporaryDirectory() as tmp:
        venv = Path(tmp) / "venv"
        subprocess.run(["uv", "venv", "--python", python_version, str(venv)], check=True, capture_output=True)
        subprocess.run(
            ["uv", "pip", "install", "--python", str(venv), "--no-deps", "--quiet", *pins],
            check=True, capture_output=True, text=True,
        )
        script = Path(tmp) / "probe.py"
        script.write_text(f"IMPURE_NAMES = {IMPURE!r}\n" + PROBE)
        proc = subprocess.run(
            [str(venv / "bin" / "python"), str(script)],
            capture_output=True,
            text=True,
            check=False,  # a ModuleNotFoundError here IS the result, not an error to raise on
        )
    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[-2000:]}
    # honeybee prints defaulting notices to stdout; the probe's JSON is the last line.
    return {"ok": True, **json.loads(proc.stdout.strip().splitlines()[-1])}


def render_markdown(scan: dict[str, dict[str, list[str]]], probe: dict[str, object]) -> str:
    lines = [
        "# Phase 2 — impure-import reachability",
        "",
        ("Generated by [`planning/spikes/phase2/import_reachability.py`]"
         "(../spikes/phase2/import_reachability.py)."),
        "",
        "**`top-level`** executes when the module is imported. **`guarded`** sits inside a function,",
        "a class, or an `if __name__` block, and executes only if that path is called — so it is not",
        "a dependency of importing the package.",
        "",
        "## Static scan",
        "",
        "| Wheel | Module | Imports | Kind |",
        "|---|---|---|---|",
    ]
    for wheel, hits in scan.items():
        if not hits:
            lines.append(f"| `{wheel}` | — | — | ✅ no impure imports |")
            continue
        for key, kinds in sorted(hits.items()):
            path, _, module = key.rpartition(":")
            kind = "⚠ top-level" if "top-level" in kinds else "guarded"
            lines.append(f"| `{wheel}` | `{path}` | `{module}` × {len(kinds)} | {kind} |")

    lines += ["", "## Empirical probe — the impure packages are not installed at all", ""]
    if probe.get("ok"):
        loaded = probe["impure_modules_loaded"] or ["NONE"]
        lines += [
            "```",
            f"python                 {probe['python']}",
            f"HBJSON faces           {probe['hbjson_faces']}",
            f"PhxProject variants    {probe['phx_variants']}",
            f"WUFI-Passive XML       {probe['wufi_xml_chars']:,} chars",
            f"METr JSON              {probe['metr_json_chars']:,} chars",
            f"impure modules loaded  {', '.join(loaded)}",
            "```",
            "",
            ("Honeybee model → PhxProject → WUFI-Passive XML **and** METr JSON, with none of "
             f"`{'`, `'.join(IMPURE)}` installed."),
        ]
    else:
        lines += ["The probe **failed**:", "", "```", str(probe.get("error", "")), "```"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-version", default="3.14", help="Pyodide 314.x runs CPython 3.14")
    parser.add_argument("--md", type=Path, help="write the report here (default: stdout)")
    args = parser.parse_args()

    if not shutil.which("uv"):
        print("uv is required", file=sys.stderr)
        return 1

    for problem in check_pins_against_closure(PINS, CLOSURE_JSON):
        print(f"pin drift: {problem}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        # uv has no `pip download` subcommand (checked against uv 0.9.1), so the wheels come from
        # pip. `uv venv --seed` is the cheapest way to get a pip that is not the system Python's.
        venv = Path(tmp) / "downloader"
        wheels = Path(tmp) / "wheels"
        subprocess.run(["uv", "venv", "--seed", str(venv)], check=True, capture_output=True)
        subprocess.run(
            [str(venv / "bin" / "python"), "-m", "pip", "download", "--quiet", "--no-deps",
             "--only-binary=:all:", "--dest", str(wheels), *PINS],
            check=True, capture_output=True,
        )
        scan = scan_wheels(wheels, IMPURE)

    probe = run_empirical_probe(PINS, args.python_version)
    report = render_markdown(scan, probe)

    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(report)
        print(f"wrote {args.md}", file=sys.stderr)
    else:
        print(report)
    return 0 if probe.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
