#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Phase 1 sections 1.1 and 1.3 -- per-face attribute co-occurrence across the corpus.

Phase 0 could only count records, so three of its conclusions rest on population arithmetic:
the `*ID` / `*Auto` precedence (Finding 2), the `areaGroupID` -> `tempZoneID` mapping (Finding 1),
and the `descName` override triple (Finding 5). This script groups records by the entity that
carries them (see `skp_blocks.py`) and checks all three *per face* instead.

It answers, in particular, the question Phase 0 recorded as the one that decides the reader:
**can `*Auto` hold a value on a face where `*ID` holds none?** If it can, "prefer `*ID`" loses
data exactly as the refuted version rule did.

Read the caveat in `skp_blocks.py` before quoting a population from this report: `model.dat` keeps
historical state, so the block count is not a census of live entities. Co-occurrence within a
block is sound; a block's existence is not proof the entity is still in the model.

Usage
-----
    uv run face_attribute_matrix.py MODEL.skp [MODEL.skp ...] \\
        --md  planning/RESULTS/PHASE-1_face-attribute-matrix.md \\
        --json planning/RESULTS/baselines/phase1_face_attributes.json
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skp_blocks import Block, face_blocks, read_blocks  # noqa: E402

DICT = "DesignPH_dict"

#: The `*ID` (authoritative assignment) / `*Auto` (auto-classification cache) pairs.
#: Phase 0 Finding 2 proposed this reading after the version-rename rule was refuted;
#: this script tests it face by face.
GENERATIONS: list[tuple[str, str]] = [
    ("areaGroupID", "areaGroupAuto"),
    ("tempZoneID", "tempZoneAuto"),
    ("assemblyID", "assemblyIDAuto"),
]

#: The name triple is the same derived/override shape but with the opposite naming --
#: `descName` is the user's override, `descNameAuto` the generated value (Phase 0 Finding 5).
NAME_KEYS = ("descName", "descNameAuto", "descNameFreeze")

#: Any key that only ever appears on a face, used to tell face blocks from the model-level
#: block that carries the library tables.
FACE_KEYS = frozenset(
    [k for pair in GENERATIONS for k in pair] + list(NAME_KEYS) + ["faceTypeAuto", "TFA_rf"]
)

#: Phase 0 Finding 1, decoded from the PHPP `Areas` summary and verified only at population
#: level. Values are the `tempZone` expected beside each `areaGroup`.
EXPECTED_TEMP_ZONE: dict[Any, str] = {
    1: "TFA",
    2: "A", 3: "A", 4: "A", 5: "A", 6: "A",
    7: "A", 8: "A", 10: "A", 15: "A",
    9: "B", 11: "B", 17: "B",
    12: "X", 13: "X", 14: "X",  # user-defined slots, not fixed PHI categories
    16: "P",
    18: "I",
    "n": "i",
}

#: `areaGroupID` values meaning "designPH has not classified this face". Phase 0 established
#: the String `'n'`; a face with no `areaGroup` key at all is untagged for the same purposes.
UNTAGGED_AREA_GROUPS = frozenset(["n"])


@dataclass
class GenerationTally:
    """How one `*ID` / `*Auto` pair is populated across one model's face blocks."""

    id_only: int = 0
    auto_only: int = 0
    both_agree: int = 0
    both_differ: int = 0
    neither: int = 0


def model_version(blocks: list[Block]) -> str:
    """Every `designPH_version` stamp in the file, joined. Models opened in two versions keep both."""
    stamps = {b.values["designPH_version"] for b in blocks if b.non_nil("designPH_version")}
    return " + ".join(sorted(str(s) for s in stamps)) or "unstamped"


def tally_generation(faces: list[Block], id_key: str, auto_key: str) -> GenerationTally:
    tally = GenerationTally()
    for face in faces:
        has_id, has_auto = face.non_nil(id_key), face.non_nil(auto_key)
        if has_id and has_auto:
            if face.values[id_key] == face.values[auto_key]:
                tally.both_agree += 1
            else:
                tally.both_differ += 1
        elif has_id:
            tally.id_only += 1
        elif has_auto:
            tally.auto_only += 1
        else:
            tally.neither += 1
    return tally


