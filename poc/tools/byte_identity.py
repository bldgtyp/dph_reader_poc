# /// script
# requires-python = ">=3.11"
# ///
"""DesignPH-PLUS POC — is the translator's output a function of its input alone?

POC-4's gate turns on one claim, and it is worth stating precisely because two different things
get called "identical":

**(a)** for the *same extraction JSON*, the HBJSON is identical across **CPython 3.11**,
**Chromium 88** and **SketchUp**. That is what this tool establishes for the first two, over every
captured corpus fixture. If it fails, the translator behaves differently per host — a dict ordering,
a float repr, a locale — and every downstream comparison in the project is built on sand.

⚠ **"Identical" here means canonically identical, not byte-identical, and the reason is upstream.**
POC-4's plan asked for byte-identity; the stack cannot deliver it, and not because of the host —
**three consecutive runs on one CPython give three different hashes.** honeybee-ph mints a fresh
`uuid4` for every PH object and honeybee-energy orders four of its lists out of a `set`. The
canonicalisation below is narrow enough that everything a *host* could change still shows. The raw
hashes are measured and printed anyway, so the day upstream becomes deterministic, it is visible.

**(b)** for the *same unedited model*, the extraction JSONs are identical across sessions. That is
a claim about the **collector**, not the translator, and only Ed's SketchUp runs can test it. The
path-qualified persistent ids (contract §2.1) are what make it hold.

Keeping them apart is the point: once (a) holds, any difference SketchUp shows is attributable to
the host or the collector, never to the translation. Attribution before investigation.

⚠ **Scope: the HBJSON, not the whole envelope.** `translate_json` returns
`{"hbjson", "report", "verdict"}`; what is compared here is the `hbjson` field, because that is the
artefact that gets written and travels. The report's determinism across hosts is *not* covered —
it would need the browser leg to hand back a byte-faithful envelope, which the driver does not do.

⚠ **Run it on every fixture, not on Adelphi.** Adelphi is the simplest model in the corpus and it
has already masked three separate defects in this project's own harness by being so
(`00_Context/CONSTRAINTS.md` §9). Bluff Reach is the only model with thermal bridges; Linde is the
only one with multi-section framing; `250708` resolves nothing in-model.

⚠ **The Chromium leg is slow** — a full Pyodide boot per fixture, ~40-60 s each — which is why this
is `make identity` and not part of `make ci`. It is a per-phase check, not a per-edit one.

Usage:
    uv run poc/tools/byte_identity.py                       # every fixture in poc/_private/fixtures
    uv run poc/tools/byte_identity.py --cpython-only        # skip the browser, ~2 s
    uv run poc/tools/byte_identity.py FIXTURE.extraction.json ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
POC = HERE.parent
REPO = POC.parent
VENV_PYTHON = POC / "py" / ".venv" / "bin" / "python"
FIXTURES = POC / "_private" / "fixtures"
WORK = POC / "_private" / "identity"

#: Runs inside the translator's own venv — the eight vendored wheels and nothing else — so what is
#: hashed here is what SketchUp will run, not what this script's interpreter happens to have.
#: `translate_json` is the frozen seam (POC-1 §4.1); calling anything else would measure a path the
#: dialog never takes.
#:
#: ⚠ `translate_json` returns the **envelope** — `{"hbjson", "report", "verdict"}` — not the HBJSON.
#: Hashing what it returns compares a different artefact from the one `--hbjson-out` writes on the
#: browser leg, and the first run of this tool duly reported 5 of 5 fixtures as differing, with the
#: CPython side 180 KB larger every time. The size gap is what gave it away: a float repr or a dict
#: ordering moves bytes, not 60 % of them. **A cross-host comparison has to extract the same field
#: on both sides**, and the field is the one that gets written to disk.
TRANSLATE = """
import json, sys
sys.path.insert(0, {py!r})
import dph_translator.entry as entry

