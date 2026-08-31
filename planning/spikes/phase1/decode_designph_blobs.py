#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Phase 1 section 1.4 -- decode designPH's Marshal tables and resolve every assembly reference.

Phase 0 flagged a risk it did not chase: faces reference assemblies that have no `layer_table_<id>`
key anywhere in the model. Adelphi's faces reference `83ud`-`95ud` with **zero** `layer_table_*`
keys; Bluff Reach reaches `114ud` while carrying only `01ud`-`06ud`. PRD section 8.3 assumes
`layer_table_<id>` is the source and calls assemblies "the easiest place to be quietly wrong".

This decodes every base64 Marshal blob in each model (see `ruby_marshal.py` -- no Ruby involved and
nothing is instantiated), catalogues the table schemas, then checks every `assemblyID` and
`assemblyIDAuto` value carried by a face against what the model actually defines. Five outcomes
per reference, and the middle ones are the finding:

* **layers** -- a `layer_table_<id>` exists in the model, so the full build-up is readable.
* **model header** -- the assembly has a row in the model's `assemblies_*` table but no layer
  table. Its name and interface resistances are readable; its build-up is not.
* **shipped library** -- not in the model at all, but present in designPH's own installed CSV
  library (`--library-dir`). Readable only on a machine with that designPH version installed.
* **connection** -- the face is a thermal bridge (area group 15, 16 or 17), so its `assemblyID`
  names a `connections_ud` row (a Psi-value and an f_Rsi), not an assembly at all. There are two
  id namespaces sharing one face key, and which one applies is decided by the area group.
* **unresolved** -- referenced by a face and defined nowhere reachable. Must be reported, never
  defaulted (AGENTS.md hard rule 4).

Usage
-----
    uv run decode_designph_blobs.py MODEL.skp [MODEL.skp ...] \\
        --md   planning/01_sketchup-export/feasibility/RESULTS/PHASE-1_assembly-resolution.md \\
        --json planning/01_sketchup-export/feasibility/RESULTS/baselines/phase1_assemblies.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import collections
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ruby_marshal import MarshalError, Symbol, loads, to_jsonable  # noqa: E402
from skp_blocks import Block, read_blocks  # noqa: E402

DICT = "DesignPH_dict"

#: base64 of Marshal's `\x04\x08` format marker -- how a blob announces itself.
MARSHAL_PREFIX = "BAh"

#: Face keys naming an assembly. Both generations, because Phase 1 section 1.1 found they are
#: complementary per face: Linde `250708.skp` defines all 92 of its assignments in `assemblyIDAuto`
#: and none in `assemblyID`.
ASSEMBLY_REF_KEYS = ("assemblyID", "assemblyIDAuto")

LAYER_TABLE_PREFIX = "layer_table_"

#: How far a face's assembly reference can be resolved, in decreasing reach. See the module
#: docstring; `unresolved` is the one AGENTS.md hard rule 4 says must always be reported.
TIERS = ("layers", "model_header", "shipped_library", "connection", "unresolved")

#: PHPP area groups whose "surfaces" are thermal bridges entered as lengths, not areas
#: (Phase 0 Finding 1). A face in one of these groups points `assemblyID` at `connections_ud`.
THERMAL_BRIDGE_GROUPS = frozenset([15, 16, 17])

#: Face keys naming the face's PHPP area group, in the coalesce order Phase 1 section 1.1
#: established -- the two generations are complementary, never both present.
AREA_GROUP_KEYS = ("areaGroupID", "areaGroupAuto")

#: designPH's installed CSV libraries. Same `#,key,value` metadata convention as the Marshal
#: tables (DESIGNPH_FILE_FORMATS.md section 2); column 1 is the assembly id.
LIBRARY_CSVS = ("phpp_assemblies_ud.csv", "phpp_assemblies_cert.csv")

#: Where designPH installs on macOS. Overridable, and absent on a machine without designPH --
#: in which case the shipped-library tier is reported as unchecked rather than as empty.
DEFAULT_LIBRARY_DIR = Path.home() / (
    "Library/Application Support/SketchUp 2022/SketchUp/Plugins/designPH/data"
)