def pair_counts(faces: list[Block], left: str, right: str) -> collections.Counter:
    """Observed (left, right) value pairs, counting only faces that carry the left key."""
    counts: collections.Counter = collections.Counter()
    for face in faces:
        if face.non_nil(left):
            counts[(face.values[left], face.values.get(right))] += 1
    return counts


def value_counts(faces: list[Block], key: str, limit: int | None = None) -> dict[str, int]:
    """`repr`-keyed counts of one key's values, most common first, over the faces that carry it."""
    counts = collections.Counter(f.values[key] for f in faces if f.non_nil(key))
    return {repr(value): count for value, count in counts.most_common(limit)}


def analyse(path: Path) -> dict[str, Any]:
    blocks = read_blocks(path, DICT)
    faces = list(face_blocks(blocks, FACE_KEYS))

    generations = {
        id_key: tally_generation(faces, id_key, auto_key) for id_key, auto_key in GENERATIONS
    }

    # The decisive case: a face carrying an `*Auto` value and no `*ID` value. Counted per pair,
    # with a couple of whole blocks kept as evidence of what such a face actually looks like.
    auto_only: dict[str, dict[str, Any]] = {}
    for id_key, auto_key in GENERATIONS:
        hits = [f for f in faces if f.non_nil(auto_key) and not f.non_nil(id_key)]
        if hits:
            auto_only[id_key] = {
                "count": len(hits),
                "auto_values": value_counts(hits, auto_key, limit=8),
                "examples": [
                    {k: v for k, v in f.values.items() if v is not None} for f in hits[:2]
                ],
            }

    # Faces carrying both generations of the same datum. Zero everywhere would mean the two are
    # complementary rather than competing -- i.e. there is no precedence question to answer.
    contested = {
        id_key: [
            {k: v for k, v in f.values.items() if v is not None}
            for f in faces
            if f.non_nil(id_key) and f.non_nil(auto_key)
        ][:5]
        for id_key, auto_key in GENERATIONS
    }

    # Section 1.5: what `faceTypeAuto` says about faces designPH did *not* classify. These are
    # the candidates for shading geometry, and the ones that must not become shading geometry.
    untagged = [
        f
        for f in faces
        if not f.non_nil("areaGroupID") or f.values["areaGroupID"] in UNTAGGED_AREA_GROUPS
    ]

    # Per-face `areaGroup` -> `tempZone` pairing, checked against Phase 0's inferred table.
    zone_pairs = pair_counts(faces, "areaGroupID", "tempZoneID")
    zone_mismatches = {
        f"{group!r} -> {zone!r}": count
        for (group, zone), count in sorted(zone_pairs.items(), key=lambda kv: str(kv[0]))
        if group not in EXPECTED_TEMP_ZONE or EXPECTED_TEMP_ZONE[group] != zone
    }

    return {
        "model": path.name,
        "designPH_version": model_version(blocks),
        "blocks": len(blocks),
        "face_blocks": len(faces),
        "generations": {k: vars(v) for k, v in generations.items()},
        "auto_only": auto_only,
        "contested": {k: v for k, v in contested.items() if v},
        "untagged_faces": len(untagged),
        "untagged_by_face_type": {
            repr(v): c
            for v, c in collections.Counter(
                f.values.get("faceTypeAuto") for f in untagged
            ).most_common()
        },
        "area_group_to_temp_zone": {
            f"{group!r} -> {zone!r}": count for (group, zone), count in zone_pairs.most_common()
        },
        "area_group_to_temp_zone_mismatches": zone_mismatches,
        "face_type_auto_by_area_group": {
            f"{group!r} -> {face_type!r}": count
            for (group, face_type), count in pair_counts(faces, "areaGroupID", "faceTypeAuto").most_common()
        },
        "face_type_auto_values": value_counts(faces, "faceTypeAuto"),
        "name_triple": {
            "descName only": sum(
                f.non_nil("descName") and not f.non_nil("descNameAuto") for f in faces
            ),
            "descNameAuto only": sum(
                f.non_nil("descNameAuto") and not f.non_nil("descName") for f in faces
            ),
            "both": sum(f.non_nil("descName") and f.non_nil("descNameAuto") for f in faces),
            "descNameFreeze set": sum(f.non_nil("descNameFreeze") for f in faces),
            "descNameFreeze values": value_counts(faces, "descNameFreeze"),
        },
        "block_shapes": {
            ", ".join(sorted(shape)): count
            for shape, count in collections.Counter(b.keys for b in blocks).most_common()
        },
    }


