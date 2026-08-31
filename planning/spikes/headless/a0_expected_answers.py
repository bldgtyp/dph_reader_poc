# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike A, step 0 — derive every gate's EXPECTED answer from the evidence, not from the plan.

`HEADLESS-A_sdk-feasibility.md` states each gate's "right answer" in prose, from memory of the POC.
Prose drifts. This re-derives the same numbers from the artefacts that hold them — the five live
contract-v2 captures and the offline corpus baseline — and prints the table the SDK gates get
graded against.

Why it exists: this repo's most expensive recurring failure is grading against a remembered number.
The POC's own reconciler failed on three of four real captures with the data right every time,
because it compared *placements* to *entities* and *dict-carriers* to *area-group carriers*
(`00_Context/CONSTRAINTS.md` §9). An expected-value table nobody re-derived is that bug one level up.

**The counting basis, established here by measurement rather than assertion** (see `--verify`):

    contract-v2 `id` == "face_<persistent_id of each ancestor>_<own persistent_id>"
      → the WHOLE PATH is the PLACEMENT identity
      → the LEAF SEGMENT is the ENTITY identity (`persistent_id`)

  So `counts.faces_tagged` is a **placements** count, and deduplicating the emitted records on the
  leaf segment yields the **entity** count. Adelphi and Bluff Reach mask the distinction entirely
  (nothing in them is placed twice); Linde and 250708 are where it bites, 2466→1791 and 2456→1781.

  ⚠ The record's separate `entity_id` field is `entity.entityID`, which is **session-local** — it is
  not `persistent_id` and must never be compared across captures (Spike B identity gate).

The offline baseline is then reconciled against that entity basis on the one claim that is well
defined on both sides, exact on all five models (see `verify`):

    live classified FACES + live tagged EDGES  ==  offline integer-valued area groups

Bluff Reach's 194 + 99 == 293 is the only instance of the edge term in the corpus, and the offline
number is entity-type-blind, which is what made the POC's reconciler read it as a 576-vs-194
contradiction.

Reads only. Writes one JSON to an explicit --out (overview §4: every script names its output).

    uv run a0_expected_answers.py \
        --fixtures _private/fixtures --baseline _private/baselines/corpus_baseline.json \
        --out _private/out/a0_expected.json --verify
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CAPTURE_GLOB = "*_COPY.extraction.json"

# The capture's self-reported `model.file_name` is not a reliable key: Wellington's says
# "2523 Weiilington" (the backup's misspelling, no _COPY suffix) while its data matches the
# Wellington row of the corpus table. `Sketchup::Model#path` is documented-untrustworthy in this
# repo (CONSTRAINTS §9); this is that same fact showing up in the name field. Key on the FILE.
CAPTURE_TO_BASELINE = {
    "adelphi-designph_COPY.extraction.json": "adelphi-designph.skp",
    "2414_Bluff Reach_COPY.extraction.json": "2414_Bluff Reach.skp",
    "2523 Wellington_COPY.extraction.json": "2523 Wellington.skp",
    "250703 - Linde Residence_COPY.extraction.json": "250703 - Linde Residence.skp",
    "250708_COPY.extraction.json": "250708.skp",
}


def leaf(entity_path_id: str) -> str:
    """The entity identity: the last `persistent_id` in a contract-v2 path-qualified id.

    `pocs/01_sketchup-export/ext/dph_plus_poc/collector.rb:597` builds it as `([kind] + path + [persistent_id]).join("_")`
    and `pocs/01_sketchup-export/ext/tests/test_collector.rb:221` pins the two-placements case to
    `%w[face_50_51 face_52_51]` — same leaf, different path.
    """
    return entity_path_id.rsplit("_", 1)[-1]


@dataclass
class ModelExpectation:
    """What one live capture says the SDK must reproduce for that model."""

    capture_file: str
    self_reported_name: str
    baseline_key: str | None
    designph_versions: list[str]

    # --- Counting bases. These are three different questions and were conflated twice.
    placements_walked: int  # counts.faces_walked
    placements_tagged: int  # counts.faces_tagged — records emitted, one per PLACEMENT
    entities_tagged: int  # the same records deduplicated on leaf persistent_id
    entities_classified: int  # faces[] — carrying a resolvable area group
    entities_unclassified: int
    edges_tagged: int
    windows_found: int

    # --- G2
    area_groups: dict[str, int]
    temp_zones: dict[str, int]
    faces_with_both_generations: int

    # --- G1 / G6
    hosts_resolved: int
    host_resolution_methods: dict[str, int]
    distinct_host_faces: int
    hosts_reporting_inner_loops: int

    # --- G3
    edges_with_connection_ref: int

    # --- G4
    tables_found: list[str]
    layer_tables: int
    library_frame_types: int
    library_glazing_types: int

    host_face_ids: list[str] = field(default_factory=list)