payload = open({extraction!r}, encoding="utf-8").read()
envelope = json.loads(entry.translate_json(payload))
open({out!r}, "wb").write(envelope["hbjson"].encode("utf-8"))
"""


# ---------------------------------------------------------------------------------------------
# Canonicalisation — and why a raw hash is not the gate
# ---------------------------------------------------------------------------------------------
#
# ⚠ **The translator's output is not byte-stable, and not because of the host.** Three consecutive
# runs on ONE CPython produce three different hashes. Two upstream causes, measured 2026-08-21 on
# all five fixtures, neither of them ours and neither fixable from here:
#
#   1. `honeybee_ph/_base.py` gives every newly CONSTRUCTED PH object a fresh `uuid.uuid4()` —
#      **152 distinct** on Adelphi, appearing 301 times because `_Base` also seeds `display_name`
#      from the identifier. ✅ Not an upstream defect: `from_dict` restores the stored id, so a
#      round trip preserves 152 of 152. The churn is ours, from building fresh PH objects each
#      export out of a designPH source with no persistent id for a site or a floor segment.
#   2. `honeybee_energy/properties/model.py` builds its material and construction lists with
#      `list(set(...))`. Four lists, ordered by `PYTHONHASHSEED`, which CPython randomises per
#      process. Same content, same length — which is why the files came out byte-for-byte the same
#      SIZE and a different hash, the signature that sent this looking for ordering rather than
#      arithmetic.
#
# So the gate is **canonical** equivalence, and the canonicalisation is deliberately narrow — it
# must not be able to hide a real difference:
#
#   * UUID-shaped strings become `«uuid:N»`, numbered by first appearance in a fixed traversal.
#     ⚠ Numbering rather than blanking keeps *aliasing* visible: two fields that share a UUID still
#     share a token, so a segment pointing at the wrong site is still a difference.
#   * Only the FOUR lists named above are sorted. ⚠ Sorting every list would be catastrophic —
#     `boundary` vertex order defines a face's orientation, and a canonicaliser that reorders
#     geometry would call two differently-facing walls identical.
#
# Anything else a host could change — float repr, dict ordering, encoding, locale-dependent
# formatting — survives this untouched, which is what makes the check still worth running.

#: Lists whose order carries no meaning, by dotted path from the document root. Anything not named
#: here keeps its order and is compared as-is.
UNORDERED_PATHS = frozenset(
    {
        "properties.energy.materials",
        "properties.energy.constructions",
        "properties.energy.global_construction_set.materials",
        "properties.energy.global_construction_set.constructions",
    }
)

UUID_PATTERN = re.compile(r"\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def canonicalise(document: Any) -> Any:
    """Replace per-run UUIDs with stable tokens and sort the known-unordered lists."""
    seen: dict[str, str] = {}

    def token(value: str) -> str:
        if value not in seen:
            seen[value] = f"«uuid:{len(seen)}»"
        return seen[value]

    def walk(node: Any, path: str) -> Any:
        if isinstance(node, dict):
            return {key: walk(value, f"{path}.{key}" if path else key) for key, value in node.items()}
        if isinstance(node, list):
            items = [walk(item, path) for item in node]
            if path in UNORDERED_PATHS:
                items.sort(key=lambda item: json.dumps(item, sort_keys=True))
            return items
        if isinstance(node, str) and UUID_PATTERN.match(node):
            return token(node)
        return node

    return walk(document, "")


@dataclass(frozen=True)
class Leg:
    """One host's answer for one fixture."""

    host: str
    digest: str | None
    canonical: str | None
    size: int
    uuids: int = 0
    detail: str = ""


@dataclass
class Outcome:
    fixture: str
    legs: list[Leg]

    @property
    def _canonical(self) -> set[str]:
        return {leg.canonical for leg in self.legs if leg.canonical}

    @property
    def identical(self) -> bool:
        # ⚠ Two ways this reads as a pass while proving nothing, and both have to be closed here:
        # a fixture where every leg FAILED has exactly one distinct digest — none — and a run with
        # a single leg is trivially self-consistent. Identity is a claim about *hosts*, so it takes
        # at least two of them.
        return len(self.legs) > 1 and all(leg.canonical for leg in self.legs) and len(self._canonical) == 1

    @property
    def byte_identical(self) -> bool:
        """The stronger claim, reported but not gated on — see the note above."""
        digests = {leg.digest for leg in self.legs if leg.digest}
        return len(self.legs) > 1 and len(digests) == 1 and all(leg.digest for leg in self.legs)


def measure(path: Path, host: str) -> Leg:
    raw = path.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    canonical = canonicalise(document)
    return Leg(
        host=host,
        digest=hashlib.sha256(raw).hexdigest(),
        canonical=hashlib.sha256(json.dumps(canonical, sort_keys=True).encode("utf-8")).hexdigest(),
        size=len(raw),
        uuids=sum(1 for _ in re.finditer(UUID_PATTERN.pattern[2:-2], raw.decode("utf-8"))),
    )


