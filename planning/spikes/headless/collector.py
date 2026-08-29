# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Spike B — the **headless contract-v2 collector**: `poc/ext/dph_plus_poc/collector.rb`, with no
SketchUp anywhere.

One `.skp` in, one contract-v2 extraction JSON out
(`planning/POC/CONTRACT_extraction-json.md`), read through the SketchUp C SDK from a plain CPython
process. The contract is **frozen at v2** and this file emits it verbatim: same keys, same shapes,
same units, `libraries` hoisted to model level. Anything the SDK exposes that v2 does not carry is
a **proposal** for the contract's §9 process, never a field added here (HEADLESS-B §2.2).

⚠ Third-party SDK re-host; feasibility-only evidence. See `sdk.py`.

    uv run collector.py --model MODEL.skp --out DIR/MODEL.extraction.json

---

## What this file must reproduce, and what it deliberately does not

`collector.rb` is the reference. It stays dumb — coalesce, accumulate transforms, convert to
metres, decode Marshal tables — and every judgement call belongs to the translator. This file
inherits that rule exactly, and the sanctioned exception is the same one: `classified()`.

The five traps `collector.rb` is designed around are all live here. Five more exist only on the C
side, and every one of them produced a plausible wrong answer on a real model first:

  6. ⛔ **`SUEntityGetAttributeDictionary` is a get-or-CREATE**, and it is the only *complete* way
     to test for a dictionary — the read-only enumeration loses up to 41 % of tagged faces
     (`HEADLESS-A_results.md` §3.3). So reading mutates the in-memory model, and hard rule 2
     survives only because nothing can save it. That is enforced **structurally**, not by
     intention: `SDK(read_only=True)` cannot resolve a symbol the binding never declared, and the
     binding declares no writer (`sdk.py:_ReadOnlyLib`).
  7. **`SUFaceGetArea` takes no transform, so it is the LOCAL area.** `collector.rb` calls
     `face.area(transform)` — world. The C analogue is `SUFaceGetAreaWithTransform`; the local one
     put 14 of Adelphi's 82 faces wrong by a constant 2.96×.
  8. **Ruby rounds half away from zero; Python's `round()` rounds half to even.** Every coordinate
     in the contract is rounded to 6 dp, so the two disagree on an exact tie — one vertex of one
     model, in a diff that is otherwise clean, reading like a transform bug. `_round6` matches Ruby.
  9. **The placement walk does not finish, and the entity walk answers a different question.**
     Adelphi is 1441 tagged face *entities* behind **1,023,558 face placements**, and
     `counts.faces_walked` counts the placements. Resolved by reading every attribute **once per
     entity** and expanding only the counts and the geometry over placements — see `_Container`.
 10. **A glue target is any drawing element, not necessarily a face.** `collector.rb` tests
     `host.is_a?(Sketchup::Face)`; the C side must test `SUEntityGetType`.

⚠ **`model.file_name` is the one field this reader is deliberately *better* at than the live one**,
and the identity gate must therefore expect a difference rather than absorb it: `collector.rb`
derives it from `Sketchup::Model#path`, which is where the model was last *saved* — on 2 of 5
corpus copies that is someone else's machine, and Wellington's live capture is stamped
`2523 Weiilington` after a backup's misspelling. A headless reader knows which file it opened.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from ctypes import byref, c_double, c_int32, c_size_t
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import gate
from sdk import (
    SDK,
    SUAttributeDictionaryRef,
    SUComponentDefinitionRef,
    SUComponentInstanceRef,
    SUDrawingElementRef,
    SUEdgeRef,
    SUEntitiesRef,
    SUEntityRef,
    SUFaceRef,
    SUGroupRef,
    SULayerRef,
    SULoopRef,
    SUModelRef,
    SUPoint3D,
    SUTransformation,
    SUVertexRef,
)
from walk import IDENTITY, Walker, apply, compose

# --------------------------------------------------------------------------------------------
# The contract's own constants — mirrors of `collector.rb`'s, in the same order and with the same
# names, so a drift between the two readers is visible by diffing two short blocks.
# --------------------------------------------------------------------------------------------

CONTRACT_VERSION = 2

#: Bumped when this reader's *behaviour* changes, so a capture says which reader made it.
COLLECTOR_VERSION = "0.1.0"
GENERATED_BY = f"dph_plus_headless collector (C SDK) {COLLECTOR_VERSION}"

DICT = "DesignPH_dict"
DC_DICT = "dynamic_attributes"

IN_TO_M = 0.0254
IN2_TO_M2 = 0.00064516

COORD_DECIMALS = 6

#: `face[*ID] or face[*Auto]`, per pair — a coalesce, never a version key (hard rule 6).
#: ⚠ `areaGroupAuto`/`tempZoneAuto` carry no "ID"; `assemblyIDAuto` does. The asymmetry is
#: designPH's, not a typo.
COALESCE: dict[str, tuple[str, str]] = {
    "area_group": ("areaGroupID", "areaGroupAuto"),
    "temp_zone": ("tempZoneID", "tempZoneAuto"),
    "assembly_ref": ("assemblyID", "assemblyIDAuto"),
    "desc_name": ("descName", "descNameAuto"),
}

TFA_KEY = "TFA_rf"

SHIP_TABLES = ("assemblies_calc", "assemblies_ud", "connections_ud", "vent_ud", "ihg_ud")
SHIP_TABLE_PREFIXES = ("layer_table_",)

#: base64 of Marshal's `\x04\x08`. ★ designPH stores its tables as BASE64 TEXT, not raw binary, so
#: the NUL-truncation hazard Spike A's G4 was built around does not exist on this path
#: (`HEADLESS-A_results.md` §5). Values still travel as `bytes` — nothing about designPH's storage
#: is guaranteed, and the length-aware read is right in general.
MARSHAL_PREFIX = b"BAh"

MODEL_VERSION_KEY = "designPH_version"
MODEL_KLIMA_ID = "klima_ID"
MODEL_KLIMA_NAME = "Klima_Standort"