def read_library(library_dir: Path | None) -> dict[str, str]:
    """Assembly id -> source CSV, for every id designPH ships. Empty when the dir is absent."""
    if library_dir is None or not library_dir.is_dir():
        return {}
    library: dict[str, str] = {}
    for name in LIBRARY_CSVS:
        path = library_dir / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            first = line.split(",", 1)[0].strip().strip('"')
            if first and not first.startswith("#"):
                library.setdefault(first, name)
    return library


@dataclass
class Table:
    """One decoded designPH table: its `:TOKENS` schema and its data rows.

    The format is self-describing -- rows beginning `"#"` are metadata carrying the schema, and
    everything else is data. `vent_ud` and `ihg_ud` put the metadata at the *end*, so this scans
    for it rather than assuming a position (DESIGNPH_DATA_MODEL.md section 7).
    """

    key: str
    tokens: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    rows: list[list[Any]] = field(default_factory=list)
    note: str | None = None

    @property
    def ids(self) -> list[str]:
        """The first column of every data row -- the assembly/connection id, when there is one."""
        if not self.rows or (self.tokens and self.tokens[0] != "id"):
            return []
        return [str(row[0]) for row in self.rows if row]


def parse_table(key: str, decoded: Any) -> Table:
    table = Table(key)
    if not isinstance(decoded, list):
        table.note = f"not a table: decoded to {type(decoded).__name__}"
        return table

    for row in decoded:
        if isinstance(row, list) and row and row[0] == "#":
            name = str(row[1]) if len(row) > 1 else ""
            value = row[2] if len(row) > 2 else None
            if name == "TOKENS" and isinstance(value, list):
                table.tokens = [str(t) for t in value]
            else:
                table.meta[name] = value if not isinstance(value, Symbol) else str(value)
        elif isinstance(row, list):
            table.rows.append(row)
        else:
            # A flat, non-tabular blob (`vent_ud` is a single row of loose values).
            table.rows.append([row])
    return table


def decode_blobs(blocks: list[Block]) -> tuple[dict[str, Table], dict[str, str]]:
    """Decode every Marshal blob across a model's blocks. Returns (tables, failures)."""
    tables: dict[str, Table] = {}
    failures: dict[str, str] = {}

    for block in blocks:
        for key, value in block.values.items():
            if not isinstance(value, str) or not value.startswith(MARSHAL_PREFIX):
                continue
            if key in tables:
                continue  # a model touched by two designPH versions carries two model blocks
            try:
                tables[key] = parse_table(key, loads(base64.b64decode(value)))
            except (MarshalError, binascii.Error, IndexError, ValueError) as exc:
                failures[key] = f"{type(exc).__name__}: {exc}"
    return tables, failures


def coalesce(block: Block, keys: tuple[str, ...]) -> Any:
    """The first key of `keys` carrying a value on `block`, or None.

    Phase 1 section 1.1 found the `*ID` / `*Auto` generations are complementary per face and
    never both populated, so the order of `keys` never actually decides anything.
    """
    return next((block.values[k] for k in keys if block.non_nil(k)), None)