def counted_values(counts: dict[str, int]) -> str:
    """A counted-value map as one markdown cell: `` `value`×n, `value`×n ``."""
    return ", ".join(f"`{value}`×{count}" for value, count in counts.items())


def _render_header() -> list[str]:
    return [
        "# Phase 1 — per-face attribute matrix",
        "",
        "Generated by [`face_attribute_matrix.py`](../spikes/phase1/face_attribute_matrix.py).",
        "Read-only; no corpus file was modified.",
        "",
        "Records are grouped by the entity that carries them, so every co-occurrence below was",
        "observed on a single face — not inferred from population arithmetic as in Phase 0.",
        "",
        "⚠ `model.dat` retains historical state. A *block* is one attribute dictionary that was",
        "written at some point, not necessarily a live entity. Co-occurrence within a block is",
        "sound evidence; a block count is not a census of the current model.",
        "",
    ]


def _render_precedence(results: list[dict[str, Any]]) -> list[str]:
    """Section 1.1's headline table: how each `*ID` / `*Auto` pair is populated, per model."""
    out = [
        "## 1.1 — `*ID` / `*Auto` precedence, per face",
        "",
        "`auto only` is the decisive column: faces a naive *prefer `*ID`* rule would read as empty.",
        "",
        "| Model | version | faces | pair | ID only | auto only | both agree | both differ | neither |",
        "|---|---|--:|---|--:|--:|--:|--:|--:|",
    ]
    for result in results:
        for id_key, tally in result["generations"].items():
            out.append(
                f"| {result['model']} | {result['designPH_version']} | {result['face_blocks']} "
                f"| `{id_key}` | {tally['id_only']} | **{tally['auto_only']}** "
                f"| {tally['both_agree']} | {tally['both_differ']} | {tally['neither']} |"
            )
    return out


def _render_contested(results: list[dict[str, Any]]) -> list[str]:
    """Whether any face carries both generations of one datum -- i.e. whether precedence exists."""
    out = ["", "### Are the two generations ever both populated on one face?", ""]
    contested_total = sum(len(v) for r in results for v in r["contested"].values())
    if not contested_total:
        return out + [
            "**No — not once, on any face, in any of the 14 corpus models.** Every `both agree` and",
            "`both differ` cell above is zero.",
            "",
            "This reframes section 1.1. `*ID` and `*Auto` are not two competing answers needing a",
            "precedence rule; they are **complementary and mutually exclusive per face**. The read",
            "rule is a coalesce, not a precedence:",
            "",
            "```",
            "value = face[*ID] or face[*Auto]     # never both; order is therefore moot",
            "```",
            "",
        ]

    out += [
        f"**Yes — {contested_total} faces carry both.** A precedence rule is genuinely required.",
        "",
    ]
    for result in results:
        for id_key, examples in result["contested"].items():
            out.append(f"- `{result['model']}` `{id_key}` — e.g. {examples[0]}")
    out.append("")
    return out


def _render_auto_only(results: list[dict[str, Any]]) -> list[str]:
    """The decisive case: faces holding an `*Auto` value and no `*ID` value."""
    out = [
        "### Faces carrying an `*Auto` value and no `*ID` value",
        "",
        "The case Phase 0 flagged as the one that decides the reader: if it exists, *prefer `*ID`*",
        "loses data exactly as the refuted version rule did.",
        "",
        "| Model | pair | faces | `*Auto` values |",
        "|---|---|--:|---|",
    ]
    auto_only_total = 0
    for result in results:
        for id_key, detail in result["auto_only"].items():
            auto_only_total += detail["count"]
            values = counted_values(detail["auto_values"])
            out.append(f"| {result['model']} | `{id_key}` | **{detail['count']}** | {values} |")
    if not auto_only_total:
        out += ["| — | — | 0 | none in any model |"]

    out += ["", f"**{auto_only_total} such faces across the corpus.** A worked example:", ""]
    worked_example = next(
        (detail["examples"][0] for r in results for detail in r["auto_only"].values()), None
    )
    if worked_example is not None:
        out += ["```", repr(worked_example), "```", ""]
    return out