UNITS_NOTE = (
    "geometry in metres; raw designPH table and DC values untouched "
    "(mixed units, see contract §4/§5)"
)

WINDOW_DC_KEYS = (
    "frametypeid", "glazingtypeid", "frametype", "glazingtype",
    "lenx", "leny", "area",
    "framewidth", "framewidthl", "framewidthr", "framewidthtop", "framewidthbot",
    "framedepth", "revealdepth", "d_reveal", "o_reveal",
    "instcill", "insthead", "instleft", "instright",
)

#: ⚠ LIBRARY data, not window data. Shipping these per window cost contract v1 **2.07 MB of a
#: 2.25 MB payload** — 44,915 characters byte-identical on all 46 Adelphi windows (contract §5.1).
WINDOW_LIBRARY_KEYS = {
    "_frametype_options": "frame_types",
    "_glazingtype_options": "glazing_types",
}

WINDOW_SIZE_KEYS = ("lenx", "leny")

#: What makes a component instance a designPH window — a predicate, never a definition name.
WINDOW_MARKER = "frametypeid"

#: SUResult codes an *absent* attribute or dictionary legitimately answers with.
ABSENT = (2, 8, 9)


# --------------------------------------------------------------------------------------------
# Small shared rules
# --------------------------------------------------------------------------------------------


def _round6(value: float) -> float:
    """Round to 6 dp **the way Ruby does** — half away from zero, on the exact binary value.

    Python's built-in `round()` rounds half to *even*, so the two readers disagree on an exact tie
    at the 7th decimal. Ties are rare in real geometry and that is precisely the problem: the
    difference would surface on one vertex of one model and read as a transform bug.
    """
    if not math.isfinite(value):
        return value
    return float(Decimal(value).quantize(Decimal("1E-6"), rounding=ROUND_HALF_UP))


def classified(raw: object) -> bool:
    """A face is classified iff its coalesced area group parses as a **positive integer**.

    `'n'` — designPH's "not assigned" — is the common case: 1359 of Adelphi's 1441 tagged faces.
    The filter is therefore by VALUE, never by presence (hard rule 5). This is the collector's one
    sanctioned judgement call, and it decides only whether a record ships.
    """
    if raw is None or isinstance(raw, bool):
        return False
    try:
        return int(str(raw), 10) > 0
    except (TypeError, ValueError):
        return False


def _blank_to_nil(value: object) -> str | None:
    text = ("" if value is None else str(value)).strip()
    return text or None


# --------------------------------------------------------------------------------------------
# Marshal tables — `Collector::Tables`, ported
# --------------------------------------------------------------------------------------------