def analyse(path: Path, library: dict[str, str]) -> dict[str, Any]:
    blocks = read_blocks(path, DICT)
    tables, failures = decode_blobs(blocks)

    # What the model defines.
    layer_tables = {k[len(LAYER_TABLE_PREFIX):] for k in tables if k.startswith(LAYER_TABLE_PREFIX)}
    defined_headers = {aid for k, t in tables.items() if k.startswith("assemblies") for aid in t.ids}
    connection_ids = {cid for k, t in tables.items() if k.startswith("connections") for cid in t.ids}

    # What the faces ask for, and -- because the id namespace depends on it -- the area group
    # each asking face sits in.
    referenced: collections.Counter = collections.Counter()
    for block in blocks:
        assembly = coalesce(block, ASSEMBLY_REF_KEYS)
        if assembly is None:
            continue
        referenced[(str(assembly), coalesce(block, AREA_GROUP_KEYS))] += 1

    # Assembly id -> {"faces": how many faces reference it, "groups": their area groups}, per tier.
    resolution: dict[str, dict[str, dict[str, Any]]] = {tier: {} for tier in TIERS}
    for (aid, group), count in referenced.items():
        if group in THERMAL_BRIDGE_GROUPS and aid in connection_ids:
            tier = "connection"
        elif aid in layer_tables:
            tier = "layers"
        elif aid in defined_headers:
            tier = "model_header"
        elif aid in library:
            tier = "shipped_library"
        else:
            tier = "unresolved"
        entry = resolution[tier].setdefault(aid, {"faces": 0, "groups": []})
        entry["faces"] += count
        entry["groups"].append(group)

    return {
        "model": path.name,
        "tables": {
            key: {
                "tokens": table.tokens,
                "meta": {k: to_jsonable(v) for k, v in table.meta.items()},
                "row_count": len(table.rows),
                "sample_rows": [to_jsonable(r) for r in table.rows[:3]],
                "note": table.note,
            }
            for key, table in sorted(tables.items())
        },
        "decode_failures": failures,
        "layer_tables": sorted(layer_tables),
        "library_sources": sorted({library[a] for a in resolution["shipped_library"]}),
        "assembly_headers": sorted(defined_headers),
        "referenced": {f"{aid} (group {group})": c for (aid, group), c in referenced.most_common()},
        "connection_ids": sorted(connection_ids),
        "resolution": resolution,
        "faces_by_outcome": {
            tier: sum(e["faces"] for e in hits.values()) for tier, hits in resolution.items()
        },
    }


def generic_key(key: str) -> str:
    """Collapse the per-assembly `layer_table_<id>` keys onto one name, so schemas group."""
    return LAYER_TABLE_PREFIX + "<id>" if key.startswith(LAYER_TABLE_PREFIX) else key


def _render_header() -> list[str]:
    return [
        "# Phase 1 — assembly resolution and Marshal table schemas",
        "",
        "Generated by [`decode_designph_blobs.py`](../spikes/phase1/decode_designph_blobs.py).",
        "Read-only; no corpus file was modified, and nothing in the blobs was instantiated —",
        "[`ruby_marshal.py`](../spikes/phase1/ruby_marshal.py) parses the stream without running Ruby.",
        "",
    ]


def _render_resolution(results: list[dict[str, Any]]) -> list[str]:
    """The headline: how far each model's face references resolve, then the unresolved ones."""
    out = [
        "## Can a face's assembly be resolved from the model alone?",
        "",
        "Per PRD §8.3 and Phase 0's flagged risk, in four tiers of decreasing reach:",
        "",
        "- **layers** — a `layer_table_<id>` is in the model. The full build-up is readable.",
        "- **model header** — a row in the model's `assemblies_*` table, but no layer table.",
        "  Name and interface resistances are readable; the build-up is not.",
        "- **shipped library** — not in the model, but in designPH's installed CSV library.",
        "  Readable only on a machine carrying that designPH version.",
        "- **unresolved** — referenced by a face and defined nowhere reachable.",
        "",
        "| Model | face refs | layers | model header | shipped library | connection | unresolved |",
        "|---|--:|--:|--:|--:|--:|--:|",
    ]
    for result in results:
        by_outcome = result["faces_by_outcome"]
        out.append(
            f"| {result['model']} | {sum(result['referenced'].values())} "
            f"| {by_outcome['layers']} | {by_outcome['model_header']} "
            f"| {by_outcome['shipped_library']} | {by_outcome['connection']} "
            f"| **{by_outcome['unresolved']}** |"
        )

    unresolved_total = sum(r["faces_by_outcome"]["unresolved"] for r in results)
    library_total = sum(r["faces_by_outcome"]["shipped_library"] for r in results)
    out += [
        "",
        f"**Resolvable only outside the model: {library_total} references.** "
        f"**Unresolvable anywhere reachable: {unresolved_total}.**",
        "",
    ]
    if unresolved_total:
        out += ["| Model | assembly id | faces | area groups |", "|---|---|--:|---|"]
        for result in results:
            for aid, entry in sorted(result["resolution"]["unresolved"].items()):
                groups = ", ".join(f"`{g}`" for g in sorted(set(entry["groups"]), key=str))
                out.append(f"| {result['model']} | `{aid}` | {entry['faces']} | {groups} |")
        out.append("")
    return out