def load_captures(fixtures: Path) -> dict[str, dict[str, Any]]:
    """Load the live captures, skipping the deliberately-defective PRE-FIX Adelphi.

    That one is kept for provenance (`planning/spikes/poc/solve_window_parent.py` reads it);
    grading against it would reproduce the very window-transform defect it records.
    """
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(fixtures.glob(CAPTURE_GLOB)):
        if "PRE-FIX" in path.name:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("contract_version") != 2:
            raise SystemExit(f"{path.name}: contract_version {data.get('contract_version')}, expected 2")
        out[path.name] = data
    if not out:
        raise SystemExit(f"no contract-v2 captures found in {fixtures}")
    return out


def expectation_for(capture_file: str, cap: dict[str, Any]) -> ModelExpectation:
    counts, faces, windows, edges = cap["counts"], cap["faces"], cap["windows"], cap["edges"]
    unclassified = cap["unclassified"]["tagged_faces"]

    all_ids = [f["id"] for f in faces] + [u["id"] for u in unclassified]
    hosts = [w["host_face_id"] for w in windows if w.get("host_face_id")]
    host_ids = sorted(set(hosts))
    by_id = {f["id"]: f for f in faces}
    tables = list(counts["tables_found"])

    return ModelExpectation(
        capture_file=capture_file,
        self_reported_name=cap["model"]["file_name"],
        baseline_key=CAPTURE_TO_BASELINE.get(capture_file),
        designph_versions=list(cap["model"].get("designph_versions") or []),
        placements_walked=counts["faces_walked"],
        placements_tagged=counts["faces_tagged"],
        entities_tagged=len({leaf(i) for i in all_ids}),
        entities_classified=len(faces),
        entities_unclassified=len({leaf(u["id"]) for u in unclassified}),
        edges_tagged=counts["edges_tagged"],
        windows_found=counts["windows_found"],
        area_groups=dict(sorted(Counter(str(f["area_group"]) for f in faces).items())),
        temp_zones=dict(sorted(Counter(str(f["temp_zone"]) for f in faces).items())),
        faces_with_both_generations=sum(1 for f in faces if f["both_generations"]),
        hosts_resolved=len(hosts),
        host_resolution_methods=dict(sorted(Counter(w.get("host_resolution") or "UNRESOLVED" for w in windows).items())),
        distinct_host_faces=len(host_ids),
        # ⚠ NOT a host test. A glued opening reduces face.area without creating a loop, so this is
        # true on almost no real host. Measured, so the trap stays a number instead of a memory.
        hosts_reporting_inner_loops=sum(1 for h in host_ids if by_id.get(h, {}).get("inner_loops")),
        edges_with_connection_ref=sum(1 for e in edges if e.get("connection_ref")),
        tables_found=tables,
        layer_tables=sum(1 for t in tables if t.startswith("layer_table_")),
        library_frame_types=len(cap["libraries"]["frame_types"]),
        library_glazing_types=len(cap["libraries"]["glazing_types"]),
        host_face_ids=host_ids,
    )


# Hard rule 6 — coalesce the key generations, never version-key them. ⚠ designPH's own naming is
# asymmetric: the area-group and temp-zone fallbacks DROP the "ID" while the assembly fallback keeps
# it. Reading `areaGroupIDAuto` finds nothing and loses 250708's 92 assemblies silently; the POC
# regresses it directly (POC-2 finding 50) and `00_Context/DATA_CONTRACTS.md` had the wrong key
# standing until 2026-08-28.
AREA_GROUP_KEYS = ("areaGroupID", "areaGroupAuto")


