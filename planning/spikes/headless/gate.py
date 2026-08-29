# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The POC's version gate (`poc/ext/dph_plus_poc/gate.rb`), ported for the headless reader.

The decision that stands between "a file arrived in a watched folder" and a translator: **is this a
designPH generation this reader understands?** Pure functions over plain data, exactly as the Ruby
original is, so every branch is reachable without a model — including the branch nobody has a file
for.

⚠ **This is a port, not a redesign.** The table below is `gate.rb`'s, row for row, and the two must
stay in step: if a headless service and the extension disagree about which files they will read,
one of them is wrong and nobody will find out from a passing test.

⚠ **Never version-key the READ.** Hard rule 6 stands: this decides *whether* to read at all. Past
it, the collector coalesces `*ID` ‖ `*Auto` regardless of any stamp — `250708.skp` is 2.1.15 and
keeps every one of its 92 assemblies in `assemblyIDAuto`.

⚠ **The version check runs TWICE and that is not redundancy.** Before the walk, on the stamps alone,
so a generation this reader has never seen bounces off the front door rather than meeting a
collector written against a schema it does not have. After the walk, with the census as evidence,
because "no version stamp" only means "not a designPH model" if the walk *also* found nothing — and
the corpus has models whose envelope data is fine with a stamp missing or doubled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: The only designPH generation this reader understands. 3.0 changed the storage schema, and the
#: working assumption is that a 2.x reader will be taught to translate it later.
SUPPORTED_MAJOR = 2

NOT_DESIGNPH = (
    "This model carries no designPH data at all: no version stamp, no tagged faces or edges, "
    "no designPH windows and no designPH tables.\n\n"
    "DesignPH-PLUS reads models prepared with the designPH SketchUp plugin. Nothing was read "
    "and nothing was written."
)

_LEADING_INTEGER = re.compile(r"\A(\d+)")


@dataclass(frozen=True)
class Decision:
    """`allow` false is a refusal and `reason` says why, in the user's words.

    `note` is a fact worth carrying into the report on a run that proceeds. The two are
    independent, and proceed-with-note is the common case on real models.
    """

    allow: bool
    reason: str | None = None
    note: str | None = None

    @property
    def refused(self) -> bool:
        return not self.allow


ALLOWED = Decision(True)


def major(stamp: object) -> int | None:
    """The leading integer, or `None` when there is not one.

    `"2.4.0 BETA PRO"` → 2, which is the intended answer: a beta of a 2.x release reads like a 2.x
    release. `"3.0.1"` → 3. `"1.0.30"` → 1. `"unknown"` → None.
    """
    found = _LEADING_INTEGER.match(str(stamp).strip())
    return int(found.group(1)) if found else None


def unsupported_text(stamps: list[str]) -> str:
    """Name the stamp. A refusal that does not say what it saw sends the user to us to find out."""
    described = []
    for stamp in stamps:
        found = major(stamp)
        if found is None:
            why = "not a version this reader recognises"
        elif found > SUPPORTED_MAJOR:
            why = "newer than this reader"
        else:
            why = "older than this reader supports"
        described.append(f"  {stamp!r} — {why}")
    return (
        "This model reports a designPH version DesignPH-PLUS cannot read:\n\n"
        + "\n".join(described)
        + f"\n\nThis reader understands designPH {SUPPORTED_MAJOR}.x. Nothing was read and "
        "nothing was written."
    )


def version(raw_stamps: list[Any] | None, evidence: list[str] | None = None) -> Decision:
    """`gate.rb`'s decision table, as one function.

    `evidence` is the walk's human-readable designPH findings, or **None when the walk has not run
    yet** — the pre-walk call. That is the only difference between the two calls, and it affects
    only the no-stamp row: pre-walk, "no stamp" is undecidable and defers.

        all stamps 2.x, one distinct  -> proceed
        any stamp not 2.x             -> REFUSE, naming the stamp
        mixed 2.x stamps              -> proceed + note
        no stamp, evidence present    -> proceed + note
        no stamp, no evidence         -> REFUSE ("not a designPH model")
        no stamp, evidence unknown    -> proceed (defer to the post-walk call)
    """
    found = [str(stamp).strip() for stamp in (raw_stamps or []) if str(stamp).strip()]

    unsupported = [stamp for stamp in found if major(stamp) != SUPPORTED_MAJOR]
    if unsupported:
        return Decision(False, unsupported_text(unsupported))

    if not found:
        if evidence is None:
            return ALLOWED
        if not evidence:
            return Decision(False, NOT_DESIGNPH)
        return Decision(
            True,
            note="no designPH version stamp on the model; proceeding on " + ", ".join(evidence),
        )

    distinct = list(dict.fromkeys(found))
    if len(distinct) == 1:
        return ALLOWED
    # ⚠ Real: `2523 Wellington.skp` carries two stamps in its binary. The live API returns only the
    # current one, so this row fires on the offline reader's view rather than a session's. No
    # behaviour hangs off which stamp wins — hard rule 6 forbids keying the read on the version at
    # all. The note exists so the fact reaches the report, not so anything downstream branches.
    return Decision(
        True, note=f"the model carries {len(distinct)} designPH version stamps: {', '.join(distinct)}"
    )


def evidence(extraction: dict[str, Any]) -> list[str]:
    """What the walk found that says "designPH". Human-readable, because it goes into a note.

    "proceeding on 194 tagged faces, 99 tagged edges" is a defensible reason to translate a model
    with no stamp; a boolean is not.
    """
    model = extraction.get("model") or {}
    counts = extraction.get("counts") or {}
    found: list[str] = []
    if int(counts.get("faces_tagged") or 0) > 0:
        found.append(f"{counts['faces_tagged']} tagged faces")
    if int(counts.get("edges_tagged") or 0) > 0:
        found.append(f"{counts['edges_tagged']} tagged edges")
    if int(counts.get("windows_found") or 0) > 0:
        found.append(f"{counts['windows_found']} designPH windows")
    tables = list(counts.get("tables_found") or [])
    if tables:
        found.append(f"{len(tables)} designPH table(s)")
    if str(model.get("klima_id") or "").strip():
        found.append("a designPH climate id")
    return found