def under_cpython(extraction: Path, destination: Path) -> Leg:
    if not VENV_PYTHON.exists():
        return Leg("cpython3.11", None, None, 0, detail=f"no venv at {VENV_PYTHON} — run `make venv`")
    source = TRANSLATE.format(py=str(POC / "py"), extraction=str(extraction), out=str(destination))
    result = subprocess.run([str(VENV_PYTHON), "-c", source], capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()
        return Leg("cpython3.11", None, None, 0, detail=tail[-1] if tail else "no output")
    return measure(destination, "cpython3.11")


def under_chromium(extraction: Path, destination: Path, chrome: Path | None) -> Leg:
    # ⚠ `--out-dir` is not optional here. `verify_in_chrome.py` defaults its baseline to
    # `planning/POC/RESULTS/baselines/`, which is **committed** — and its baseline embeds the first
    # 400 characters of the translated model. Run on a real fixture with the default, and client
    # HBJSON lands in the repo. It did, once, before this line existed. Everything this tool touches
    # goes under `_private/`.
    command = [
        "uv",
        "run",
        str(HERE / "verify_in_chrome.py"),
        "--extraction",
        str(extraction),
        "--hbjson-out",
        str(destination),
        "--out-dir",
        str(destination.parent),
        "--tag",
        f"_{destination.stem}",
    ]
    if chrome:
        command += ["--chrome", str(chrome)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not destination.exists():
        tail = (result.stdout + result.stderr).strip().splitlines()
        return Leg("chromium88", None, None, 0, detail=tail[-1] if tail else "no output")
    return measure(destination, "chromium88")


def from_sketchup(stem: str) -> Leg | None:
    """Ed's own run, if it is on disk.

    Optional by design: this tool is the agent's gate and must be runnable with no SketchUp
    session behind it. When the file *is* there it joins the comparison as a third leg — but it
    only means anything if it was produced from **this same extraction**, which is what the
    runbook's toggle is for (`POC-4_ed-runbook.md`).
    """
    candidate = FIXTURES / f"{stem}.sketchup.hbjson"
    if not candidate.exists():
        return None
    return measure(candidate, "sketchup")


def report(outcomes: list[Outcome]) -> bool:
    print("\n  fixture                              host           bytes  uuids  canonical sha256")
    for outcome in outcomes:
        for index, leg in enumerate(outcome.legs):
            label = outcome.fixture if index == 0 else ""
            if leg.canonical:
                print(f"  {label:<36} {leg.host:<12} {leg.size:>7} {leg.uuids:>6}  {leg.canonical[:16]}")
            else:
                print(f"  {label:<36} {leg.host:<12} {'—':>7} {'—':>6}  FAILED: {leg.detail}")
    single = all(len(outcome.legs) < 2 for outcome in outcomes) and bool(outcomes)
    passed = all(outcome.identical for outcome in outcomes) and bool(outcomes)
    headline = "INCONCLUSIVE — one host only" if single else ("PASSED" if passed else "FAILED")
    print(f"\n  ================ {headline} ================")
    for outcome in outcomes:
        mark = "ok    " if outcome.identical else ("·     " if len(outcome.legs) < 2 else "FAIL  ")
        hosts = ", ".join(leg.host for leg in outcome.legs)
        print(f"  {mark}{outcome.fixture}  ({hosts})")
    if single:
        print("\n  A single host cannot disagree with itself. Drop --cpython-only for the real check.")
    if not outcomes:
        print("  no fixtures — poc/_private/fixtures is gitignored client data; capture it first")

    # Reported, never gated on — and reported even when it is uniformly false, because the day it
    # starts holding is the day the upstream non-determinism was fixed and somebody should notice.
    byte_ok = sum(1 for outcome in outcomes if outcome.byte_identical)
    uuids = max((leg.uuids for outcome in outcomes for leg in outcome.legs), default=0)
    if outcomes and not single:
        print(f"\n  raw byte-identity: {byte_ok} of {len(outcomes)} — expected 0 while honeybee-ph")
        print(f"  mints a fresh uuid4 per object ({uuids} in the largest output) and honeybee-energy")
        print("  orders four lists out of a set. Neither is ours; see this file's header.")
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", nargs="*", type=Path, help="extraction JSONs (default: all)")
    parser.add_argument(
        "--cpython-only",
        action="store_true",
        help="skip the browser leg. Fast, and proves nothing about hosts — use it while iterating",
    )
    parser.add_argument("--chrome", type=Path, default=None, help="Chromium 88 binary")
    parser.add_argument("--work-dir", type=Path, default=WORK)
    args = parser.parse_args()

    fixtures = args.fixtures or sorted(FIXTURES.glob("*.extraction.json"))
    # ⚠ The pre-fix Adelphi capture is contract v1 evidence, not a fixture: a translator run against
    # it produces 0 of 46 apertures (`_private/MANIFEST.md`).
    fixtures = [path for path in fixtures if "PRE-FIX" not in path.name]
    args.work_dir.mkdir(parents=True, exist_ok=True)

    outcomes: list[Outcome] = []
    for extraction in fixtures:
        stem = extraction.name.replace(".extraction.json", "")
        print(f"\n{stem}")
        legs = [under_cpython(extraction, args.work_dir / f"{stem}.cpython.hbjson")]
        if not args.cpython_only:
            legs.append(under_chromium(extraction, args.work_dir / f"{stem}.chromium.hbjson", args.chrome))
        recorded = from_sketchup(stem)
        if recorded:
            legs.append(recorded)
        for leg in legs:
            print(f"  {leg.host:<12} {leg.digest[:16] if leg.digest else 'FAILED: ' + leg.detail}")
        outcomes.append(Outcome(stem, legs))

    passed = report(outcomes)
    record = args.work_dir / "byte_identity.json"
    record.write_text(
        json.dumps(
            {
                "passed": passed,
                "cpython_only": args.cpython_only,
                "fixtures": [
                    {
                        "fixture": outcome.fixture,
                        "identical": outcome.identical,
                        "legs": [leg.__dict__ for leg in outcome.legs],
                    }
                    for outcome in outcomes
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\n  written: {record}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
