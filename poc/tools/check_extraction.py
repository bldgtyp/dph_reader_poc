# /// script
# requires-python = ">=3.11"
# ///
"""DesignPH-PLUS POC — reconcile a captured extraction against the offline baselines.

**This is the phase's evidential instrument.** Phases 0 and 1 already counted every designPH record
in all 14 corpus models, offline, key by key — `planning/RESULTS/baselines/corpus_baseline.json`.
That makes "did the live walk find everything?" a question with a real answer instead of a feeling,
and it is the only reason POC-2's Ed budget is two sessions.

The numbers are **read from the baseline**, never restated here: a hardcoded expectation would be a
second copy of a measurement, free to drift from the thing it was measured against.

⚠ **Live counts are expected to be ≤ the offline record counts, never >.** A `.skp` keeps prior
state, so the offline reader sees a historical *union* while the live walk sees only what exists
now. But when a live count undershoots by a lot, **ask which entity type is missing before assuming
history** — that is exactly how the thermal-bridge-on-edges finding was made, and assuming history
would have buried it.

Usage:
    uv run poc/tools/check_extraction.py ~/Desktop/dph_poc_copies/*.extraction.json
    uv run poc/tools/check_extraction.py --baseline <path> FILE...
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE = REPO / "planning" / "RESULTS" / "baselines" / "corpus_baseline.json"

CONTRACT_VERSION = 2

#: The coalesced pair. Offline these are counted per key; a face carries exactly one of them, so
#: the sum is the number of entities that were ever area-group tagged.
AREA_GROUP_KEYS = ("areaGroupID", "areaGroupAuto")

#: PHPP area groups that are thermal bridges, and therefore live on edges rather than faces.
BRIDGE_GROUPS = {15, 16, 17}

#: Model-level keys the POC ships as tables (contract §5), plus the `layer_table_*` family.
SHIPPED_TABLES = ("assemblies_calc", "assemblies_ud", "connections_ud", "vent_ud", "ihg_ud")
LAYER_TABLE_PREFIX = "layer_table_"

#: The **only** numbers not derivable from the offline baseline, because they were measured a
#: different way: Phase 1's *live* SketchUp run. Everything else this file checks — classified face
#: counts, thermal-bridge counts, which tables a model carries, how many layer tables — is computed
#: from `corpus_baseline.json` per model, for all 14, rather than restated for three.
#:
#: That distinction is the whole design of this harness. A hardcoded 82 or 293 would be a second
#: copy of a measurement, free to drift from the thing it was measured against; a *live* window
#: count is a genuinely independent observation and belongs written down.
LIVE_MEASUREMENTS: dict[str, dict[str, int]] = {
    # `planning/RESULTS/PHASE-1_results.md`: `glued_to` resolved 46 of 46.
    "adelphi-designph.skp": {"windows_found": 46, "windows_glued": 46},
}


@dataclass
class Outcome:
    """One model's reconciliation. `notes` are observations, not failures."""

    name: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        self.checks.append((label, bool(ok), detail))

    def note(self, text: str) -> None:
        self.notes.append(text)

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"baseline not found at {path}")
    return json.loads(path.read_text())