def _render_namespaces(results: list[dict[str, Any]]) -> list[str]:
    out = [
        "### The two id namespaces",
        "",
        "`assemblyID` does not always name an assembly. On a thermal-bridge face — PHPP area group",
        "15, 16 or 17, which are entered as *lengths* on the `Areas` worksheet, not areas — it names",
        "a `connections_ud` row carrying a Psi-value and an f_Rsi. Which namespace applies is decided",
        "by the face's area group, and nothing in the key name says so.",
        "",
        "| Model | thermal-bridge refs resolved via `connections_ud` |",
        "|---|--:|",
    ]
    for result in results:
        if result["faces_by_outcome"]["connection"]:
            out.append(f"| {result['model']} | {result['faces_by_outcome']['connection']} |")
    out.append("")
    return out


def _render_schemas(results: list[dict[str, Any]]) -> list[str]:
    """Section 1.4's deliverable: every distinct (table, `:TOKENS`) schema seen in the corpus."""
    out = ["## Table schemas found", "",
           "`:TOKENS` is the self-describing header designPH ships with each table.", "",
           "| Key | `:TOKENS` | rows | models |", "|---|---|--:|--:|"]
    schemas: dict[tuple[str, tuple[str, ...]], list[tuple[str, int]]] = collections.defaultdict(list)
    for result in results:
        for key, table in result["tables"].items():
            schemas[(generic_key(key), tuple(table["tokens"]))].append(
                (result["model"], table["row_count"])
            )
    for (key, tokens), seen in sorted(schemas.items()):
        columns = ", ".join(f"`{t}`" for t in tokens) or "— *(no `:TOKENS` row)*"
        rows = sum(count for _, count in seen)
        out.append(f"| `{key}` | {columns} | {rows} | {len({m for m, _ in seen})} |")
    return out


def _render_sample_rows(results: list[dict[str, Any]]) -> list[str]:
    """One worked sample per distinct table key, from whichever model shows it first."""
    out = ["", "## Sample rows", ""]
    shown: set[str] = set()
    for result in results:
        for key, table in result["tables"].items():
            generic = generic_key(key)
            if generic in shown or not table["sample_rows"]:
                continue
            shown.add(generic)
            out += [f"**`{generic}`** — from `{result['model']}`", "", "```"]
            out += [repr(row) for row in table["sample_rows"]]
            out += ["```", ""]
    return out


def _render_failures(results: list[dict[str, Any]]) -> list[str]:
    failures = {k: v for r in results for k, v in r["decode_failures"].items()}
    out = ["## Decode failures", ""]
    if failures:
        out.append("")  # the "none" line below is what fills this slot when nothing failed
        out += [f"- `{key}` — {reason}" for key, reason in sorted(failures.items())]
    else:
        out.append("None — every Marshal blob in the corpus decoded.")
    out.append("")
    return out


def render(results: list[dict[str, Any]]) -> str:
    """The report, section by section in the order they appear in the markdown."""
    sections = [
        _render_header(),
        _render_resolution(results),
        _render_namespaces(results),
        _render_schemas(results),
        _render_sample_rows(results),
        _render_failures(results),
    ]
    return "\n".join(line for section in sections for line in section)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("models", nargs="+", type=Path)
    ap.add_argument(
        "--library-dir",
        type=Path,
        default=DEFAULT_LIBRARY_DIR,
        help="designPH's installed CSV library folder (default: the macOS SketchUp 2022 path)",
    )
    ap.add_argument("--md", type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    library = read_library(args.library_dir)
    print(
        f"library: {len(library)} assembly ids from {args.library_dir}"
        if library
        else f"library: none found at {args.library_dir} — shipped-library tier unchecked",
        file=sys.stderr,
    )

    results: list[dict[str, Any]] = []
    for path in args.models:
        if not path.exists():
            print(f"skipping missing model: {path}", file=sys.stderr)
            continue
        results.append(analyse(path, library))
        print(
            f"read {path.name}: {len(results[-1]['tables'])} tables, "
            f"{results[-1]['faces_by_outcome']['unresolved']} unresolved refs",
            file=sys.stderr,
        )

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
