"""The reconciliation harness — tested before Ed is asked to produce its input.

`check_extraction.py` is POC-2's evidential instrument: it is what turns "did the live walk find
everything?" into a question with an answer. A harness that silently passes everything would be
worse than no harness, because the phase's gate is written in terms of it — so it is exercised here
against synthetic payloads built to satisfy, and to violate, each rule.

The **baseline it reads is real** (`planning/RESULTS/baselines/corpus_baseline.json`, all 14 corpus
models, measured offline in Phase 0). Only the extraction side is synthetic, and it proves nothing
about designPH — just that the comparison works.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
TOOL = REPO / "poc/tools/check_extraction.py"
BASELINE = REPO / "planning/RESULTS/baselines/corpus_baseline.json"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_extraction_under_test", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    return json.loads(BASELINE.read_text())


def adelphi_payload() -> dict[str, Any]:
    """A synthetic capture shaped like the Adelphi numbers Phases 0 and 1 recorded."""
    return {
        "contract_version": 2,
        "generated_by": "tests",
        "model": {"file_name": "adelphi-designph_COPY", "designph_versions": ["2.1.15"]},
        "counts": {
            "faces_walked": 8037,
            "faces_tagged": 1441,
            "faces_classified": 82,
            "edges_tagged": 0,
            "windows_found": 46,
            # ⚠ Must list everything the walk found on the model, shipped or not: the reconciler
            # now uses it to tell "the collector dropped a table" from "the live model does not
            # carry it any more", which is the difference between a bug and Wellington.
            "tables_found": ["assemblies_ud", "vent_ud", "ihg_ud"],
        },
        "faces": [{"id": f"face_{i}", "both_generations": []} for i in range(82)],
        "edges": [],
        "windows": [
            {
                "id": f"window_{i}",
                "designph_name": f"Window_{i}",
                "host_resolution": "glued_to",
                "host_face_id": "face_0",
            }
            for i in range(46)
        ],
        "tables": {
            "assemblies_ud": {"tokens": [], "rows": []},
            "vent_ud": {"tokens": [], "rows": []},
            "ihg_ud": {"tokens": [], "rows": []},
        },
        "unclassified": {"tagged_faces": [{"id": f"u_{i}"} for i in range(1359)]},
    }


def run(tool: ModuleType, baseline: dict[str, Any], payload: dict[str, Any]) -> Any:
    matched = tool.match_baseline(payload["model"]["file_name"], baseline)
    assert matched is not None
    name, record = matched
    return tool.reconcile(payload, {**record, "_name": name})


def failed_labels(outcome: Any) -> list[str]:
    return [label for label, ok, _ in outcome.checks if not ok]


def test_a_copy_reaches_the_original_baseline(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """Captures come from copies (hard rule 3), so `adelphi-designph_COPY` has to match."""
    assert tool.match_baseline("adelphi-designph_COPY", baseline)[0] == "adelphi-designph.skp"
    assert tool.match_baseline("2414_Bluff Reach", baseline)[0] == "2414_Bluff Reach.skp"
    assert tool.match_baseline("no such model", baseline) is None


def test_a_correct_adelphi_capture_reconciles(tool: ModuleType, baseline: dict[str, Any]) -> None:
    outcome = run(tool, baseline, adelphi_payload())
    assert failed_labels(outcome) == []
    assert outcome.passed


def test_the_offline_record_count_comes_from_the_baseline(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """1441 is Phase 0's measurement of Adelphi, not a number written into the harness."""
    assert tool.area_group_records(baseline["adelphi-designph.skp"]) == 1441


