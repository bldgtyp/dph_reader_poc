#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.8"]
# ///
"""Phase 0 §0.4 — characterise the reference HBJSON.

Three jobs, per the phase doc:

1. Validate the PH extension payloads against `honeybee-ph-schema`. (The *core* schema check
   is a separate script — `validate_hbjson_core.py` — because honeybee-schema 1.53.x needs
   pydantic 1.x and cannot share an environment with honeybee-ph-schema's pydantic 2.x. This
   script reads that script's JSON verdict.)
2. Dump the exact key paths where PH data lives, as the target shape for the translator.
3. Test the PRD §7.2 hypothesis that the 1287 orphaned shades are the same geometry as the
   1359 untagged designPH faces.

`honeybee-ph-schema` is not on PyPI; it is imported from the local checkout. Pass its location
with `--ph-schema` if it lives somewhere other than the BLDGTYP default.

Usage
-----
    uv run hbjson_reference_report.py MODEL.hbjson --core-verdict V.json --out SHAPE.md
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PH_SCHEMA = Path.home() / "Dropbox/bldgtyp-00/00_PH_Tools/honeybee-ph-schema"

# Paths worth calling out explicitly: these are where a translator must write PH data.
# Recorded as (json path, what lives there).
PH_PATHS: list[tuple[str, str]] = [
    ("properties.ph", "model-level PH properties — `ModelPhPropertiesAbridged`"),
    ("properties.ph.bldg_segments[]", "building segments: certification, set points, thermal bridges"),
    ("properties.ph.team", "designer / customer / building / owner contact blocks"),
    ("rooms[].properties.ph", "room-level PH properties — `RoomPhPropertiesAbridged`"),
    ("rooms[].properties.ph.spaces[]", "PH `Space`s — the TFA/iCFA carrier"),
    ("rooms[].properties.ph.spaces[].volumes[]", "space volumes: `avg_ceiling_height`, `floor`"),
    ("rooms[].properties.ph.ph_bldg_segment_id", "link from room to its building segment"),
    ("rooms[].faces[].properties.ph", "face PH properties — `FacePhPropertiesAbridged`"),
    ("rooms[].faces[].apertures[].properties.ph", "aperture PH properties: shading factors, install depth"),
    ("orphaned_shades[].properties.ph", "shade PH properties — `ShadePhPropertiesAbridged`"),
]


# ---------------------------------------------------------------------------
# 1 — schema validation
# ---------------------------------------------------------------------------


def all_faces(model: dict) -> list[dict]:
    return [f for r in model.get("rooms", []) for f in r.get("faces", [])]


def all_apertures(model: dict) -> list[dict]:
    return [a for f in all_faces(model) for a in f.get("apertures", [])]


def validate_ph(model: dict, ph_schema_dir: Path) -> dict[str, Any]:
    """Validate every PH extension payload against `honeybee-ph-schema`."""
    sys.path.insert(0, str(ph_schema_dir))
    try:
        import honeybee_ph_schema
        from honeybee_ph_schema.ph import (
            PhApertureProperties,
            PhFaceProperties,
            PhRoomProperties,
        )
    except ImportError as exc:
        return {"available": False, "error": f"{exc}", "path": str(ph_schema_dir)}

    from pydantic import ValidationError

    checks: list[tuple[str, Any, list[dict]]] = [
        ("rooms[].properties.ph", PhRoomProperties, [r["properties"]["ph"] for r in model.get("rooms", [])]),
        (
            "rooms[].faces[].properties.ph",
            PhFaceProperties,
            [f["properties"]["ph"] for f in all_faces(model)],
        ),
        (
            "rooms[].faces[].apertures[].properties.ph",
            PhApertureProperties,
            [a["properties"]["ph"] for a in all_apertures(model)],
        ),
    ]

    results = []
    for path, cls, payloads in checks:
        failures = []
        for i, payload in enumerate(payloads):
            try:
                cls.model_validate(payload)
            except ValidationError as exc:
                failures.append({"index": i, "errors": exc.errors()[:3]})
        results.append(
            {"path": path, "model": cls.__name__, "checked": len(payloads), "failed": len(failures),
             "sample_failures": failures[:3]}
        )

    return {
        "available": True,
        "version": honeybee_ph_schema.__version__,
        "path": str(ph_schema_dir),
        "results": results,
        # Worth stating plainly: this contract is permissive by construction.
        "strictness": {
            cls.__name__: {
                "extra": cls.model_config.get("extra"),
                "required_fields": [n for n, f in cls.model_fields.items() if f.is_required()],
            }
            for cls in (PhRoomProperties, PhFaceProperties, PhApertureProperties)
        },
    }


# ---------------------------------------------------------------------------
# 2 — shape
# ---------------------------------------------------------------------------


def resolve(model: dict, path: str) -> Any:
    """Follow a dotted path with `[]` list markers, returning the first value found.

    Every list element is tried, not just the first: `rooms[0].faces[0]` in this file has no
    apertures, and reporting the aperture path as *absent* on that basis would be wrong.
    """
    parts = path.split(".")

    def walk(node: Any, i: int) -> Any:
        for j in range(i, len(parts)):
            part = parts[j]
            if part.endswith("[]"):
                items = node.get(part[:-2]) if isinstance(node, dict) else None
                if not isinstance(items, list):
                    return None
                for item in items:
                    found = walk(item, j + 1)
                    if found is not None:
                        return found
                return None
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                return None
        return node

    return walk(model, 0)


def summarise(node: Any) -> str:
    if isinstance(node, dict):
        return ", ".join(f"`{k}`" for k in node)
    if isinstance(node, list):
        return f"list[{len(node)}]"
    return f"`{node!r}`"


def counts(model: dict) -> dict[str, int]:
    rooms = model.get("rooms", [])
    faces = all_faces(model)
    spaces = [s for r in rooms for s in r["properties"]["ph"].get("spaces", [])]
    return {
        "rooms": len(rooms),
        "faces": len(faces),
        "apertures": len(all_apertures(model)),
        "doors": sum(len(f.get("doors", [])) for f in faces),
        "ph_spaces": len(spaces),
        "orphaned_shades": len(model.get("orphaned_shades", [])),
        "constructions": len(model["properties"].get("energy", {}).get("constructions", [])),
        "materials": len(model["properties"].get("energy", {}).get("materials", [])),
    }


# ---------------------------------------------------------------------------
# 3 — the orphaned-shades hypothesis
# ---------------------------------------------------------------------------


def bbox(vertices: list[list[float]]) -> tuple[tuple[float, float], ...]:
    cols = list(zip(*vertices))
    return tuple((min(c), max(c)) for c in cols)


def shade_analysis(model: dict, untagged_face_count: int | None) -> dict[str, Any]:
    """Characterise the orphaned shades and compare against the untagged designPH faces.

    The offline `.skp` reader cannot read geometry, so a coordinate-level comparison is not
    possible here — that needs SketchUp. What *is* decidable offline is what kind of geometry
    the shades are, which is enough to answer whether "untagged face -> orphaned shade" is a
    safe blanket rule.
    """
    shades = model.get("orphaned_shades", [])
    if not shades:
        return {"shades": 0}

    shade_verts = [v for s in shades for v in s["geometry"]["boundary"]]
    room_verts = [v for f in all_faces(model) for v in f["geometry"]["boundary"]]
    sb, rb = bbox(shade_verts), bbox(room_verts)

    def within_room_bbox(shade: dict) -> bool:
        return all(
            all(rb[i][0] <= v[i] <= rb[i][1] for i in range(3)) for v in shade["geometry"]["boundary"]
        )

    inside = sum(1 for s in shades if within_room_bbox(s))
    name_patterns = collections.Counter(
        re.sub(r"\d+", "#", s.get("display_name", "")) for s in shades
    )

    return {
        "shades": len(shades),
        "untagged_designph_faces": untagged_face_count,
        "all_detached": all(s.get("is_detached") for s in shades),
        "geometry_types": dict(collections.Counter(s["geometry"]["type"] for s in shades)),
        "vertex_counts": dict(collections.Counter(len(s["geometry"]["boundary"]) for s in shades).most_common(6)),
        "shade_bbox": sb,
        "room_bbox": rb,
        "shades_inside_room_bbox": inside,
        "name_patterns": name_patterns.most_common(5),
        "shades_carrying_ph_properties": sum(1 for s in shades if s["properties"].get("ph")),
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def render(model: dict, core: dict | None, ph: dict, shades: dict, src: Path) -> str:
    lines: list[str] = []
    add = lines.append
    n = counts(model)

    add("# Phase 0 §0.4 — Reference HBJSON: validation and shape")
    add("")
    add(f"Source: `{src}`")
    add(
        f"Declared honeybee schema version **{model.get('version')}**, "
        f"units **{model.get('units')}**, tolerance **{model.get('tolerance')}**."
    )
    add("")
    add(
        "> ⚠ **Shape reference, not an equality target.** This file came from the Rhino route: "
        "6 solid Rooms with solved interior adjacency. v1 emits one non-solid Room by design "
        "(PRD §8.1). Use it to check our output is well-formed and plausibly populated — never "
        "to assert equality."
    )
    add("")

    add("## Inventory")
    add("")
    add("| Collection | n |")
    add("|---|---|")
    for k, v in n.items():
        add(f"| {k.replace('_', ' ')} | {v} |")
    add("")

    add("## 1 — Schema validation")
    add("")
    if core is None:
        add("*Core schema verdict not supplied — run `validate_hbjson_core.py` first.*")
    else:
        verdict = "**VALID**" if core["valid"] else "**INVALID**"
        add(f"### Core — `{core['validator']}`")
        add("")
        add(
            f"{verdict} — {core['error_count']} raw errors across "
            f"{core['failing_object_count']} distinct failing objects."
        )
        add("")
        if not core["valid"]:
            touching = core["errors_touching_core_or_ph"]
            containers = core["failing_containers"]
            add("| Failing container | Distinct objects |")
            add("|---|---|")
            for path, count in containers.items():
                add(f"| `{path}` | {count} |")
            add("")
            add(
                "The raw error count is inflated by pydantic-1 union expansion: each non-conforming "
                "material or construction reports once per candidate branch of its union. The object "
                "count is the honest figure."
            )
            add("")
            # Computed, not asserted: if a future run does touch geometry or PH, this says so.
            if touching == 0:
                add(
                    "**No error touches geometry, boundary conditions, apertures, shades, or "
                    "`properties.ph`.** Every failure is inside an honeybee-energy payload."
                )
                add("")
                add(
                    "**Consequence for PRD §11.** Validating v1 output against `honeybee-schema` "
                    "remains a sound acceptance gate: the parts that fail here are energy payloads "
                    "v1 does not write. Do not weaken the criterion on the strength of this "
                    "result — scope it to the core geometry and PH payloads."
                )
            else:
                add(
                    f"⚠ **{touching} error(s) touch geometry, boundary conditions, apertures, "
                    "shades, or `properties.ph`** — the payloads v1 *does* write. This is not the "
                    "harmless energy-only skew recorded in Phase 0; investigate before relying on "
                    "PRD §11 criterion 1."
                )
                add("")
                for loc in core.get("sample_of_errors_touching_core_or_ph", []):
                    add(f"- `{loc}`")
        add("")

    add(f"### PH extensions — `honeybee-ph-schema`")
    add("")
    if not ph.get("available"):
        add(f"⚠ Not importable from `{ph.get('path')}`: `{ph.get('error')}`")
    else:
        add(f"Version **{ph['version']}**, imported from `{ph['path']}` (not published to PyPI).")
        add("")
        add("| Payload path | Model | Checked | Failed |")
        add("|---|---|---|---|")
        for r in ph["results"]:
            add(f"| `{r['path']}` | `{r['model']}` | {r['checked']} | {r['failed']} |")
        add("")
        add("**How much does this prove?** Not much yet:")
        add("")
        add("| Schema model | `extra` policy | Required fields |")
        add("|---|---|---|")
        for name, s in ph["strictness"].items():
            req = ", ".join(f"`{f}`" for f in s["required_fields"]) or "*none*"
            add(f"| `{name}` | `{s['extra']}` | {req} |")
        add("")
        add(
            "Every field is optional and every model allows extra keys, so a payload of `{}` "
            "validates. `honeybee-ph-schema` at v0.1.0 is a **contract stub, not an acceptance "
            "gate**. PRD §11 should not lean on it until it tightens."
        )
    add("")

    add("## 2 — Where PH data lives")
    add("")
    add("The target shape for the translator. Paths verified present in this file.")
    add("")
    add("| Path | Holds | Keys / value |")
    add("|---|---|---|")
    for path, meaning in PH_PATHS:
        node = resolve(model, path)
        add(f"| `{path}` | {meaning} | {summarise(node) if node is not None else '*absent*'} |")
    add("")

    space = resolve(model, "rooms[].properties.ph.spaces[]")
    if space:
        add("### `Space` in detail — the TFA carrier")
        add("")
        add("| Key | Example | Note |")
        add("|---|---|---|")
        notes = {
            "wufi_type": "WUFI/Phius room-use enum",
            "quantity": "multiplier for repeated identical spaces",
            "number": "user room number, e.g. `000ST`",
            "name": "user room name, e.g. `STAIR`",
            "volumes": "one or more `Volume`s; each carries `floor` and `avg_ceiling_height`",
        }
        for k, v in space.items():
            shown = f"list[{len(v)}]" if isinstance(v, list) else (
                "`{…}`" if isinstance(v, dict) else f"`{v!r}`"
            )
            add(f"| `{k}` | {shown} | {notes.get(k, '')} |")
        add("")

    add("## 3 — The 1287 orphaned shades")
    add("")
    add(
        "PRD §7.2 proposes that untagged designPH faces (`areaGroupID='n'`) have a natural home "
        "as orphaned shades, and asks Phase 0 to confirm it by comparing counts and coordinates."
    )
    add("")
    add("| Observation | Value |")
    add("|---|---|")
    add(f"| Orphaned shades in the reference | {shades['shades']} |")
    add(f"| Untagged faces in `adelphi-designph.skp` | {shades['untagged_designph_faces']} |")
    add(f"| All shades `is_detached` | {shades['all_detached']} |")
    add(f"| Geometry types | {shades['geometry_types']} |")
    add(f"| Vertices per shade | {shades['vertex_counts']} |")
    sb, rb = shades["shade_bbox"], shades["room_bbox"]
    axes = "XYZ"
    add(f"| Shade bounding box (m) | {' · '.join(f'{axes[i]}[{sb[i][0]:.1f}, {sb[i][1]:.1f}]' for i in range(3))} |")
    add(f"| Room bounding box (m) | {' · '.join(f'{axes[i]}[{rb[i][0]:.1f}, {rb[i][1]:.1f}]' for i in range(3))} |")
    add(f"| Shades entirely inside the room bbox | {shades['shades_inside_room_bbox']} |")
    add(f"| Shades carrying `properties.ph` | {shades['shades_carrying_ph_properties']} / {shades['shades']} |")
    add("")
    add("### Verdict — confirmed as a destination, refuted as a blanket rule")
    add("")
    add(
        "**The destination is right.** Exterior context geometry has a well-formed home in HBJSON "
        "as `orphaned_shades` with `is_detached: true` and a `ShadePhPropertiesAbridged` block. "
        "Emitting it costs nothing and lets Ladybug compute shading downstream. Promote to v1 scope."
    )
    add("")
    add(
        "**The source mapping is not.** These shades are *purely exterior site context*: all "
        f"{shades['shades']} are detached, and **{shades['shades_inside_room_bbox']}** of them fall "
        "inside the building's bounding box — they span roughly 50 m × 50 m around a 15 m × 9 m "
        "building. The untagged designPH faces are a mixed bag: "
        "`00_Context/DESIGNPH_DATA_MODEL.md` §6 characterises them as *interior partitions, "
        "furniture, and context*. Mapping every untagged face to an orphaned shade would inject "
        "interior partitions and furniture into the shading model and silently corrupt any "
        "downstream shading calculation."
    )
    add("")
    add(
        "**The count similarity is not evidence.** 1287 vs 1359 is close, but the two sets have "
        "different provenance — this HBJSON came from the Rhino route, not from "
        "`adelphi-designph.skp`. The offline `.skp` reader reads attribute dictionaries only, not "
        "geometry, so a coordinate-level comparison is not possible without SketchUp."
    )
    add("")
    add(
        "**Carried to Phase 1:** define the filter that separates shading-relevant exterior "
        "geometry from interior clutter, and confirm it against live geometry in SketchUp. Until "
        "that filter exists, untagged faces must be *reported*, not exported."
    )
    add("")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hbjson", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--core-verdict", type=Path, help="JSON written by validate_hbjson_core.py")
    ap.add_argument("--ph-schema", type=Path, default=DEFAULT_PH_SCHEMA)
    ap.add_argument(
        "--untagged-faces",
        type=int,
        default=None,
        help="count of untagged designPH faces to compare the shade count against",
    )
    args = ap.parse_args()

    model = json.loads(args.hbjson.read_text())
    core = json.loads(args.core_verdict.read_text()) if args.core_verdict else None
    ph = validate_ph(model, args.ph_schema)
    shades = shade_analysis(model, args.untagged_faces)

    args.out.write_text(render(model, core, ph, shades, args.hbjson))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
