"""`html/boot.py` -- the Python entry surface the dialog boots into.

It lives in the extension tree because it ships there, but it is deliberately host-agnostic and
runs unmodified on native CPython 3.11. Testing it here is what makes a failure inside SketchUp
attributable to the *host* rather than to this code -- the Phase 3 method rule.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from dph_translator.contract import parse

REPO = Path(__file__).resolve().parents[3]
BOOT_PY = REPO / "poc/ext/dph_plus_poc/html/boot.py"
PYPROJECT = REPO / "poc/py/pyproject.toml"


def pinned_versions() -> dict[str, str]:
    """`poc/py/pyproject.toml` is the one place the payload is pinned; `tools/vendor_payload.py`
    reads the same list. Restating a version in a test would be a fourth copy to drift."""
    pins = {}
    for requirement in tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]:
        name, _, version = requirement.partition("==")
        pins[name.strip()] = version.strip()
    return pins


def _load_boot() -> ModuleType:
    """A fresh module each time -- `import_stack` memoises, and that is under test."""
    spec = importlib.util.spec_from_file_location("dph_boot_under_test", BOOT_PY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def boot() -> ModuleType:
    return _load_boot()


def test_honeybee_ph_is_imported_last(boot: ModuleType) -> None:
    """Its `_extend_` hooks graft `.properties.ph` onto honeybee's own classes, so anything
    imported after it would be measuring a different runtime from the translator's."""
    assert boot.IMPORT_SEQUENCE[-1] == "honeybee_ph"


def test_import_stack_reports_versions_and_timings(boot: ModuleType) -> None:
    result = json.loads(boot.import_stack())
    assert result["ok"] is True
    assert result["failed"] == {}
    assert set(result["import_ms"]) == set(boot.IMPORT_SEQUENCE)
    assert result["versions"] == pinned_versions()


def test_the_reported_distributions_are_exactly_the_pinned_payload(boot: ModuleType) -> None:
    """The venv the tests run in and the wheels the `.rbz` ships must be the same set. If they are
    not, a green suite says nothing about what SketchUp will load."""
    assert set(boot.DISTRIBUTIONS) == set(pinned_versions())


def test_the_seam_probe_is_a_valid_contract_document(boot: ModuleType) -> None:
    """`_SEAM_PROBE` is hand-written and ships inside the `.rbz`, so a contract bump could leave the
    self-test exercising a shape no collector emits. Hold it against the live parser."""
    extraction = parse(boot._SEAM_PROBE)
    assert len(extraction.faces) == 1
    assert extraction.faces[0].error is None


def test_import_stack_is_measured_once_not_re_timed(boot: ModuleType) -> None:
    """A second call must replay the first measurement. Re-timing cached imports reports ~0 ms,
    which reads as "the stack imported instantly" rather than as "this is not a measurement"."""
    first = boot.import_stack()
    assert boot.import_stack() == first


def test_self_test_passes_and_carries_a_verdict(boot: ModuleType) -> None:
    result = json.loads(boot.self_test())
    assert result["verdict"]["passed"] is True
    assert [check["label"] for check in result["verdict"]["checks"]] == [
        "stack imports",
        "builds and reloads a model",
        "translator seam reachable",
    ]
    assert result["steps"]["model_round_trip"]["rooms"] == 1
    assert result["steps"]["translator_seam"]["ok"] is True


def test_self_test_reports_the_boots_own_import_timing(boot: ModuleType) -> None:
    booted = json.loads(boot.import_stack())
    assert json.loads(boot.self_test())["steps"]["imports"] == booted