def test_the_expected_counts_are_derived_not_restated(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """Every number the plan quotes falls out of the offline histogram: Adelphi's 82 classified
    faces, and Bluff Reach's 194 + 99 = 293. Nothing is written down twice."""
    assert tool.expected_counts(baseline["adelphi-designph.skp"]) == (82, 0)
    assert tool.expected_counts(baseline["2414_Bluff Reach.skp"]) == (194, 99)
    # And it generalises to the models nobody hardcoded — Holmes has 42 bridges of its own.
    assert tool.expected_counts(baseline["2536 Holmes.skp"]) == (105, 42)


def bluff_reach_payload(edges: int) -> dict[str, Any]:
    return {
        "contract_version": 2,
        "generated_by": "tests",
        "model": {"file_name": "2414_Bluff Reach_COPY", "designph_versions": ["2.2.24"]},
        "counts": {
            "faces_walked": 500,
            "faces_tagged": 194,
            "faces_classified": 100,
            "edges_tagged": edges,
            "windows_found": 0,
            "tables_found": [f"layer_table_{i}" for i in range(6)]
            + ["assemblies_calc", "connections_ud", "vent_ud", "ihg_ud"],
        },
        "faces": [{"id": f"face_{i}", "both_generations": []} for i in range(100)],
        "edges": [{"id": f"edge_{i}"} for i in range(edges)],
        "windows": [],
        "tables": {f"layer_table_{i}": {} for i in range(6)}
        | {"assemblies_calc": {}, "connections_ud": {}, "vent_ud": {}, "ihg_ud": {}},
        "unclassified": {"tagged_faces": [{"id": f"u_{i}"} for i in range(94)]},
    }


def test_a_face_only_walk_of_bluff_reach_fails_loudly(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """The finding this whole phase is shaped around: 99 of Bluff Reach's 293 area-group carriers
    are on `Sketchup::Edge`. A face-only walk loses every thermal bridge **silently** — so the
    harness has to be the thing that is loud about it, and for any model with bridges, not just
    the one somebody remembered to name."""
    failures = failed_labels(run(tool, baseline, bluff_reach_payload(edges=0)))
    assert "a model with thermal bridges found some" in failures


def test_a_complete_bluff_reach_walk_reconciles(tool: ModuleType, baseline: dict[str, Any]) -> None:
    assert failed_labels(run(tool, baseline, bluff_reach_payload(edges=99))) == []


def test_more_bridges_than_the_baseline_recorded_is_a_failure(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    assert "thermal-bridge edges <= the baseline's 15/16/17 groups" in failed_labels(
        run(tool, baseline, bluff_reach_payload(edges=120))
    )


def test_a_broken_census_is_caught(tool: ModuleType, baseline: dict[str, Any]) -> None:
    payload = adelphi_payload()
    payload["unclassified"]["tagged_faces"] = payload["unclassified"]["tagged_faces"][:-1]
    assert "census: classified + tagged-unclassified == faces_tagged" in failed_labels(
        run(tool, baseline, payload)
    )


def test_duplicate_ids_are_caught(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """Two placements of one component must not collide — the reason ids are path-qualified."""
    payload = adelphi_payload()
    payload["faces"][1]["id"] = payload["faces"][0]["id"]
    assert "face ids are unique" in failed_labels(run(tool, baseline, payload))


def test_a_live_count_exceeding_the_offline_record_count_is_a_bug(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """Live ≤ historical always: a `.skp` keeps prior state, so the offline reader sees a union.
    More live entities than records means the walk is counting something that is not designPH's."""
    payload = adelphi_payload()
    payload["counts"]["faces_tagged"] = 2000
    payload["unclassified"]["tagged_faces"] = [{"id": f"u_{i}", "area_group": "8"} for i in range(1918)]
    assert "live area-group entities <= offline records" in failed_labels(run(tool, baseline, payload))


def test_a_face_with_no_area_group_is_not_an_area_group_carrier(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """⚠ The distinction that made this check fail on Bluff Reach while the data was right.

    The baseline counts entities carrying an **area-group key**; `faces_tagged` counts entities
    carrying a `DesignPH_dict` **at all** — and a face can hold `descNameAuto` or a cached
    `Material` and no group. On Bluff Reach that is 576 against 194, and 194 + 99 edges is the
    baseline exactly. Adelphi has no such face, which is why it never showed.
    """
    payload = adelphi_payload()
    payload["counts"]["faces_tagged"] = 4000
    payload["unclassified"]["tagged_faces"] = [{"id": f"u_{i}"} for i in range(3918)]
    assert failed_labels(run(tool, baseline, payload)) == []


def test_the_same_entity_placed_twice_is_counted_once_against_the_baseline(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """⚠ The other half of the same failure. A live walk visits **placements**; the offline reader
    sees **entities**. `250708` ships 2456 face records over 1781 distinct persistent ids — 675
    faces placed twice — and 1781 is the baseline exactly. Nothing tagged in Adelphi is placed
    twice, so again it never showed.

    Each placement is still a distinct envelope surface and still ships its own record; only this
    comparison deduplicates, and it says so in a note.
    """
    payload = adelphi_payload()
    payload["counts"]["faces_tagged"] = 2000
    payload["unclassified"]["tagged_faces"] = [
        # The same entity id under two different component paths — contract §2.1.
        {"id": f"face_{parent}_{i}", "area_group": "8"}
        for i in range(959)
        for parent in ("111", "222")
    ]
    outcome = run(tool, baseline, payload)
    assert failed_labels(outcome) == []
    assert any("re-placements" in note for note in outcome.notes)


def test_an_undershoot_is_a_note_not_a_failure_but_says_what_to_ask(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    payload = adelphi_payload()
    payload["counts"]["faces_tagged"] = 1400
    payload["unclassified"]["tagged_faces"] = [{"id": f"u_{i}", "area_group": "8"} for i in range(1318)]
    outcome = run(tool, baseline, payload)
    assert failed_labels(outcome) == []
    assert any("WHICH ENTITY TYPE" in note for note in outcome.notes)


def test_an_unnameable_window_is_caught(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """The contract guarantees `designph_name` is never null: every report line names its window."""
    payload = adelphi_payload()
    payload["windows"][0]["designph_name"] = ""
    assert "every window can be named in a report" in failed_labels(run(tool, baseline, payload))


def test_a_layer_table_found_live_but_not_shipped_is_caught(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """`layer_table_*` is a family, not a key, and Linde carries 28 of them. Dropping one is a
    collector bug that no face count would reveal."""
    payload = adelphi_payload()
    payload["counts"]["tables_found"] = [*payload["counts"]["tables_found"], "layer_table_01ud"]
    assert "every live layer_table_* was collected" in failed_labels(run(tool, baseline, payload))


def test_a_table_the_baseline_records_but_the_live_model_lacks_is_a_note(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """⚠ Wellington's case. The baseline is an **offline** scan, so its key list is a historical
    union (`DESIGNPH_DATA_MODEL.md` §8.7): it records `connections_ud`, and the live model has no
    such key and **0 tagged edges** — a model with no thermal bridges has nothing to connect.

    `counts.tables_found` is what separates that from a dropped table, and it is why the contract
    ships it. Present-live-but-not-shipped stays a hard failure; absent from the model entirely is
    history, and failing on it would block a model whose capture is correct.
    """
    payload = bluff_reach_payload(edges=99)
    payload["counts"]["tables_found"] = [
        n for n in payload["counts"]["tables_found"] if n != "connections_ud"
    ]
    del payload["tables"]["connections_ud"]
    outcome = run(tool, baseline, payload)
    assert failed_labels(outcome) == []
    assert any("historical state" in note for note in outcome.notes)


def test_a_table_found_live_but_not_shipped_is_still_a_failure(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """The other side of the same line: the walk saw it, and the collector did not ship it."""
    payload = bluff_reach_payload(edges=99)
    del payload["tables"]["connections_ud"]
    assert "`connections_ud` was collected" in failed_labels(run(tool, baseline, payload))


def test_a_table_the_model_carries_must_be_collected(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """Adelphi's `model_keys` name `assemblies_ud`, `vent_ud` and `ihg_ud`. Dropping one is a
    collector bug that no count would reveal."""
    payload = adelphi_payload()
    del payload["tables"]["assemblies_ud"]
    assert "`assemblies_ud` was collected" in failed_labels(run(tool, baseline, payload))


def test_a_table_the_model_does_not_carry_must_not_appear(tool: ModuleType, baseline: dict[str, Any]) -> None:
    payload = adelphi_payload()
    payload["tables"]["connections_ud"] = {}
    assert "no `connections_ud` (the model has none)" in failed_labels(run(tool, baseline, payload))


def test_both_generations_of_a_value_key_on_one_face_fails(
    tool: ModuleType, baseline: dict[str, Any]
) -> None:
    """Two contradicting assignments for one face. 0 across the corpus, live and offline."""
    payload = adelphi_payload()
    payload["faces"][0]["both_generations"] = ["assembly"]
    assert "no face carries both generations of a value key" in failed_labels(run(tool, baseline, payload))


def test_both_generations_of_desc_name_is_normal(tool: ModuleType, baseline: dict[str, Any]) -> None:
    """⚠ `desc_name` was never one of the mutually-exclusive pairs.

    `descName` is the user's typed name and `descNameAuto` is designPH's generated one — an
    *override* pair, so both present is simply a renamed face. Bluff Reach has 70, carrying real
    room names ("104C HALL", "100 FOYER"), and the coalesce does the documented thing: the user
    wins. Failing on it would have blocked a model whose data is correct.
    """
    payload = adelphi_payload()
    payload["faces"][0]["both_generations"] = ["desc_name"]
    outcome = run(tool, baseline, payload)
    assert failed_labels(outcome) == []
    assert any("descName and descNameAuto" in note for note in outcome.notes)