def baseline_classified(baseline_path: Path) -> dict[str, dict[str, Any]]:
    """Per-model CLASSIFIED-ENTITY counts from the offline binary parse — the historical union.

    An area group is *classified* when its value is an integer; the String `'n'` is designPH's
    "unclassified" marker and `nil` is a placeholder (count non-nil values, never records).

    ⚠ Two properties of this number that make it easy to mis-compare, both learned the hard way:

    - It is **entity-type-blind**. The offline parser sees attribute records, not entity classes, so
      Bluff Reach's 293 is 194 faces PLUS 99 thermal-bridge edges. Comparing it to a face count
      alone is one of the reconciler's three known false alarms.
    - There is **no well-defined offline "total tagged entities"** to compare against the live
      count. The baseline reports a total per *key*, not a union over entities, and the keys cover
      different subsets. So this function deliberately reports only the classified figure, which is
      exact, rather than manufacturing a union that would merely look rigorous.
    """
    if not baseline_path.exists():
        return {}
    raw = json.loads(baseline_path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for name, entry in raw.items():
        face_keys = entry.get("face_keys") or {}
        present = [k for k in AREA_GROUP_KEYS if k in face_keys]
        if not present:
            continue
        classified = sum(
            v["count"] for k in present for v in face_keys[k]["values"] if v["type"] not in ("str", "nil")
        )
        out[name] = {
            "classified_faces_and_edges": classified,
            "area_group_keys_present": present,
            "per_key_totals": {k: face_keys[k]["total"] for k in present},
            "versions": entry.get("versions") or [],
            "generation": entry.get("generation"),
            "layer_tables": len(entry.get("layer_tables") or []),
        }
    return out


def verify(exp: dict[str, ModelExpectation], base: dict[str, dict[str, Any]]) -> list[str]:
    """Cross-check the derived counting bases against the offline baseline.

    The one claim that is well defined on both sides, and it is exact on all five models:

        live classified FACES + live tagged EDGES  ==  offline integer-valued area groups

    Bluff Reach is the only model that exercises the edge term (194 + 99 == 293) and it is the only
    model that would catch a face-only reader. A check that fires is doing its job — but a check
    that can only fire on one of five models must say which one carries it.
    """
    out: list[str] = []
    for name, e in sorted(exp.items()):
        if e.entities_classified + e.entities_unclassified != e.entities_tagged:
            out.append(f"FAIL {name}: classified+unclassified != entities_tagged (leaf ids collide across the two lists)")
        b = base.get(e.baseline_key or "")
        if b is None:
            out.append(f"SKIP {name}: no baseline entry for key {e.baseline_key!r}")
            continue
        live = e.entities_classified + e.edges_tagged
        off = b["classified_faces_and_edges"]
        carries_edges = " ← the only model exercising the edge term" if e.edges_tagged else ""
        out.append(
            f"{'ok  ' if live == off else 'FAIL'} {name}: classified faces({e.entities_classified})"
            f" + edges({e.edges_tagged}) = {live} vs offline {off}"
            f" [keys {'+'.join(b['area_group_keys_present'])}]{carries_edges}"
        )
    return out


def gate_table(exp: dict[str, ModelExpectation], base: dict[str, dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    add = lines.append

    def total(attr: str) -> int:
        return sum(getattr(e, attr) for e in exp.values())

    def merged(attr: str) -> dict[str, int]:
        c: Counter[str] = Counter()
        for e in exp.values():
            c.update(getattr(e, attr))
        return dict(sorted(c.items()))

    add("GATE  EXPECTED — measured from the five live contract-v2 captures (ENTITY basis unless noted)")
    add("=" * 100)
    add(f"G1    {total('hosts_resolved')}/{total('windows_found')} windows resolve to a host face; methods={merged('host_resolution_methods')}")
    add(
        f"      ⚠ 'host has inner loops' is TRUE on {total('hosts_reporting_inner_loops')} of "
        f"{total('distinct_host_faces')} distinct hosts corpus-wide "
        f"({ {e.self_reported_name: f'{e.hosts_reporting_inner_loops}/{e.distinct_host_faces}' for e in exp.values()} }) "
        "— glue leaves no loop, so loops.size>1 is NOT a host test"
    )
    add(f"G2    area groups: {merged('area_groups')}")
    add(f"      temp zones:  {merged('temp_zones')}")
    add(f"      faces carrying BOTH key generations: {total('faces_with_both_generations')} (descName override pairs — normal, not a contradiction)")
    edge_models = {e.self_reported_name: e.edges_tagged for e in exp.values() if e.edges_tagged}
    add(f"G3    edges carrying DesignPH_dict: {edge_models} — 0 on the other {len(exp) - len(edge_models)}")
    add(f"      connection_ref present on {total('edges_with_connection_ref')}/{total('edges_tagged')}")
    add(f"G4    model tables per model (layer_table_* counted separately):")
    for e in sorted(exp.values(), key=lambda x: x.capture_file):
        add(f"        {e.self_reported_name:<28} {len(e.tables_found):>2} tables ({e.layer_tables} layer_table_*): {', '.join(e.tables_found)}")
    add("G5    the three counting bases — the SDK must reproduce the ENTITY column, and the offline")
    add("      baseline is the historical union, a DIFFERENT question:")
    add(f"      {'model':<28} {'placements':>11} {'entities':>9} {'classified':>11} {'edges':>6}  offline baseline")
    for e in sorted(exp.values(), key=lambda x: x.capture_file):
        b = base.get(e.baseline_key or "", {})
        off = f"{b.get('classified_faces_and_edges', '?')} classified (faces+edges)" if b else "(not matched)"
        add(f"      {e.self_reported_name:<28} {e.placements_tagged:>11} {e.entities_tagged:>9} {e.entities_classified:>11} {e.edges_tagged:>6}  {off}")
    add(f"G6    net-vs-gross probe set = {total('distinct_host_faces')} distinct host faces "
        f"({ {e.self_reported_name: e.distinct_host_faces for e in exp.values()} })")
    add(f"G7    {total('windows_found')} window world transforms + {total('entities_classified')} classified face loops, within 1 mm")
    add("G8    designPH version stamps that must open:")
    for e in sorted(exp.values(), key=lambda x: x.capture_file):
        b = base.get(e.baseline_key or "", {})
        add(f"        {e.self_reported_name:<28} {', '.join(e.designph_versions) or '(unstamped)':<10} baseline generation: {b.get('generation', '?')}")
    add("=" * 100)
    add(
        f"CORPUS TOTALS (entity basis): {len(exp)} models · {total('entities_classified')} classified faces · "
        f"{total('windows_found')} windows · {total('edges_tagged')} edges · {total('entities_tagged')} dict-carrying face entities "
        f"(= {total('placements_tagged')} placements)"
    )
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", type=Path, required=True, help="dir of live contract-v2 captures")
    ap.add_argument("--baseline", type=Path, required=True, help="offline corpus_baseline.json")
    ap.add_argument("--out", type=Path, required=True, help="explicit output path under _private/")
    ap.add_argument("--verify", action="store_true", help="cross-check the derived bases against the offline baseline")
    args = ap.parse_args()

    captures = load_captures(args.fixtures)
    exp = {name: expectation_for(name, cap) for name, cap in captures.items()}
    base = baseline_classified(args.baseline)

    print("\n".join(gate_table(exp, base)))

    checks: list[str] = []
    if args.verify:
        checks = verify(exp, base)
        print("\nVERIFY — live entity counts vs the offline baseline (like for like)")
        print("\n".join("  " + c for c in checks))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "note": "Spike A expected answers, re-derived from the live captures. Grade the SDK against THIS, not the plan's prose.",
                "counting_basis": {
                    "id_format": "kind_<ancestor persistent_ids...>_<own persistent_id>",
                    "placement_identity": "the whole path-qualified id",
                    "entity_identity": "the leaf segment (persistent_id)",
                    "entity_id_field": "entity.entityID — SESSION-LOCAL, never compare across captures",
                    "offline_equivalent": "corpus_baseline face_keys.areaGroupID.total",
                },
                "models": {n: asdict(e) for n, e in sorted(exp.items())},
                "offline_baseline_classified": base,
                "verify": checks,
            },
            indent=1,
        )
    )

    failed = [c for c in checks if c.startswith("FAIL")]
    verdict = "FAIL" if failed else "DERIVED"
    print(
        f"\nVERDICT a0: {verdict} — {len(exp)} live captures · "
        f"{sum(e.entities_classified for e in exp.values())} classified faces · "
        f"{sum(e.windows_found for e in exp.values())} windows · "
        f"{sum(e.edges_tagged for e in exp.values())} edges"
        + (f" · {len(failed)} cross-check failures" if failed else " · all cross-checks agree")
        + f" → {args.out}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
