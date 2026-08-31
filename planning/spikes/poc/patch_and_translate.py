# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Rehearse the fixed collector against Adelphi, offline, before spending an Ed session on it.

The first capture shipped the two window fields wrong (contract §8.1/§8.2). `solve_window_parent.py`
recovers the parent transform exactly from that same capture, which is enough to rebuild the two
fields *as the fixed collector would emit them* and run the real translator on the result.

⚠ **The output is a rehearsal, not a capture.** It is written to a scratch path and marked in
`generated_by`; nothing here may be used as a fixture or quoted as evidence about a live model. What
it does prove is that the translator's aperture path works on the real model's geometry — so if the
re-capture in POC-2's next Ed session still reports 0 of 46, the fault is in the collector and not
in the translation.

    uv run planning/spikes/poc/patch_and_translate.py [OUT.json]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from solve_window_parent import FIXTURE, IN_TO_M, columns, kabsch, plane_of  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = ROOT / "pocs/01_sketchup-export/py/.venv/bin/python"


def parent_transform(payload: dict) -> np.ndarray:
    """The 4×4 parent transform, in INCHES — solved, not read. See `solve_window_parent.py`."""
    faces = {face["id"]: face for face in payload["faces"]}
    axes, normals, origins, points = [], [], [], []
    for window in payload["windows"]:
        host = faces.get(window["host_face_id"] or "")
        if host is None:
            continue
        matrix = columns(window["transformation"])
        point, normal = plane_of(host["outer_loop"])
        axes.append(matrix[:3, 2])
        normals.append(normal)
        origins.append(matrix[:3, 3] * IN_TO_M)
        points.append(point)

    axes, normals, origins = np.array(axes), np.array(normals), np.array(origins)
    signs = np.ones(len(axes))
    for _ in range(20):
        rotation = kabsch(axes, normals * signs[:, None])
        updated = np.sign(np.einsum("ij,ij->i", axes @ rotation.T, normals))
        updated[updated == 0] = 1.0
        if np.array_equal(updated, signs):
            break
        signs = updated
    b = np.einsum("ij,ij->i", normals, np.array(points)) - np.einsum(
        "ij,ij->i", normals, origins @ rotation.T
    )
    translation, *_ = np.linalg.lstsq(normals, b, rcond=None)

    parent = np.eye(4)
    parent[:3, :3] = rotation
    parent[:3, 3] = translation / IN_TO_M  # the matrices are in SketchUp's inches
    return parent


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/adelphi_rehearsal.extraction.json")
    payload = json.loads(FIXTURE.read_text())
    parent = parent_transform(payload)

    for window in payload["windows"]:
        world = parent @ columns(window["transformation"])
        # Column-major, translation at 12-14, inches — exactly `world.to_a` in Ruby.
        window["transformation"] = [round(v, 12) for v in world.T.reshape(-1).tolist()]
        attributes = window["dynamic_attributes"]
        try:
            lenx, leny = float(attributes["lenx"]), float(attributes["leny"])
        except (KeyError, TypeError, ValueError):
            window["panel_outer_loop"] = None
            continue
        window["panel_outer_loop"] = [
            [round(v, 6) for v in ((world @ np.array([x, y, 0.0, 1.0]))[:3] * IN_TO_M).tolist()]
            for x, y in ((0.0, 0.0), (lenx, 0.0), (lenx, leny), (0.0, leny))
        ]

    payload["generated_by"] = "REHEARSAL: first capture patched offline by patch_and_translate.py"
    out.write_text(json.dumps(payload))
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)\n")

    script = """
import json, sys
from dph_translator.contract import parse
from dph_translator.build import translate
result = translate(parse(json.load(open(sys.argv[1]))))
summary = result.report["summary"]
for key in ("faces", "apertures", "thermal_bridges", "spaces"):
    print(f"  {key:<16}{summary[key]}")
print(f"  {'tfa m2':<16}covered {summary['tfa_m2_covered']}, lost {summary['tfa_m2_lost']}")
print(f"  {'hbjson':<16}{summary['hbjson_bytes']} bytes")
print(f"  {'verdict':<16}{result.verdict['headline']}")
tally = result.report["entries"]["aperture"]["outcomes"]
print(f"  {'aperture tally':<16}{tally}")
reasons = {}
for entry in result.report["entries"]["aperture"]["listed"]:
    if entry["outcome"] != "translated":
        reasons[entry.get("reason", "-")] = reasons.get(entry.get("reason", "-"), 0) + 1
for reason, count in reasons.items():
    print(f"      {count} x {reason[:130]}")
tfa = result.report["entries"].get("tfa", {})
print(f"  {'tfa entries':<16}{tfa.get('outcomes', {})}")
for entry in tfa.get("listed", [])[:3]:
    print(f"      {entry['id']}: {entry['reason'][:120]}")
"""
    return subprocess.run(
        [str(VENV_PYTHON), "-c", script, str(out)], cwd=ROOT / "pocs/01_sketchup-export/py", check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