def match_baseline(file_name: str, baseline: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Find the baseline entry for a captured model.

    Captures come from **copies**, so `adelphi-designph_COPY` has to reach `adelphi-designph.skp`.
    Matching is by normalised stem rather than by an alias table nobody would maintain.
    """
    stem = file_name.removesuffix(".skp")
    for suffix in ("_COPY", " copy", "-copy", " COPY"):
        stem = stem.removesuffix(suffix)
    wanted = stem.strip().casefold()
    for name, record in baseline.items():
        if name.removesuffix(".skp").strip().casefold() == wanted:
            return name, record
    return None


def area_group_records(record: dict[str, Any]) -> int:
    """How many entities the offline reader saw carrying either area-group key."""
    keys = record.get("face_keys") or {}
    return sum(int((keys.get(key) or {}).get("total", 0)) for key in AREA_GROUP_KEYS)


def area_group_histogram(record: dict[str, Any]) -> dict[int, int]:
    """Offline records per PHPP area group, coalescing the two key generations.

    They are mutually exclusive per entity, so summing them is a union and not a double-count.
    Values that do not parse as a positive integer — `'n'`, designPH's "not assigned" — are
    excluded, which is the same rule the collector classifies by.
    """
    histogram: dict[int, int] = {}
    keys = record.get("face_keys") or {}
    for key in AREA_GROUP_KEYS:
        for entry in (keys.get(key) or {}).get("values") or []:
            group = _as_int(entry.get("value"))
            if group is not None and group > 0:
                histogram[group] = histogram.get(group, 0) + int(entry.get("count", 0))
    return histogram


def expected_counts(record: dict[str, Any]) -> tuple[int, int]:
    """(classified faces, thermal-bridge edges) the offline baseline accounts for.

    Groups 15/16/17 are thermal bridges and live on `Sketchup::Edge`; everything else that
    classifies is a face. Splitting the histogram on that line is what lets **every** corpus model
    check its own edge count, rather than only the one model somebody thought to hardcode.
    """
    histogram = area_group_histogram(record)
    faces = sum(count for group, count in histogram.items() if group not in BRIDGE_GROUPS)
    bridges = sum(count for group, count in histogram.items() if group in BRIDGE_GROUPS)
    return faces, bridges


def reconcile(payload: dict[str, Any], baseline: dict[str, Any]) -> Outcome:
    model = payload.get("model") or {}
    counts = payload.get("counts") or {}
    faces = payload.get("faces") or []
    edges = payload.get("edges") or []
    windows = payload.get("windows") or []
    unclassified = (payload.get("unclassified") or {}).get("tagged_faces") or []
    tables = payload.get("tables") or {}
    file_name = str(model.get("file_name") or "?")

    outcome = Outcome(name=file_name)
    outcome.check(
        "contract version is current",
        payload.get("contract_version") == CONTRACT_VERSION,
        str(payload.get("contract_version")),
    )

    # --- the collector's census must agree with the collector's own output ----------------------
    outcome.check(
        "counts.faces_classified matches `faces`",
        counts.get("faces_classified") == len(faces),
        f"{counts.get('faces_classified')} vs {len(faces)}",
    )
    outcome.check(
        "counts.edges_tagged matches `edges`",
        counts.get("edges_tagged") == len(edges),
        f"{counts.get('edges_tagged')} vs {len(edges)}",
    )
    outcome.check(
        "counts.windows_found matches `windows`",
        counts.get("windows_found") == len(windows),
        f"{counts.get('windows_found')} vs {len(windows)}",
    )
    # Contract §6.1's invariant. The translator asserts it too; if it fails, the walk and the census
    # disagree, which is how a whole missing entity type announces itself.
    outcome.check(
        "census: classified + tagged-unclassified == faces_tagged",
        len(faces) + len(unclassified) == counts.get("faces_tagged"),
        f"{len(faces)} + {len(unclassified)} vs {counts.get('faces_tagged')}",
    )

    # --- identity ------------------------------------------------------------------------------
    for label, records in (("face", faces), ("edge", edges), ("window", windows)):
        ids = [r.get("id") for r in records]
        outcome.check(
            f"{label} ids are unique", len(ids) == len(set(ids)), f"{len(ids) - len(set(ids))} duplicate(s)"
        )

    # --- against the offline record counts -----------------------------------------------------
    #
    # ⚠ Two corrections, both found on 2026-08-21 when this check failed on three of four real
    # models and the data turned out to be right every time. Adelphi masked both, and this is the
    # house lesson again: a check confirmed on one model is confirmed on nothing.
    #
    # 1. **The baseline counts AREA-GROUP carriers; `faces_tagged` counts DICT carriers.** They are
    #    equal on Adelphi (1441/1441) and nowhere else: Bluff Reach has 576 faces carrying a
    #    `DesignPH_dict` of which only **194** carry an area group. 194 + 99 edges = 293 = the
    #    baseline, exactly. A face can hold `descNameAuto` or a cached `Material` and no group.
    # 2. **The baseline counts ENTITIES; a live walk counts PLACEMENTS.** `250708` ships 2456 face
    #    records over 1781 distinct persistent ids — 675 faces placed twice — and 1781 is the
    #    baseline, exactly. (Its twin `250703` shows the same 675: the embedded paths say both are
    #    the same Linde project.)
    #
    # So compare like with like: area-group carriers, deduplicated by the persistent id at the tail
    # of the path-qualified id (contract §2.1).
    offline = area_group_records(baseline)
    live_records = (
        [f for f in faces] + [u for u in unclassified if u.get("area_group") is not None] + [e for e in edges]
    )
    live = len({str(r.get("id", "")).rsplit("_", 1)[-1] for r in live_records})
    outcome.check(
        "live area-group entities <= offline records", live <= offline, f"{live} live vs {offline} offline"
    )
    placements = len(live_records) - live
    if placements:
        outcome.note(
            f"{placements} tagged face(s) are re-placements of an entity already counted — a "
            "component placed more than once. Each is a distinct envelope surface and ships its "
            "own record; only this comparison deduplicates."
        )
    if live < offline:
        outcome.note(
            f"{offline - live} offline record(s) have no live entity. Historical state is the "
            "usual cause — but ask WHICH ENTITY TYPE is missing before assuming it."
        )

    stamps = set(model.get("designph_versions") or [])
    known = set(baseline.get("versions") or [])
    outcome.check(
        "the version stamp is one the baseline recorded",
        stamps <= known or not stamps,
        f"{sorted(stamps)} vs {sorted(known)}",
    )
    if known - stamps:
        # Expected on Wellington: the `.skp` holds two stamps historically, the live API one.
        outcome.note(f"baseline also recorded {sorted(known - stamps)} — historical, not live")

    # --- entity-shape rules the contract guarantees ---------------------------------------------
    unnamed = [w for w in windows if not str(w.get("designph_name") or "").strip()]
    outcome.check("every window can be named in a report", not unnamed, f"{len(unnamed)} unnamed")
    bad_resolution = [w for w in windows if w.get("host_resolution") not in ("glued_to", "unresolved")]
    outcome.check("host_resolution is always one of the two legal values", not bad_resolution)

    off_group = [e for e in edges if _as_int(e.get("area_group")) not in BRIDGE_GROUPS]
    if off_group:
        # Legal contract data; the translator reports it. Worth surfacing here because a *lot* of
        # them would mean the edge walk is picking up something it should not.
        outcome.note(f"{len(off_group)} tagged edge(s) are not area group 15/16/17")

    dangling = _dangling_hosts(windows, faces)
    if dangling:
        outcome.note(f"{dangling} window(s) name a host that is not in `faces` (unclassified host)")

    # ⚠ **`desc_name` is not one of the mutually-exclusive pairs, and never was.**
    # `descName` is the user's typed name and `descNameAuto` is designPH's generated one — an
    # *override* pair, so both present is the ordinary state of a renamed face. Bluff Reach has 70,
    # all carrying real room names ("104C HALL", "100 FOYER"), and the coalesce does exactly the
    # documented thing: the user's name wins.
    #
    # Mutual exclusivity is a claim about `area_group` / `temp_zone` / `assembly`, where a second
    # value would mean two contradicting assignments. Those stay a hard failure — 0 across the
    # corpus so far. AGENTS.md hard rule 6 is narrowed to match.
    exclusive = [f for f in faces if set(f.get("both_generations") or ()) - {"desc_name"}]
    outcome.check(
        "no face carries both generations of a value key", not exclusive, f"{len(exclusive)} face(s)"
    )
    renamed = [f for f in faces if "desc_name" in (f.get("both_generations") or ())]
    if renamed:
        outcome.note(f"{len(renamed)} face(s) carry both descName and descNameAuto — renamed, normal")

    _apply_baseline_expectations(outcome, baseline, counts, windows, tables)
    return outcome


def _as_int(value: Any) -> int | None:
    try:
        return int(str(value).strip(), 10)
    except (TypeError, ValueError):
        return None


def _dangling_hosts(windows: list[dict[str, Any]], faces: list[dict[str, Any]]) -> int:
    """Referential integrity is deliberately loose (contract §4): a host may be unclassified."""
    known = {f.get("id") for f in faces}
    return sum(1 for w in windows if w.get("host_face_id") and w["host_face_id"] not in known)


def _apply_baseline_expectations(
    outcome: Outcome,
    baseline: dict[str, Any],
    counts: dict[str, Any],
    windows: list[dict[str, Any]],
    tables: dict[str, Any],
) -> None:
    """Everything the offline baseline can say about this model, said for every model.

    The counts are upper bounds, not equalities: a `.skp` keeps prior state, so the offline reader
    sees a historical union. What matters is that nothing live is *missing* — and, in particular,
    that the edge count is checked at all. A face-only walk loses every thermal bridge silently,
    and it does so on any model that has them, not just the one anybody thought to name.
    """
    expected_faces, expected_bridges = expected_counts(baseline)

    outcome.check(
        "classified faces <= the baseline's non-bridge groups",
        int(counts.get("faces_classified") or 0) <= expected_faces,
        f"{counts.get('faces_classified')} live vs {expected_faces} offline",
    )
    outcome.check(
        "thermal-bridge edges <= the baseline's 15/16/17 groups",
        int(counts.get("edges_tagged") or 0) <= expected_bridges,
        f"{counts.get('edges_tagged')} live vs {expected_bridges} offline",
    )
    if expected_bridges and not counts.get("edges_tagged"):
        # The loudest single check in this file. It is what a face-only walk fails.
        outcome.check(
            "a model with thermal bridges found some",
            False,
            f"baseline has {expected_bridges} on edges, the walk found 0",
        )

    # --- tables the model is known to carry -----------------------------------------------------
    #
    # ⚠ The baseline is an offline scan, so its key list is a **historical union** and the live
    # model may legitimately no longer carry a table (`DESIGNPH_DATA_MODEL.md` §8.7). Wellington is
    # the case: the baseline records `connections_ud`, `glazing_ud`, `tfa_calc` and `tfa_calc_ud`,
    # and the live model has none of them — consistent with its **0 tagged edges**, since a model
    # with no thermal bridges has nothing to connect.
    #
    # `counts.tables_found` is what separates the two, and it is why the contract ships it: it lists
    # every Marshal blob key found on the live model, shipped or not. Present-but-not-shipped is a
    # collector bug and stays a hard failure; absent-from-the-model-entirely is history.
    model_keys = set(baseline.get("model_keys") or {})
    found_live = set(counts.get("tables_found") or ())
    for name in SHIPPED_TABLES:
        if name in model_keys and name in found_live:
            outcome.check(f"`{name}` was collected", name in tables)
        elif name in model_keys:
            outcome.note(
                f"the baseline records `{name}` but the live model does not carry it — historical "
                "state, not a dropped table (it is absent from counts.tables_found too)"
            )
        else:
            # Absence is the *normal* case and a real expectation: Adelphi has no `connections_ud`
            # and no layer tables at all, which is exactly why it cannot test the tier-1 path.
            outcome.check(f"no `{name}` (the model has none)", name not in tables)

    expected_layers = len(baseline.get("layer_tables") or [])
    found_layers = [name for name in tables if name.startswith(LAYER_TABLE_PREFIX)]
    live_layers = len([n for n in found_live if n.startswith(LAYER_TABLE_PREFIX)])
    outcome.check(
        "every live layer_table_* was collected",
        len(found_layers) == live_layers,
        f"{len(found_layers)} shipped vs {live_layers} found live",
    )
    if live_layers != expected_layers:
        outcome.note(
            f"the baseline recorded {expected_layers} layer table(s), the live model has "
            f"{live_layers} — historical state"
        )

    # --- the one independent, live measurement --------------------------------------------------
    live = LIVE_MEASUREMENTS.get(baseline.get("_name", ""))
    if not live:
        return
    if "windows_found" in live:
        outcome.check(
            "window count matches Phase 1's live run",
            counts.get("windows_found") == live["windows_found"],
            f"{counts.get('windows_found')} vs {live['windows_found']}",
        )
    if "windows_glued" in live:
        glued = sum(1 for w in windows if w.get("host_resolution") == "glued_to")
        outcome.check(
            "every window host resolves via glued_to",
            glued == live["windows_glued"],
            f"{glued} vs {live['windows_glued']}",
        )


def report(outcome: Outcome) -> None:
    print(f"\n  == {outcome.name} ==  {'PASS' if outcome.passed else 'FAIL'}")
    for label, ok, detail in outcome.checks:
        print(f"  {'ok    ' if ok else 'FAIL  '}{label}{f'  ({detail})' if detail else ''}")
    for note in outcome.notes:
        print(f"  note  {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="extraction JSON captured by the console run")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args()

    baseline = load_baseline(args.baseline)
    outcomes: list[Outcome] = []
    for path in args.files:
        payload = json.loads(path.read_text())
        # ⚠ Try the file's own name too, and prefer it when the model's disagrees. `model.file_name`
        # comes from `Sketchup::Model#path`, which is the path the model was last saved to **on the
        # machine that saved it** — on `250703` that is `C:\Users\greg\OneDrive\…`, which matches no
        # baseline and names no model anyone here has. The name on disk is the one Ed chose.
        declared = str((payload.get("model") or {}).get("file_name") or "")
        matched = match_baseline(path.stem.replace(".extraction", ""), baseline) or match_baseline(
            declared, baseline
        )
        if matched is None:
            outcome = Outcome(name=path.name)
            outcome.check(
                "has an offline baseline to reconcile against",
                False,
                "no matching model in corpus_baseline.json",
            )
            outcomes.append(outcome)
            continue
        name, record = matched
        outcomes.append(reconcile(payload, {**record, "_name": name}))

    for outcome in outcomes:
        report(outcome)

    failed = [o for o in outcomes if not o.passed]
    print("\n" + "=" * 70)
    print(f"{len(outcomes) - len(failed)} of {len(outcomes)} model(s) reconciled")
    for outcome in failed:
        print(f"  FAILED: {outcome.name}")
    print("=" * 70)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