def load_ruby_marshal(repo_root: Path) -> Any:
    """Import Phase 1's decoder unchanged. It constructs nothing, so a corpus file cannot run code.

    ⚠ `collector.rb` uses `Marshal.load`, which *does* instantiate whatever the blob names — an
    accepted POC risk, because the POC only ever reads BLDGTYP's own models. A headless service
    reads files it did not author, so the construct-nothing reader is not an optimisation here.
    """
    path = repo_root / "planning" / "spikes" / "phase1" / "ruby_marshal.py"
    spec = importlib.util.spec_from_file_location("ruby_marshal", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ruby_marshal"] = module
    spec.loader.exec_module(module)
    return module


class Tables:
    """Decode designPH's base64'd `Marshal.dump` blobs into `{tokens, rows}`."""

    def __init__(self, marshal_module: Any) -> None:
        self._marshal = marshal_module

    def decode(self, stored: bytes) -> dict[str, Any]:
        """One stored base64 value → `{tokens, rows}`, or `{"error": …}` — reported, never dropped."""
        try:
            raw = self._marshal.loads(base64.b64decode(stored))
        except Exception as error:  # noqa: BLE001 — a bad blob is a finding, not a crash
            return {"error": f"{type(error).__name__}: {error}"}
        return self.normalise(raw)

    def normalise(self, raw: object) -> dict[str, Any]:
        """designPH's tables are self-describing, and **the header's position varies**.

        `vent_ud` and `ihg_ud` put their `["#", :TOKENS, [...]]` row at the END and carry their data
        as a flat array of scalars rather than a list of rows (`DESIGNPH_DATA_MODEL.md` §7).
        Normalising here is what stops the translator having to know that.
        """
        if not isinstance(raw, list):
            return {"error": f"not an Array ({type(raw).__name__})"}

        tokens: list[Any] = []
        rows: list[list[Any]] = []
        scalars: list[Any] = []
        for entry in raw:
            if self._metadata_row(entry):
                if len(entry) > 1 and str(entry[1]) == "TOKENS":
                    header = entry[2] if len(entry) > 2 else []
                    tokens = [self.plain(t) for t in (header if isinstance(header, list) else [header])]
            elif isinstance(entry, list):
                rows.append([self.plain(value) for value in entry])
            else:
                scalars.append(self.plain(entry))
        if scalars:
            rows.append(scalars)  # a flat table: the scalars ARE the single row
        return {"tokens": tokens, "rows": rows}

    @staticmethod
    def _metadata_row(entry: object) -> bool:
        return isinstance(entry, list) and bool(entry) and str(entry[0]) == "#"

    def plain(self, value: object) -> Any:
        """Symbols become strings; everything else stays exactly as designPH stored it.

        Table values are already SI/PHPP units (lambda, Psi, mm) and stay that way — only *SketchUp
        geometry* is converted to metres.
        """
        if isinstance(value, self._marshal.Symbol):
            return str(value)
        if isinstance(value, list):
            return [self.plain(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        # A `RubyObject` or a Hash. Neither appears in any corpus table, and inventing a shape for
        # one would be a silent guess — `to_jsonable` names the class instead.
        return self._marshal.to_jsonable(value)


# --------------------------------------------------------------------------------------------
# The container index — every attribute read happens ONCE PER ENTITY
# --------------------------------------------------------------------------------------------


@dataclass
class _FaceEntity:
    """One face entity, read once. Geometry stays out: it is a property of the *placement*."""

    ref: SUFaceRef
    persistent_id: int
    values: dict[str, Any]
    tfa_rf: Any


@dataclass
class _EdgeEntity:
    ref: SUEdgeRef
    persistent_id: int
    values: dict[str, Any]


@dataclass
class _WindowEntity:
    """A designPH window's whole non-geometric record, read once per instance entity."""

    designph_name: str
    definition_name: str
    instance_name: str | None
    dynamic_attributes: dict[str, Any]
    libraries: dict[str, list[str]]
    host_persistent_id: int | None
    host_has_inner_loops: bool
    lenx: float | None
    leny: float | None


@dataclass
class _Instance:
    ref: SUComponentInstanceRef
    persistent_id: int
    transform: tuple[float, ...]
    #: The definition's container. `None` for a designPH window: the walk emits the record and does
    #: not descend, so window internals are neither walked nor counted (contract §6.1).
    child_ptr: int | None
    window: _WindowEntity | None


@dataclass
class _Group:
    persistent_id: int
    transform: tuple[float, ...]
    child_ptr: int


@dataclass
class _Container:
    """One `SUEntitiesRef` — the model's top level, or one component/group **definition**.

    ★ This is the structure that makes a contract-v2 capture affordable headlessly. The contract's
    `counts` are **placement** counts (Adelphi's `faces_walked` is 1,023,558) while every attribute
    is a property of the **entity**. Reading attributes per placement does not finish; reading them
    once per entity and expanding only the counts and the geometry over placements does, in seconds.
    """

    entities: SUEntitiesRef
    faces: list[_FaceEntity] = field(default_factory=list)
    edges: list[_EdgeEntity] = field(default_factory=list)
    instances: list[_Instance] = field(default_factory=list)
    groups: list[_Group] = field(default_factory=list)
    #: Untagged faces contribute only to an aggregate, so they are counted, never stored — which is
    #: what keeps Lavoie's 126k faces off the heap.
    untagged_by_tag: Counter[str] = field(default_factory=Counter)
    n_faces: int = 0

    @property
    def children(self) -> list[int]:
        """Child container ptrs, **with repetition** — two placements of one definition are two."""
        out = [i.child_ptr for i in self.instances if i.child_ptr is not None]
        out.extend(g.child_ptr for g in self.groups)
        return out

    @property
    def has_designph_data(self) -> bool:
        """Does anything *directly* in this container carry designPH data?"""
        return bool(self.faces) or bool(self.edges) or any(i.window for i in self.instances)


@dataclass
class _WalkState:
    """What the placement walk accumulates. One instance per extraction."""

    faces: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    tagged_unclassified: list[dict[str, Any]] = field(default_factory=list)
    libraries: dict[str, list[str]] = field(
        default_factory=lambda: {name: [] for name in WINDOW_LIBRARY_KEYS.values()}
    )

    def add_library_values(self, values: dict[str, list[str]]) -> None:
        """Distinct raw option-list strings, in first-seen order (contract §5.1).

        Deduplicating is not a judgement call; choosing between a real library and designPH's
        `&Launch designPH to edit=01ud&` placeholder is, and that is the translator's.
        """
        for name, found in values.items():
            bucket = self.libraries[name]
            for value in found:
                if value not in bucket:
                    bucket.append(value)


class HeadlessCollector:
    """Reads one open model into a contract-v2 document."""

    def __init__(self, sdk: SDK, tables: Tables) -> None:
        self.sdk = sdk
        self.walker = Walker(sdk)
        self.tables = tables
        self._layer_names: dict[int, str] = {}
        #: ⚠ Read from the SDK's own headers, never hardcoded. The published `SURefType` order puts
        #: `Face` at 9; the shipped API 13.0 header puts it at **11**, and a literal 9 here rejects
        #: every glued host on every model — 0 of 239, reading exactly like a broken glue query.
        self._face_type = sdk.ref_type("Face")
        #: Anything the reader could not resolve. Hard rule 4: report, never guess.
        self.notices: list[str] = []

    # -- entry point ------------------------------------------------------

    def extract(self, model: SUModelRef, file_name: str) -> dict[str, Any]:
        index, root = self._index(model)
        keep = self._keep(index)
        walked, untagged = self._aggregate(index, root)

        state = _WalkState()
        self._expand(index, keep, root, (), IDENTITY, state)

        tables, found = self._model_tables(model)
        return {
            "contract_version": CONTRACT_VERSION,
            "generated_by": GENERATED_BY,
            "model": self._model_info(model, file_name),
            "counts": {
                "faces_walked": walked,
                "faces_tagged": len(state.faces) + len(state.tagged_unclassified),
                "faces_classified": len(state.faces),
                "edges_tagged": len(state.edges),
                "windows_found": len(state.windows),
                "tables_found": found,
            },
            "faces": state.faces,
            "edges": state.edges,
            "windows": state.windows,
            "libraries": state.libraries,
            "tables": tables,
            "unclassified": {
                "tagged_faces": state.tagged_unclassified,
                "untagged_by_tag": dict(untagged),
            },
        }

    # -- pass 1: the container index ---------------------------------------

    def _index(self, model: SUModelRef) -> tuple[dict[int, _Container], int]:
        """Every container in the model, with every attribute already read.

        Containers come from the model's top-level entities plus each component and group
        **definition**: a definition's contents are stored once however many times it is placed,
        which is what makes this pass the entity basis and ~1000× cheaper than a placement walk.
        """
        top = self._top(model)
        index: dict[int, _Container] = {}
        pending: list[SUEntitiesRef] = [top]
        for count_fn, get_fn in (
            ("SUModelGetNumComponentDefinitions", "SUModelGetComponentDefinitions"),
            ("SUModelGetNumGroupDefinitions", "SUModelGetGroupDefinitions"),
        ):
            for definition in self.sdk.get_list(count_fn, get_fn, SUComponentDefinitionRef, model):
                pending.append(self._definition_entities(definition))

        while pending:
            entities = pending.pop()
            if entities.ptr in index:
                continue
            index[entities.ptr] = self._read_container(entities, pending)
        return index, top.ptr

    def _read_container(
        self, entities: SUEntitiesRef, pending: list[SUEntitiesRef]
    ) -> _Container:
        container = _Container(entities=entities)

        faces = self.sdk.get_list("SUEntitiesGetNumFaces", "SUEntitiesGetFaces", SUFaceRef, entities)
        container.n_faces = len(faces)
        for face in faces:
            dictionary = self.walker.dictionary(face)
            if dictionary is None:
                container.untagged_by_tag[self._tag_name(face)] += 1
                continue
            container.faces.append(
                _FaceEntity(
                    ref=face,
                    persistent_id=self.walker.persistent_id(face),
                    values=self._coalesce(dictionary),
                    tfa_rf=self._raw(dictionary, TFA_KEY),
                )
            )

        # `standalone_only=False`: designPH tags edges that bound faces, and Bluff Reach's thermal
        # bridges sit two levels deep. Standalone-only would report 0 of 99, silently.
        for edge in self.sdk.get_list(
            "SUEntitiesGetNumEdges", "SUEntitiesGetEdges", SUEdgeRef, entities, extra=(False,)
        ):
            dictionary = self.walker.dictionary(edge)
            if dictionary is None:
                continue
            container.edges.append(
                _EdgeEntity(
                    ref=edge,
                    persistent_id=self.walker.persistent_id(edge),
                    values=self._coalesce(dictionary),
                )
            )

        for instance in self.sdk.get_list(
            "SUEntitiesGetNumInstances", "SUEntitiesGetInstances", SUComponentInstanceRef, entities
        ):
            window = self._read_window(instance)
            transform = SUTransformation()
            self.sdk.call("SUComponentInstanceGetTransform", instance, byref(transform))
            child = None
            if window is None:
                sub = self._instance_entities(instance)
                child = sub.ptr
                pending.append(sub)
            container.instances.append(
                _Instance(
                    ref=instance,
                    persistent_id=self.walker.persistent_id(instance),
                    transform=tuple(transform.as_list()),
                    child_ptr=child,
                    window=window,
                )
            )

        for group in self.sdk.get_list(
            "SUEntitiesGetNumGroups", "SUEntitiesGetGroups", SUGroupRef, entities
        ):
            transform = SUTransformation()
            self.sdk.call("SUGroupGetTransform", group, byref(transform))
            sub = self._group_entities(group)
            pending.append(sub)
            container.groups.append(
                _Group(
                    persistent_id=self.walker.persistent_id(group),
                    transform=tuple(transform.as_list()),
                    child_ptr=sub.ptr,
                )
            )

        return container

    # -- pass 2: aggregates over the container graph ------------------------

    def _aggregate(
        self, index: dict[int, _Container], root: int
    ) -> tuple[int, Counter[str]]:
        """`counts.faces_walked` and `unclassified.untagged_by_tag`, on the **placement** basis.

        Both are transform-independent, so each is computed once per container and expanded over
        the container DAG rather than over the million-node placement tree. The multiplicity lives
        in `_Container.children`, which repeats a definition once per placement of it.
        """
        walked: dict[int, int] = {}
        untagged: dict[int, Counter[str]] = {}

        for ptr in self._post_order(index):
            container = index[ptr]
            total = container.n_faces
            tags = Counter(container.untagged_by_tag)
            for child in container.children:
                total += walked.get(child, 0)
                tags.update(untagged.get(child, ()))
            walked[ptr] = total
            untagged[ptr] = tags

        return walked.get(root, 0), untagged.get(root, Counter())

    def _post_order(self, index: dict[int, _Container]) -> list[int]:
        """Container ptrs, children before parents, tolerating a malformed cycle rather than looping.

        SketchUp's definition graph is acyclic — a definition cannot contain itself — but a reader
        that recurses forever on a corrupt file is a worse failure than one that reports a cycle.
        """
        order: list[int] = []
        state: dict[int, int] = {}  # 0 = on the stack, 1 = emitted
        for start in index:
            if start in state:
                continue
            stack: list[tuple[int, bool]] = [(start, False)]
            while stack:
                ptr, expanded = stack.pop()
                if expanded:
                    state[ptr] = 1
                    order.append(ptr)
                    continue
                if ptr in state:
                    if state[ptr] == 0:
                        self.notices.append(f"container graph revisits {ptr:#x} — cycle tolerated")
                    continue
                state[ptr] = 0
                stack.append((ptr, True))
                for child in dict.fromkeys(index[ptr].children):
                    if child in index and child not in state:
                        stack.append((child, False))
        return order

    def _keep(self, index: dict[int, _Container]) -> set[int]:
        """Containers whose subtree holds designPH data — the pruning set for the placement walk.

        A container is kept if *anything* anywhere beneath it is tagged, so no tagged entity can be
        skipped: this prunes the traversal, never the answer. Without it the placement walk visits
        millions of nodes to reach the ~0.3 % that carry data.
        """
        keep = {ptr for ptr, container in index.items() if container.has_designph_data}
        changed = True
        while changed:
            changed = False
            for ptr, container in index.items():
                if ptr not in keep and any(child in keep for child in container.children):
                    keep.add(ptr)
                    changed = True
        return keep

    # -- pass 3: the pruned placement walk ----------------------------------

    def _expand(
        self,
        index: dict[int, _Container],
        keep: set[int],
        ptr: int,
        path: tuple[int, ...],
        world: tuple[float, ...],
        state: _WalkState,
    ) -> None:
        container = index[ptr]

        for face in container.faces:
            if classified(face.values["area_group"]):
                state.faces.append(self._face_record(face, world, path))
            else:
                # Compact, ~100 bytes: enough for the report to NAME every tagged face the
                # translation omits, which is what hard rule 4 asks for.
                state.tagged_unclassified.append(
                    {
                        "id": self._id("face", path, face.persistent_id),
                        "area_group": face.values["area_group"],
                        "tag": self._tag_name(face.ref),
                    }
                )

        for edge in container.edges:
            state.edges.append(self._edge_record(edge, world, path))

        for instance in container.instances:
            child_world = compose(world, instance.transform)
            if instance.window is not None:
                state.windows.append(self._window_record(instance, child_world, path))
                state.add_library_values(instance.window.libraries)
                continue
            if instance.child_ptr in keep:
                self._expand(
                    index, keep, instance.child_ptr, path + (instance.persistent_id,),
                    child_world, state,
                )

        for group in container.groups:
            if group.child_ptr not in keep:
                continue
            self._expand(
                index, keep, group.child_ptr, path + (group.persistent_id,),
                compose(world, group.transform), state,
            )

    # -- records ------------------------------------------------------------

    def _face_record(
        self, face: _FaceEntity, world: tuple[float, ...], path: tuple[int, ...]
    ) -> dict[str, Any]:
        outer = SULoopRef()
        self.sdk.call("SUFaceGetOuterLoop", face.ref, byref(outer))
        inner = self.sdk.get_list(
            "SUFaceGetNumInnerLoops", "SUFaceGetInnerLoops", SULoopRef, face.ref
        )
        return {
            "id": self._id("face", path, face.persistent_id),
            "entity_id": self._entity_id(face.ref),
            "area_group": face.values["area_group"],
            "temp_zone": face.values["temp_zone"],
            "assembly_ref": face.values["assembly_ref"],
            "desc_name": face.values["desc_name"],
            "tfa_rf": face.tfa_rf,
            # SketchUp's winding order, verbatim: orientation is derived from it downstream. No
            # normal is shipped — transforming one is wrong under non-uniform scale or mirroring,
            # and a mirrored transform flips the winding with the geometry (contract §2.2).
            "outer_loop": self._loop(outer, world),
            "inner_loops": [self._loop(loop, world) for loop in inner],
            "area_m2": _round6(self._world_area(face.ref, world) * IN2_TO_M2),
            "both_generations": face.values["both_generations"],
        }

    def _edge_record(
        self, edge: _EdgeEntity, world: tuple[float, ...], path: tuple[int, ...]
    ) -> dict[str, Any]:
        start = self._point(self._vertex(edge.ref, "SUEdgeGetStartVertex"), world)
        end = self._point(self._vertex(edge.ref, "SUEdgeGetEndVertex"), world)
        return {
            "id": self._id("edge", path, edge.persistent_id),
            "entity_id": self._entity_id(edge.ref),
            "area_group": edge.values["area_group"],
            # ⚠ Named apart from a face's `assembly_ref` on purpose: it resolves against
            # `connections_ud`, NOT the assembly tables. Both namespaces use `NNud` ids, so joining
            # it to assemblies by accident returns an unrelated row rather than an error.
            "connection_ref": edge.values["assembly_ref"],
            "desc_name": edge.values["desc_name"],
            # From the TRANSFORMED endpoints, exactly as `collector.rb` does it.
            "length_m": _round6(math.dist(start, end)),
            "start": start,
            "end": end,
            "both_generations": edge.values["both_generations"],
        }

    def _window_record(
        self, instance: _Instance, world: tuple[float, ...], path: tuple[int, ...]
    ) -> dict[str, Any]:
        window = instance.window
        assert window is not None
        host_id = (
            self._id("face", path, window.host_persistent_id)
            if window.host_persistent_id is not None
            else None
        )
        return {
            "id": self._id("window", path, instance.persistent_id),
            "entity_id": self._entity_id(instance.ref),
            "designph_name": window.designph_name,
            "definition_name": window.definition_name,
            "instance_name": window.instance_name,
            "dynamic_attributes": window.dynamic_attributes,
            # The ACCUMULATED world transform, column-major, translation at 12-14, in INCHES.
            # ⚠ NOT the instance's own transform — that is parent-relative while every other
            # geometry field is world, and mixing them put Adelphi's 46 windows 1.2-3.3 m off their
            # hosts (contract §8.2). Composed once, on the way down.
            "transformation": list(world),
            "panel_outer_loop": self._panel_loop(world, window),
            "host_face_id": host_id,
            # No geometric fallback here: "unresolved" is legal contract data and ships with the
            # transform and panel loop, so a downstream recovery stays possible without the capture
            # device guessing.
            "host_resolution": "glued_to" if host_id else "unresolved",
            "host_has_inner_loops": window.host_has_inner_loops,
        }

    def _panel_loop(
        self, world: tuple[float, ...], window: _WindowEntity
    ) -> list[list[float]] | None:
        """The **rough opening**: definition-local `(0,0)→(lenx,0)→(lenx,leny)→(0,leny)`, in world.

        ⚠ Two refuted alternatives, because both look right. The definition's largest face is the
        **glazing** — 41 % small, real geometry in the right place and the right shape, with nothing
        downstream to flag it — and `dynamic_attributes["area"]` is a stale DC formula output that
        equals `lenx × leny × 0.00064516` on only 20 of 46 real windows. Contract §8.1.

        The corner convention is measured, not assumed: `+x/+y` from the origin puts all 46 Adelphi
        windows inside their host polygons, against 23, 15 and 12 for the alternatives.

        `None` means a genuine read failure — no usable `lenx`/`leny`.
        """
        if window.lenx is None or window.leny is None:
            return None
        corners = ((0.0, 0.0), (window.lenx, 0.0), (window.lenx, window.leny), (0.0, window.leny))
        return [self._point((x, y, 0.0), world) for x, y in corners]

    # -- window reading -----------------------------------------------------

    def _read_window(self, instance: SUComponentInstanceRef) -> _WindowEntity | None:
        """The window's whole non-geometric record, or `None` if this instance is not one."""
        instance_dc = self.walker.dictionary(instance, DC_DICT)
        if instance_dc is None or self._raw(instance_dc, WINDOW_MARKER) is None:
            return None

        definition = SUComponentDefinitionRef()
        self.sdk.call("SUComponentInstanceGetDefinition", instance, byref(definition))
        definition_dc = self.walker.dictionary(definition, DC_DICT)
        definition_name = self._string_of("SUComponentDefinitionGetName", definition)
        instance_name = _blank_to_nil(self._string_of("SUComponentInstanceGetName", instance))

        attributes: dict[str, Any] = {}
        for key in WINDOW_DC_KEYS:
            # Per-window values live on the INSTANCE; the definition holds the shared template and
            # fills in where the instance is silent. Reading only one gives wrong answers
            # (`DESIGNPH_DATA_MODEL.md` §8.2).
            value = self._raw(instance_dc, key)
            if value is None and definition_dc is not None:
                value = self._raw(definition_dc, key)
            if value is not None:
                attributes[key] = value

        host_pid, host_inner = self._host(instance)
        return _WindowEntity(
            designph_name=self._window_name(instance, definition_name, instance_name),
            definition_name=definition_name,
            instance_name=instance_name,
            dynamic_attributes=attributes,
            libraries=self._libraries_of(instance_dc, definition_dc),
            host_persistent_id=host_pid,
            host_has_inner_loops=host_inner,
            lenx=self._inches(attributes.get("lenx")),
            leny=self._inches(attributes.get("leny")),
        )

    def _window_name(
        self, instance: SUComponentInstanceRef, definition_name: str, instance_name: str | None
    ) -> str:
        """Never null: every report line downstream names its window with this."""
        dictionary = self.walker.dictionary(instance)
        generated = None
        if dictionary is not None:
            generated = self._raw(dictionary, "descName")
            if generated is None:
                generated = self._raw(dictionary, "descNameAuto")
        return (
            instance_name
            or _blank_to_nil(generated)
            or f"{definition_name}#{self.walker.persistent_id(instance)}"
        )

    def _libraries_of(
        self,
        instance_dc: SUAttributeDictionaryRef,
        definition_dc: SUAttributeDictionaryRef | None,
    ) -> dict[str, list[str]]:
        """designPH's frame and glazing option lists, read from the instance AND the definition.

        ⚠ A definition can hold the real list while its instances hold designPH's
        `&Launch designPH to edit=01ud&` placeholder, and vice versa — so both are read.
        """
        out: dict[str, list[str]] = {name: [] for name in WINDOW_LIBRARY_KEYS.values()}
        for key, name in WINDOW_LIBRARY_KEYS.items():
            for source in (instance_dc, definition_dc):
                if source is None:
                    continue
                value = self._raw(source, key)
                if isinstance(value, str) and value.strip():
                    out[name].append(value)
        return out

    def _host(self, instance: SUComponentInstanceRef) -> tuple[int | None, bool]:
        """The glued host face, via `SUComponentInstanceGetAttachedToDrawingElements`.

        ★ `glued_to` is the **only** host test. `cuts_opening?` is a capability of the *definition*
        (true on all 46 Adelphi windows) and `loops.size > 1` is true on 1 of 81 real hosts, because
        a glued opening reduces `face.area` without creating a loop. The C SDK resolved 239/239 with
        this call (`HEADLESS-A_results.md` G1).

        ⚠ A glue target is any drawing element, so the type is checked — `collector.rb`'s
        `host.is_a?(Sketchup::Face)`, one layer down. ⚠⚠ And the type *value* comes from the
        shipped header (`SDK.ref_type`), not from the documented enum order, which is two off.
        """
        attached = self.sdk.get_list(
            "SUComponentInstanceGetNumAttachedToDrawingElements",
            "SUComponentInstanceGetAttachedToDrawingElements",
            SUDrawingElementRef,
            instance,
        )
        for element in attached:
            if self.sdk.lib.SUEntityGetType(SUEntityRef(element.ptr)) != self._face_type:
                continue
            face = SUFaceRef(element.ptr)
            inner = c_size_t()
            self.sdk.call("SUFaceGetNumInnerLoops", face, byref(inner), tolerate=ABSENT)
            # Reports whether the hole was MODELLED — which is why `face.area` comes back net while
            # the loop polygon is gross. ⚠ It is not a host test.
            return self.walker.persistent_id(face), inner.value > 0
        return None, False

    def _inches(self, value: object) -> float | None:
        """The one designPH value this reader coerces, and only because the rectangle needs a number.

        The raw String still ships in `dynamic_attributes`, so the translator's type check runs on
        the authoritative copy and "the collector stays dumb" survives intact.
        """
        if value is None:
            return None
        try:
            number = float(str(value))
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    # -- model-level --------------------------------------------------------

    def _model_info(self, model: SUModelRef, file_name: str) -> dict[str, Any]:
        dictionary = self._model_dictionary(model)
        version = self._raw(dictionary, MODEL_VERSION_KEY) if dictionary is not None else None
        return {
            # ⚠ The opened file's stem, NOT `SUModelGetName` and NOT a path. `collector.rb` has only
            # `Sketchup::Model#path` — the last-SAVED location, which on 2 of 5 corpus copies is
            # another machine — and a headless reader knows which file it opened. Also: nothing
            # here may embed a filesystem path (HEADLESS overview §4).
            "file_name": file_name,
            # ⚠ ONE stamp, not all of them. A `.skp` can hold two in its binary (Wellington does),
            # but that is historical state visible only to the offline reader; shipped as a list
            # because the contract's shape allows for more.
            "designph_versions": [version] if version is not None else [],
            "klima_id": self._raw(dictionary, MODEL_KLIMA_ID) if dictionary is not None else None,
            "klima_standort": (
                self._raw(dictionary, MODEL_KLIMA_NAME) if dictionary is not None else None
            ),
            "units_note": UNITS_NOTE,
        }

    def _model_tables(self, model: SUModelRef) -> tuple[dict[str, Any], list[str]]:
        """Returns (shipped tables, **every** blob key found).

        A table absent from the model is **omitted** — never `null`, never `{}`. The translator
        treats absence as tier-unresolvable and reports; Adelphi, the primary fixture, carries no
        `assemblies_calc`, no `connections_ud` and no `layer_table_*`, so absence is the normal case.
        """
        dictionary = self._model_dictionary(model)
        if dictionary is None:
            return {}, []
        found: list[str] = []
        shipped: dict[str, Any] = {}
        for key in self.walker.dict_keys(dictionary):
            got = self.walker.typed_value(dictionary, key)
            if not got or got[0] != "String" or not isinstance(got[1], bytes):
                continue
            if not got[1].startswith(MARSHAL_PREFIX):
                continue  # designPH_version, klima_ID — plain scalars, not tables
            found.append(key)
            if key in SHIP_TABLES or key.startswith(SHIP_TABLE_PREFIXES):
                shipped[key] = self.tables.decode(got[1])
        return shipped, sorted(found)

    def _model_dictionary(self, model: SUModelRef) -> SUAttributeDictionaryRef | None:
        """The model's own `DesignPH_dict`, found by **enumerating** the model's dictionaries.

        ⚠ Deliberately not `SUEntityGetAttributeDictionary`: that call is a get-or-CREATE, and
        creating an empty `DesignPH_dict` on a model that has none would put this reader inside the
        namespace hard rule 2 forbids. The model-level enumeration has no equivalent under-reporting
        trap — unlike the entity-level one, which loses up to 41 % of tagged faces.
        """
        for candidate in self.sdk.get_list(
            "SUModelGetNumAttributeDictionaries", "SUModelGetAttributeDictionaries",
            SUAttributeDictionaryRef, model,
        ):
            if self._string_of("SUAttributeDictionaryGetName", candidate) == DICT:
                return candidate
        return None

    # -- shared reading -----------------------------------------------------

    def _coalesce(self, dictionary: SUAttributeDictionaryRef) -> dict[str, Any]:
        """`entity[*ID] or entity[*Auto]`, per pair — deliberately version-independent (hard rule 6).

        Any rule keyed on the designPH version stamp loses envelope data silently: `250708.skp` is
        2.1.15 and keeps every one of its 92 assemblies in `assemblyIDAuto`.

        A pair with both values non-nil is impossible according to the corpus for area group, temp
        zone and assembly. It is *normal* for `descName`/`descNameAuto`, which are an override pair
        — 70 Bluff Reach faces carry both, with real room names — so the pair is named in
        `both_generations` and the reporting is left downstream rather than called an anomaly here.
        """
        both: list[str] = []
        values: dict[str, Any] = {}
        for name, (primary, fallback) in COALESCE.items():
            first = self._raw(dictionary, primary)
            second = self._raw(dictionary, fallback)
            if first is not None and second is not None:
                # The designPH concept's name, not the contract field's: `assembly_ref` is the
                # field, `assembly` is the pair the two keys share.
                both.append(name[: -len("_ref")] if name.endswith("_ref") else name)
            values[name] = second if first is None else first
        values["both_generations"] = both
        return values

    def _raw(self, dictionary: SUAttributeDictionaryRef, key: str) -> Any:
        """One typed attribute value, decoded to a JSON-native type but **not normalised**.

        Hard rule 5: the type tag travels with the value in the C API, and `areaGroupID` is a String
        `'n'` on 1359 of Adelphi's 1441 tagged faces. Nothing here coerces `'n'` into anything.
        """
        got = self.walker.typed_value(dictionary, key)
        if got is None:
            return None
        tag, value = got
        if tag == "String" and isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value

    def _loop(self, loop: SULoopRef, world: tuple[float, ...]) -> list[list[float]]:
        return [[_round6(v) for v in point] for point in self.walker.loop_points(loop, world)]

    def _point(
        self, position: tuple[float, float, float], world: tuple[float, ...]
    ) -> list[float]:
        return [_round6(v * IN_TO_M) for v in apply(world, position)]

    def _vertex(self, edge: SUEdgeRef, fn: str) -> tuple[float, float, float]:
        vertex = SUVertexRef()
        self.sdk.call(fn, edge, byref(vertex))
        point = SUPoint3D()
        self.sdk.call("SUVertexGetPosition", vertex, byref(point))
        return point.as_tuple()

    def _world_area(self, face: SUFaceRef, world: tuple[float, ...]) -> float:
        """⚠ `SUFaceGetAreaWithTransform`, never `SUFaceGetArea`.

        The latter takes no transform and is therefore the **local** area, while `collector.rb`
        calls `face.area(transform)` — world. On four corpus models the two agree; on Adelphi's
        scaled container the local one put 14 of 82 faces wrong by a constant 2.96×. Using the
        library's own transform-aware call rather than rescaling locally is the same rule as
        `clean_string` and `is_horizontal`, one layer down.
        """
        transform = SUTransformation()
        transform.values[:] = list(world)
        area = c_double()
        self.sdk.call("SUFaceGetAreaWithTransform", face, byref(transform), byref(area))
        return area.value

    def _tag_name(self, ref: Any) -> str:
        """The SketchUp tag (layer) name, cached per layer — `collector.rb`'s `entity.layer.name`."""
        layer = SULayerRef()
        code = self.sdk.call(
            "SUDrawingElementGetLayer", SUDrawingElementRef(ref.ptr), byref(layer), tolerate=ABSENT
        )
        if code != 0 or not layer.ptr:
            return "Untagged"
        cached = self._layer_names.get(layer.ptr)
        if cached is None:
            cached = self._string_of("SULayerGetName", layer) or "Untagged"
            self._layer_names[layer.ptr] = cached
        return cached

    def _entity_id(self, ref: Any) -> int:
        """`entityID` — session-scoped, a debugging aid ONLY. The contract joins on `id`."""
        value = c_int32()
        self.sdk.call("SUEntityGetID", SUEntityRef(ref.ptr), byref(value), tolerate=ABSENT)
        return value.value

    @staticmethod
    def _id(kind: str, path: tuple[int, ...], persistent_id: int) -> str:
        """The contract's path-qualified id: `kind_<ancestor pids…>_<own pid>` (contract §2.1).

        The path is the PLACEMENT identity and the leaf is the ENTITY identity, which is what makes
        an id unique under component instancing and stable across sessions for an unedited model.
        """
        return "_".join([kind, *(str(p) for p in path), str(persistent_id)])

    def _string_of(self, fn: str, ref: Any) -> str:
        return self.sdk.string_out(fn, ref).decode("utf-8", "replace")

    # -- container plumbing -------------------------------------------------

    def _top(self, model: SUModelRef) -> SUEntitiesRef:
        entities = SUEntitiesRef()
        self.sdk.call("SUModelGetEntities", model, byref(entities))
        return entities

    def _definition_entities(self, definition: SUComponentDefinitionRef) -> SUEntitiesRef:
        entities = SUEntitiesRef()
        self.sdk.call("SUComponentDefinitionGetEntities", definition, byref(entities))
        return entities

    def _instance_entities(self, instance: SUComponentInstanceRef) -> SUEntitiesRef:
        definition = SUComponentDefinitionRef()
        self.sdk.call("SUComponentInstanceGetDefinition", instance, byref(definition))
        return self._definition_entities(definition)

    def _group_entities(self, group: SUGroupRef) -> SUEntitiesRef:
        entities = SUEntitiesRef()
        self.sdk.call("SUGroupGetEntities", group, byref(entities))
        return entities


# --------------------------------------------------------------------------------------------
# Driving one file
# --------------------------------------------------------------------------------------------


def capture(
    path: Path, sdk: SDK, tables: Tables
) -> tuple[dict[str, Any], list[str], float]:
    """Open one `.skp`, extract it, close it. Returns (document, notices, seconds).

    ⛔ The model is **never saved**. That is not a promise this function keeps — `sdk` is
    `read_only`, so it cannot resolve `SUModelSaveToFile` at all (`sdk.py:_ReadOnlyLib`).

    ⚠ This reads unconditionally, by design: the *gate* decides whether a capture may be used, and
    it is applied by `main` (and by anything else driving this). Keeping the read gate-free is what
    lets the gate's own evidence — the census — exist to decide the no-stamp row.
    """
    collector = HeadlessCollector(sdk, tables)
    started = time.perf_counter()
    model = sdk.open_model(path)
    try:
        document = collector.extract(model, path.stem)
    finally:
        sdk.close_model(model)
    return document, collector.notices, time.perf_counter() - started


def gated_capture(
    path: Path, sdk: SDK, tables: Tables
) -> tuple[dict[str, Any] | None, gate.Decision, list[str], float]:
    """A capture the version gate has passed, or `None` and the refusal that stopped it.

    ⚠ **The gate runs twice, and that is not redundancy.** Before the walk it sees the stamps alone,
    so a generation this reader has never met is refused in milliseconds rather than meeting a
    collector written against a schema it does not have. After the walk it sees the census, because
    "no version stamp" only means "not a designPH model" if the walk *also* found nothing — a row
    that is simply undecidable before the walk. `gate.py` is `gate.rb` ported; the extension and a
    headless service must not silently disagree about which files they will read.

    ⛔ On a refusal **nothing is emitted**. A partial capture that does not say it is partial is the
    failure this exists to prevent (H9), and the precedent is this repo's own: the offline parser
    returned a clean zero on the 1.0.30 file and it stood for ten days.
    """
    stamps = model_version_stamps(sdk, tables, path)
    pre = gate.version(stamps, None)
    if pre.refused:
        return None, pre, [], 0.0
    document, notices, seconds = capture(path, sdk, tables)
    post = gate.version(document["model"]["designph_versions"], gate.evidence(document))
    if post.refused:
        return None, post, notices, seconds
    return document, post, notices, seconds


def model_version_stamps(sdk: SDK, tables: Tables, path: Path) -> list[str]:
    """The model's own designPH stamps, read without walking anything.

    Model-level only: designPH writes one per model and reading it costs a file open, which is what
    makes the pre-walk refusal worth having on a 146 MB file.
    """
    collector = HeadlessCollector(sdk, tables)
    model = sdk.open_model(path)
    try:
        dictionary = collector._model_dictionary(model)
        if dictionary is None:
            return []
        stamp = collector._raw(dictionary, MODEL_VERSION_KEY)
        return [] if stamp is None else [str(stamp)]
    finally:
        sdk.close_model(model)


def write_capture(document: dict[str, Any], out: Path) -> int:
    """Write one capture and return its byte size.

    ⚠ Every Spike-B script takes an explicit `--out`: `byte_identity.py` once inherited another
    tool's default baseline directory and wrote client HBJSON into the committed repo
    (CONSTRAINTS §9).
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, separators=(",", ":"))
    out.write_text(payload, encoding="utf-8")
    return len(payload.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", type=Path, required=True, help="a COPY of a .skp, never an original")
    parser.add_argument("--out", type=Path, required=True, help="where to write the extraction JSON")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--no-gate",
        action="store_true",
        help="read without the version gate — for the gates that grade the READ, never for a service",
    )
    args = parser.parse_args()

    sdk = SDK(read_only=True)
    tables = Tables(load_ruby_marshal(args.repo_root))
    try:
        if args.no_gate:
            captured, notices, seconds = capture(args.model, sdk, tables)
            document, decision = captured, gate.ALLOWED
        else:
            document, decision, notices, seconds = gated_capture(args.model, sdk, tables)
    finally:
        sdk.terminate()

    if document is None:
        # ⛔ Refused: nothing written, and the reason names what it saw.
        print(f"{args.model.name}: REFUSED — nothing was read and nothing was written\n")
        print(decision.reason)
        return 2
    if decision.note:
        print(f"  NOTE {decision.note}")

    size = write_capture(document, args.out)
    counts = document["counts"]
    for notice in notices:
        print(f"  NOTE {notice}")
    print(
        f"{args.model.name}: {counts['faces_classified']} classified / {counts['faces_tagged']} "
        f"tagged / {counts['faces_walked']} walked · {counts['edges_tagged']} edges · "
        f"{counts['windows_found']} windows · {len(document['tables'])} tables · "
        f"{size} bytes · {seconds:.2f} s → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