def _render_untagged(results: list[dict[str, Any]]) -> list[str]:
    out = [
        "### Faces designPH did not classify, by `faceTypeAuto` (section 1.5 input)",
        "",
        "`areaGroupID` is `'n'` or absent. These are the candidates for shading geometry — and the",
        "ones that must *not* become shading geometry.",
        "",
        "| Model | untagged faces | by `faceTypeAuto` |",
        "|---|--:|---|",
    ]
    for result in results:
        if not result["untagged_faces"]:
            continue
        split = counted_values(result["untagged_by_face_type"])
        out.append(f"| {result['model']} | {result['untagged_faces']} | {split} |")
    out.append("")
    return out


def _render_zone_pairs(results: list[dict[str, Any]]) -> list[str]:
    """Section 1.3: the observed `areaGroup` -> `tempZone` pairs, against Phase 0 Finding 1."""
    out = ["", "## 1.3 — `areaGroup` → `tempZone`, per face", ""]
    for result in results:
        mismatches = result["area_group_to_temp_zone_mismatches"]
        if mismatches:
            verdict = f"⚠ {sum(mismatches.values())} faces disagree"
        else:
            verdict = "✅ matches Phase 0 Finding 1"
        out += [f"**{result['model']}** — {verdict}", "", "| pair | faces |", "|---|--:|"]
        out += [f"| `{pair}` | {count} |" for pair, count in result["area_group_to_temp_zone"].items()]
        if mismatches:
            out += ["", "Disagreeing pairs: " + ", ".join(f"`{k}` ({v})" for k, v in mismatches.items())]
        out.append("")
    return out


def _render_face_type(results: list[dict[str, Any]]) -> list[str]:
    out = ["## 1.3 — `faceTypeAuto`", "", "| Model | values | by area group |", "|---|---|---|"]
    for result in results:
        values = result["face_type_auto_values"]
        if not values:
            continue
        out.append(
            f"| {result['model']} | {counted_values(values)} "
            f"| {counted_values(result['face_type_auto_by_area_group'])} |"
        )
    return out


def _render_name_triple(results: list[dict[str, Any]]) -> list[str]:
    out = ["", "## 1.3 — the `descName` triple", "",
           "| Model | descName only | descNameAuto only | both | Freeze set | Freeze values |",
           "|---|--:|--:|--:|--:|---|"]
    for result in results:
        triple = result["name_triple"]
        out.append(
            f"| {result['model']} | {triple['descName only']} | {triple['descNameAuto only']} "
            f"| {triple['both']} | {triple['descNameFreeze set']} "
            f"| {counted_values(triple['descNameFreeze values']) or '—'} |"
        )
    return out


def _render_block_shapes(results: list[dict[str, Any]]) -> list[str]:
    out = ["", "## Block shapes", "",
           "The distinct key sets written together on one entity. A shape is a strong hint about",
           "what designPH did to that face: a full shape is a classified surface, a bare",
           "`tempZoneAuto` is a face designPH looked at and did not classify.", ""]
    for result in results:
        out += [f"### {result['model']}", "", "| n | keys |", "|--:|---|"]
        out += [f"| {count} | `{shape}` |" for shape, count in result["block_shapes"].items()]
        out.append("")
    return out


def render(results: list[dict[str, Any]]) -> str:
    """The report, section by section in the order they appear in the markdown."""
    sections = [
        _render_header(),
        _render_precedence(results),
        _render_contested(results),
        _render_auto_only(results),
        _render_untagged(results),
        _render_zone_pairs(results),
        _render_face_type(results),
        _render_name_triple(results),
        _render_block_shapes(results),
    ]
    return "\n".join(line for section in sections for line in section)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+", type=Path)
    ap.add_argument("--md", type=Path, help="write the markdown report here")
    ap.add_argument("--json", type=Path, help="write the machine-readable result here")
    args = ap.parse_args()

    results: list[dict[str, Any]] = []
    for path in args.models:
        if not path.exists():
            print(f"skipping missing model: {path}", file=sys.stderr)
            continue
        results.append(analyse(path))
        print(f"read {path.name}: {results[-1]['face_blocks']} face blocks", file=sys.stderr)

    if not results:
        print("no models read", file=sys.stderr)
        return 1

    report = render(results)
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(report + "\n")
        print(f"wrote {args.md}", file=sys.stderr)
    else:
        print(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2, default=str))
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
