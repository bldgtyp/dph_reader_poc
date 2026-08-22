#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Phase 0 §0.3 — structured baseline of every `DesignPH_dict` key across the corpus.

Reuses the offline reader in `00_Context/tools/skp_attr_dump.py` (no SketchUp needed) and
adds what the raw dump does not give:

* the designPH version stamp(s) each model carries,
* **every** distinct value of every face-level key (the raw dump truncates to the top 8),
* which key generation (`*ID` vs `*Auto`) the model is written in,
* and a flag on any key or value **not** documented in
  `00_Context/DESIGNPH_DATA_MODEL.md` §4–§5.

CAVEAT, inherited from the reader: `model.dat` accumulates historical state. Counts here are
records-in-the-file, not live entities. A model opened in two designPH versions carries both
key generations and neither is ever purged (§6). Treat every count as an upper bound.

Usage
-----
    uv run corpus_baseline.py MODEL.skp [MODEL.skp ...] --md OUT.md [--json OUT.json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
READER = REPO_ROOT / "00_Context" / "tools" / "skp_attr_dump.py"

# ---------------------------------------------------------------------------
# What `00_Context/DESIGNPH_DATA_MODEL.md` already documents.
# Anything outside these sets is reported as a finding, not silently accepted.
# ---------------------------------------------------------------------------

# §5 — attached to individual faces.
FACE_KEYS = frozenset(
    {
        "areaGroupAuto",
        "areaGroupID",
        "assemblyIDAuto",
        "assemblyID",
        "tempZoneAuto",
        "tempZoneID",
        "faceTypeAuto",
        "descNameAuto",
        "descNameFreeze",
        "TFA_rf",
        "Material",
        "BackMaterial",
    }
)

# §4 — attached to the model. `layer_table_*` is a family, handled separately.
MODEL_KEYS = frozenset(
    {
        "designPH_version",
        "klima_ID",
        "Klima_Standort",
        "Dashboard",
        "assemblies_calc",
        "assemblies_ud",  # §6: Adelphi spells it this way
        "connections_ud",
        "frames_ud",
        "glazing_ud",
        "vent_ud",
        "ihg_ud",
        "tfa_calc",
        "tfa_calc_ud",
        "tracker_data",
    }
)

LAYER_TABLE_PREFIX = "layer_table_"

# §5.3 + §6 — PHPP Areas-worksheet group numbers we can account for.
# 14 has a shipped .skm but no observed data; 18 was observed on Adelphi and is unexplained.
DOCUMENTED_AREA_GROUPS: frozenset[object] = frozenset(
    {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, "n", None}
)
DOCUMENTED_TEMP_ZONES: frozenset[object] = frozenset({"A", "B", "i", "I", "TFA", "split A/B", None})
DOCUMENTED_FACE_TYPES: frozenset[object] = frozenset({"xo", "xi", "i", None})
DOCUMENTED_TFA_RF: frozenset[object] = frozenset({0, 0.0, 0.3, 0.5, None})

# Keys whose value space is a documented enum. Free-text keys (names, materials,
# assembly IDs) are excluded — their values carry no schema to violate.
ENUM_KEYS: dict[str, frozenset[object]] = {
    "areaGroupID": DOCUMENTED_AREA_GROUPS,
    "areaGroupAuto": DOCUMENTED_AREA_GROUPS,
    "tempZoneID": DOCUMENTED_TEMP_ZONES,
    "tempZoneAuto": DOCUMENTED_TEMP_ZONES,
    "faceTypeAuto": DOCUMENTED_FACE_TYPES,
    "TFA_rf": DOCUMENTED_TFA_RF,
}

# §6 — the version rename. Only these two pairs discriminate between the generations:
# `assemblyIDAuto`, `descNameAuto` and `faceTypeAuto` exist in *both* eras (they are genuine
# derived caches, not part of the rename), so they cannot be used as evidence of generation.
GENERATION_ID = ("areaGroupID", "tempZoneID")
GENERATION_AUTO = ("areaGroupAuto", "tempZoneAuto")

MARSHAL_PREFIX = "BAh"  # base64 of Ruby's \x04\x08 Marshal marker (§7)


def load_reader():
    """Import the offline .skp reader from `00_Context/tools/` by path."""
    spec = importlib.util.spec_from_file_location("skp_attr_dump", READER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reader at {READER}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec: the reader defines a dataclass, and `dataclasses` resolves
    # field types through `sys.modules[cls.__module__]`, which fails for an unregistered module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class KeyProfile:
    """Every value seen for one key in one model, with its Ruby type."""

    key: str
    values: Counter = field(default_factory=Counter)  # (type, value) -> count
    total: int = 0

    def add(self, type_name: str, value: object) -> None:
        # Marshal blobs are megabytes of base64; record the fact and the size, not the payload.
        if type_name == "str" and isinstance(value, str) and value.startswith(MARSHAL_PREFIX):
            value = f"<marshal {len(value)} b64 chars>"
        self.values[(type_name, value)] += 1
        self.total += 1

    @property
    def types(self) -> set[str]:
        return {t for t, _ in self.values}

    @property
    def non_nil(self) -> int:
        """Records holding an actual value. designPH writes nil placeholders freely."""
        return sum(n for (_, v), n in self.values.items() if v is not None)

    def undocumented_values(self) -> list[tuple[str, object, int]]:
        allowed = ENUM_KEYS.get(self.key)
        if allowed is None:
            return []
        return [
            (t, v, n) for (t, v), n in sorted(self.values.items(), key=lambda kv: -kv[1])
            if v not in allowed
        ]


@dataclass
class ModelProfile:
    """One `.skp`, profiled."""

    path: Path
    versions: list[str] = field(default_factory=list)
    face: dict[str, KeyProfile] = field(default_factory=dict)
    model: dict[str, KeyProfile] = field(default_factory=dict)
    layer_tables: list[str] = field(default_factory=list)
    unknown: dict[str, KeyProfile] = field(default_factory=dict)
    other_dicts: dict[str, int] = field(default_factory=dict)

    @property
    def generation(self) -> str:
        """Which key generation carries this model's data — see §6.

        A model opened in both eras carries both, and the stale set is never purged;
        say so rather than picking one.

        A key that is present but holds only nil is not evidence of its generation —
        designPH writes the placeholder either way.
        """
        has_id = any(self.face[k].non_nil for k in GENERATION_ID if k in self.face)
        has_auto = any(self.face[k].non_nil for k in GENERATION_AUTO if k in self.face)
        if has_id and has_auto:
            return "BOTH"
        if has_auto:
            return "Auto (>=2.2)"
        if has_id:
            return "ID (<2.2)"
        return "none"

    def undocumented_keys(self) -> list[str]:
        return sorted(self.unknown)


def profile(path: Path, reader) -> ModelProfile:
    buf = reader.read_model_dat(path)
    grouped = reader.collect(buf)
    out = ModelProfile(path=path)
    versions: set[str] = set()
    layer_tables: set[str] = set()

    for dict_name, entries in grouped.items():
        if dict_name != "DesignPH_dict":
            out.other_dicts[dict_name] = len(entries)
            continue
        for key, type_name, value in entries:
            if key == "designPH_version" and isinstance(value, str):
                versions.add(value)
            if key.startswith(LAYER_TABLE_PREFIX):
                layer_tables.add(key)
                continue
            bucket = out.face if key in FACE_KEYS else out.model if key in MODEL_KEYS else out.unknown
            bucket.setdefault(key, KeyProfile(key)).add(type_name, value)

    out.versions = sorted(versions)
    out.layer_tables = sorted(layer_tables)
    return out


def render_value(type_name: str, value: object) -> str:
    return f"`{value!r}` *({type_name})*"


def render(profiles: list[ModelProfile]) -> str:
    lines: list[str] = []
    add = lines.append

    add("# Phase 0 §0.3 — Corpus Baseline")
    add("")
    add(
        "Generated by `planning/spikes/phase0/corpus_baseline.py` from the offline reader "
        "`00_Context/tools/skp_attr_dump.py`. No SketchUp involved, no corpus file modified."
    )
    add("")
    add(
        "> ⚠ **Counts are records in `model.dat`, not live entities.** The `.skp` stream "
        "accumulates historical state, so every count below is an upper bound on the number of "
        "faces actually carrying that key. Use the BT Attribute Inspector for live state."
    )
    add("")

    add("## Models")
    add("")
    add("| Model | designPH stamp(s) | Key generation | Face keys | Model keys | `layer_table_*` | Undocumented keys |")
    add("|---|---|---|---|---|---|---|")
    for p in profiles:
        stamps = ", ".join(f"`{v}`" for v in p.versions) or "*(none)*"
        undoc = ", ".join(f"`{k}`" for k in p.undocumented_keys()) or "—"
        add(
            f"| `{p.path.name}` | {stamps} | {p.generation} | {len(p.face)} | "
            f"{len(p.model)} | {len(p.layer_tables)} | {undoc} |"
        )
    add("")

    # --- findings first: this is the part of the report that changes the plan ---
    add("## Findings — undocumented keys and values")
    add("")
    undoc_keys: dict[str, list[str]] = {}
    for p in profiles:
        for key in p.undocumented_keys():
            undoc_keys.setdefault(key, []).append(p.path.name)
    if undoc_keys:
        add("### Keys not in `DESIGNPH_DATA_MODEL.md` §4–§5")
        add("")
        add("| Key | Models | Types | Sample values |")
        add("|---|---|---|---|")
        for key, models in sorted(undoc_keys.items()):
            kp = next(p.unknown[key] for p in profiles if key in p.unknown)
            samples = ", ".join(
                render_value(t, v) for (t, v), _ in kp.values.most_common(3)
            )
            add(f"| `{key}` | {len(models)} | {', '.join(sorted(kp.types))} | {samples} |")
        add("")
    else:
        add("No undocumented keys found.")
        add("")

    undoc_vals: dict[tuple[str, str, object], list[str]] = {}
    for p in profiles:
        for key, kp in p.face.items():
            for type_name, value, _ in kp.undocumented_values():
                undoc_vals.setdefault((key, type_name, value), []).append(p.path.name)
    add("### Values outside the documented enums (§5.3, §6)")
    add("")
    if undoc_vals:
        add("| Key | Value | Type | Models |")
        add("|---|---|---|---|")
        for (key, type_name, value), models in sorted(undoc_vals.items(), key=lambda kv: kv[0][0]):
            add(f"| `{key}` | `{value!r}` | {type_name} | {', '.join(sorted(models))} |")
    else:
        add("None — every enum value observed is already documented.")
    add("")

    # --- per-model detail ---
    add("## Per-model detail")
    add("")
    for p in profiles:
        add(f"### `{p.path.name}`")
        add("")
        add(f"- Path: `{p.path}`")
        add(f"- designPH stamp(s): {', '.join(f'`{v}`' for v in p.versions) or '*(none)*'}")
        add(f"- Key generation: **{p.generation}**")
        if p.layer_tables:
            add(f"- `layer_table_*` keys ({len(p.layer_tables)}): {', '.join(f'`{k}`' for k in p.layer_tables)}")
        if p.other_dicts:
            ranked = sorted(p.other_dicts.items(), key=lambda kv: -kv[1])
            shown, rest = ranked[:8], len(ranked) - 8
            others = ", ".join(f"`{d}` ({n})" for d, n in shown)
            if rest > 0:
                others += f", *…{rest} more*"
            add(f"- Other attribute dictionaries present: {others}")
        add("")
        if p.face:
            add("**Face-level keys** — every distinct value:")
            add("")
            add("| Key | n | Types | Distinct values (count) |")
            add("|---|---|---|---|")
            for key in sorted(p.face, key=lambda k: -p.face[k].total):
                kp = p.face[key]
                shown = kp.values.most_common(12)
                rest = len(kp.values) - len(shown)
                vals = " · ".join(f"`{v!r}` ({n})" for (_, v), n in shown)
                if rest > 0:
                    vals += f" · *…{rest} more*"
                add(f"| `{key}` | {kp.total} | {', '.join(sorted(kp.types))} | {vals} |")
            add("")
        if p.model:
            add("**Model-level keys:**")
            add("")
            add("| Key | n | Types | Value |")
            add("|---|---|---|---|")
            for key in sorted(p.model):
                kp = p.model[key]
                vals = " · ".join(f"`{v!r}`" for (_, v), _ in kp.values.most_common(4))
                add(f"| `{key}` | {kp.total} | {', '.join(sorted(kp.types))} | {vals} |")
            add("")

    return "\n".join(lines) + "\n"


def to_json(profiles: list[ModelProfile]) -> dict:
    return {
        p.path.name: {
            "path": str(p.path),
            "versions": p.versions,
            "generation": p.generation,
            "layer_tables": p.layer_tables,
            "other_dictionaries": p.other_dicts,
            "face_keys": {
                k: {
                    "total": kp.total,
                    "types": sorted(kp.types),
                    "values": [
                        {"type": t, "value": v, "count": n} for (t, v), n in kp.values.most_common()
                    ],
                    "undocumented_values": [
                        {"type": t, "value": v, "count": n} for t, v, n in kp.undocumented_values()
                    ],
                }
                for k, kp in p.face.items()
            },
            "model_keys": {
                k: {"total": kp.total, "types": sorted(kp.types)} for k, kp in p.model.items()
            },
            "undocumented_keys": p.undocumented_keys(),
        }
        for p in profiles
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+", type=Path)
    ap.add_argument("--md", type=Path, required=True, help="write the markdown report here")
    ap.add_argument("--json", type=Path, help="also write the full machine-readable profile here")
    args = ap.parse_args()

    reader = load_reader()
    profiles: list[ModelProfile] = []
    for path in args.models:
        if not path.exists():
            print(f"skipping missing file: {path}", file=sys.stderr)
            continue
        profiles.append(profile(path, reader))

    args.md.write_text(render(profiles))
    print(f"wrote {args.md}  ({len(profiles)} models)")
    if args.json:
        args.json.write_text(json.dumps(to_json(profiles), indent=2, default=str))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
