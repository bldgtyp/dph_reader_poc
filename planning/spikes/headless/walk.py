# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The recursive model walk every behavioural gate shares.

Mirrors what `poc/ext/dph_plus_poc/collector.rb` does inside SketchUp, so the two can be compared
directly rather than approximately:

- **ids are path-qualified `persistent_id`s** — `kind_<ancestors...>_<own>` — so the whole path is
  the PLACEMENT identity and the leaf is the ENTITY identity. Reproducing the collector's exact id
  format is what makes a headless capture comparable to a live one at all.
- **groups and component instances are both containers, and they are separate API calls.**
  `SUEntitiesGetInstances` alone misses group-nested geometry; designPH's thermal bridges sit two
  levels deep on Bluff Reach, so a walk that gets this wrong reports **0 of 99 edges, silently**.
- **transforms compose to world on the way down.** `SUComponentInstanceGetTransform` and
  `SUGroupGetTransform` are both parent-relative — the trap that put Adelphi's 46 windows 1.2-3.3 m
  off their hosts in the POC (`CONSTRAINTS.md` §4).
- **counts are reported on both bases**, never one. A placements count and an entity count differ by
  675 on Linde and Adelphi masks the difference entirely.
"""

from __future__ import annotations

from ctypes import byref, c_int64, c_size_t
from dataclasses import dataclass, field
from typing import Callable, Iterator

from sdk import (
    SDK,
    SU_ERROR_NO_DATA,
    SUAttributeDictionaryRef,
    SUComponentDefinitionRef,
    SUComponentInstanceRef,
    SUEdgeRef,
    SUEntitiesRef,
    SUEntityRef,
    SUFaceRef,
    SUGroupRef,
    SULoopRef,
    SUPoint3D,
    SUTransformation,
    SUVertexRef,
    TYPED_VALUE_TYPES,
    SUTypedValueRef,
)

INCHES_TO_M = 0.0254
IDENTITY = tuple(
    [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
)


def compose(parent: tuple[float, ...], child: tuple[float, ...]) -> tuple[float, ...]:
    """parent ∘ child for SketchUp's COLUMN-major 4x4 layout.

    Column-major means index `c*4 + r`. Getting this transposed produces transforms that are wrong
    only when there is rotation — so it would pass on an axis-aligned test model and fail on every
    real building. Composed here rather than via `SUTransformationMultiply` so the ordering is
    visible and testable in Python.
    """
    out = [0.0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = sum(parent[k * 4 + r] * child[c * 4 + k] for k in range(4))
    return tuple(out)


def apply(t: tuple[float, ...], p: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = p
    return tuple(t[0 + r] * x + t[4 + r] * y + t[8 + r] * z + t[12 + r] for r in range(3))  # type: ignore[return-value]


@dataclass
class Node:
    """One entity, at one placement, with the world transform that got it there."""

    kind: str  # "face" | "edge" | "window" (a ComponentInstance)
    ref: object
    entity: SUEntityRef
    path: tuple[int, ...]  # ancestor persistent_ids
    persistent_id: int
    world: tuple[float, ...]
    depth: int

    @property
    def id(self) -> str:
        return "_".join([self.kind, *(str(p) for p in self.path), str(self.persistent_id)])

    @property
    def leaf(self) -> str:
        """The ENTITY identity — what to deduplicate on when counting entities, not placements."""
        return str(self.persistent_id)


def _entity(ref) -> SUEntityRef:
    """Reinterpret an SU*Ref as SUEntityRef. All handles are one pointer; this is the C cast."""
    return SUEntityRef(ref.ptr)


class Walker:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk

    # -- identity ---------------------------------------------------------

    def persistent_id(self, ref) -> int:
        pid = c_int64()
        self.sdk.call("SUEntityGetPersistentID", _entity(ref), byref(pid))
        return pid.value

    # -- attributes -------------------------------------------------------

    def dictionary(self, ref, name: str = "DesignPH_dict") -> SUAttributeDictionaryRef | None:
        """The named attribute dictionary if it has any keys, else None.

        ⚠⚠ **Two SDK traps meet here, and each one alone gives a wrong answer silently.**

        **Trap 1 — `SUEntityGetAttributeDictionary` is a get-or-CREATE.** Its own header says: "If a
        dictionary with the given name does not exist, one is added to the entity." A function named
        `Get` writes. Using its mere success as the tagged-test reports EVERY entity as tagged: 8037
        faces instead of 1441 on Adelphi, 16718 edges instead of 0, 1343 instances instead of 46.

        **Trap 2 — the enumerating alternative silently under-reports.** The obvious read-only fix is
        `SUEntityGetNumAttributeDictionaries` + `SUEntityGetAttributeDictionaries`. Measured on the
        corpus, those two disagree with each other: for many entities `GetNum` returns **1** while
        `GetAttributeDictionaries` returns **`SU_ERROR_NONE` with count 0** and an unset handle —
        and the dictionary is really there, with keys. Cost of trusting it: **118 of 446** tagged
        faces lost on Wellington, **731 of 1791** on Linde, **716 of 1781** on 250708. Adelphi and
        Bluff Reach are unaffected, so they mask it completely — as usual.

        **So the only complete predicate is: ask by name, then require at least one key.** A genuinely
        absent dictionary comes back freshly created and empty, so `num_keys > 0` is what separates
        real data from the SDK's own side effect.

        ⛔ **This means a C-SDK reader MUTATES THE IN-MEMORY MODEL as a side effect of reading it.**
        Hard rule 2 (never write to `DesignPH_dict`) survives only because nothing here ever calls
        `SUModelSaveToFile`. Any headless service built on this must treat "never save an opened
        model" as a load-bearing invariant, not a convention.
        """
        d = SUAttributeDictionaryRef()
        code = self.sdk.call(
            "SUEntityGetAttributeDictionary", _entity(ref), name.encode("utf-8"), byref(d),
            tolerate=(SU_ERROR_NO_DATA, 2, 8),
        )
        if code != 0 or not d.ptr:
            return None
        n = c_size_t()
        self.sdk.call("SUAttributeDictionaryGetNumKeys", d, byref(n), tolerate=(2, 8, 9))
        return d if n.value else None

    def dict_keys(self, d: SUAttributeDictionaryRef) -> list[str]:
        from sdk import SUStringRef

        n = c_size_t()
        self.sdk.call("SUAttributeDictionaryGetNumKeys", d, byref(n))
        if not n.value:
            return []
        arr = (SUStringRef * n.value)()
        for i in range(n.value):
            self.sdk.call("SUStringCreate", byref(arr[i]))
        got = c_size_t()
        self.sdk.call("SUAttributeDictionaryGetKeys", d, n.value, arr, byref(got))
        keys = [self.sdk.read_string(arr[i]).decode("utf-8", "replace") for i in range(got.value)]
        for i in range(n.value):
            self.sdk.lib.SUStringRelease(byref(arr[i]))
        return keys

    def typed_value(self, d: SUAttributeDictionaryRef, key: str) -> tuple[str, object] | None:
        """(type_tag, value) — the TAG is returned alongside, because hard rule 5 says type-check
        every read and `areaGroupID` is a String `'n'` on most faces."""
        from ctypes import c_bool, c_double, c_int32

        from sdk import SUStringRef

        tv = SUTypedValueRef()
        self.sdk.call("SUTypedValueCreate", byref(tv))
        try:
            code = self.sdk.call(
                "SUAttributeDictionaryGetValue", d, key.encode("utf-8"), byref(tv),
                tolerate=(SU_ERROR_NO_DATA, 2, 8),
            )
            if code != 0:
                return None
            t = c_int32()
            self.sdk.call("SUTypedValueGetType", tv, byref(t))
            tag = TYPED_VALUE_TYPES.get(t.value, f"<{t.value}>")
            if tag == "String":
                s = SUStringRef()
                self.sdk.call("SUStringCreate", byref(s))
                try:
                    self.sdk.call("SUTypedValueGetString", tv, byref(s))
                    return tag, self.sdk.read_string(s)  # RAW BYTES — Marshal blobs come through here
                finally:
                    self.sdk.lib.SUStringRelease(byref(s))
            if tag == "Int32":
                v = c_int32()
                self.sdk.call("SUTypedValueGetInt32", tv, byref(v))
                return tag, v.value
            if tag in ("Double", "Float"):
                v2 = c_double()
                self.sdk.call("SUTypedValueGetDouble", tv, byref(v2))
                return tag, v2.value
            if tag == "Bool":
                b = c_bool()
                self.sdk.call("SUTypedValueGetBool", tv, byref(b))
                return tag, b.value
            return tag, None
        finally:
            self.sdk.lib.SUTypedValueRelease(byref(tv))

    # -- geometry ---------------------------------------------------------

    def loop_points(self, loop: SULoopRef, world: tuple[float, ...]) -> list[tuple[float, float, float]]:
        n = c_size_t()
        self.sdk.call("SULoopGetNumVertices", loop, byref(n))
        if not n.value:
            return []
        arr = (SUVertexRef * n.value)()
        got = c_size_t()
        self.sdk.call("SULoopGetVertices", loop, n.value, arr, byref(got))
        pts = []
        for i in range(got.value):
            p = SUPoint3D()
            self.sdk.call("SUVertexGetPosition", arr[i], byref(p))
            wx, wy, wz = apply(world, p.as_tuple())
            pts.append((wx * INCHES_TO_M, wy * INCHES_TO_M, wz * INCHES_TO_M))
        return pts

    # -- the walk ---------------------------------------------------------

    def walk(self, entities: SUEntitiesRef, path: tuple[int, ...] = (), world: tuple[float, ...] = IDENTITY,
             depth: int = 0, max_depth: int = 64) -> Iterator[Node]:
        """Yield every face, edge and component instance, depth-first, with world transforms composed.

        ⚠ Recurses through BOTH instances and groups. Omitting groups is the silent-zero-edges bug.
        """
        if depth > max_depth:
            return

        for face in self._list("SUEntitiesGetNumFaces", "SUEntitiesGetFaces", SUFaceRef, entities):
            yield Node("face", face, _entity(face), path, self.persistent_id(face), world, depth)

        # `SUEntitiesGetNumEdges(entities, standalone_only, count)` — False means include edges that
        # bound faces. designPH tags real geometry edges, so standalone-only would lose them.
        for edge in self._list("SUEntitiesGetNumEdges", "SUEntitiesGetEdges", SUEdgeRef, entities,
                               extra=(False,)):
            yield Node("edge", edge, _entity(edge), path, self.persistent_id(edge), world, depth)

        for inst in self._list("SUEntitiesGetNumInstances", "SUEntitiesGetInstances",
                               SUComponentInstanceRef, entities):
            pid = self.persistent_id(inst)
            yield Node("window", inst, _entity(inst), path, pid, world, depth)
            t = SUTransformation()
            self.sdk.call("SUComponentInstanceGetTransform", inst, byref(t))
            child_world = compose(world, tuple(t.as_list()))
            definition = SUComponentDefinitionRef()
            self.sdk.call("SUComponentInstanceGetDefinition", inst, byref(definition))
            sub = SUEntitiesRef()
            self.sdk.call("SUComponentDefinitionGetEntities", definition, byref(sub))
            yield from self.walk(sub, path + (pid,), child_world, depth + 1, max_depth)

        for group in self._list("SUEntitiesGetNumGroups", "SUEntitiesGetGroups", SUGroupRef, entities):
            pid = self.persistent_id(group)
            t = SUTransformation()
            self.sdk.call("SUGroupGetTransform", group, byref(t))
            child_world = compose(world, tuple(t.as_list()))
            sub = SUEntitiesRef()
            self.sdk.call("SUGroupGetEntities", group, byref(sub))
            yield from self.walk(sub, path + (pid,), child_world, depth + 1, max_depth)

    def _list(self, count_fn: str, get_fn: str, ref_type, entities, extra: tuple = ()):
        return self.sdk.get_list(count_fn, get_fn, ref_type, entities, extra=extra)

    # -- the ENTITY-basis walk -------------------------------------------

    def walk_entities(self, model) -> Iterator[Node]:
        """Every entity in the model EXACTLY ONCE, regardless of how many times it is placed.

        ⚠ This is a different traversal from `walk()`, on purpose, and the difference is the whole
        placements-vs-entities distinction:

        - `walk()` recurses through instances, so a definition placed 400 times is visited 400
          times. That is the PLACEMENT basis, and it is what world transforms need.
        - `walk_entities()` enumerates the model's top-level entities plus each component and group
          DEFINITION once. Every entity appears exactly once because a definition's contents are
          stored once. That is the ENTITY basis, and it is what every count must be reported on.

        It is also ~1000x faster on real models, which is not a coincidence: Adelphi has 1441 tagged
        face entities behind 1,023,558 face placements, and the placement walk spends all its time
        re-visiting the same trees. The first attempt at this script used the placement walk for
        counting and did not finish.

        World transforms are meaningless here (an entity in a definition has no single world
        position), so every node carries IDENTITY and `path=()`. Anything needing world coordinates
        must use `walk()`.
        """
        from sdk import SUComponentDefinitionRef, SUEntitiesRef

        top = SUEntitiesRef()
        self.sdk.call("SUModelGetEntities", model, byref(top))
        containers = [top]

        for count_fn, get_fn in (
            ("SUModelGetNumComponentDefinitions", "SUModelGetComponentDefinitions"),
            ("SUModelGetNumGroupDefinitions", "SUModelGetGroupDefinitions"),
        ):
            for definition in self.sdk.get_list(count_fn, get_fn, SUComponentDefinitionRef, model):
                sub = SUEntitiesRef()
                self.sdk.call("SUComponentDefinitionGetEntities", definition, byref(sub))
                containers.append(sub)

        for entities in containers:
            for face in self._list("SUEntitiesGetNumFaces", "SUEntitiesGetFaces", SUFaceRef, entities):
                yield Node("face", face, _entity(face), (), self.persistent_id(face), IDENTITY, 0)
            for edge in self._list("SUEntitiesGetNumEdges", "SUEntitiesGetEdges", SUEdgeRef,
                                   entities, extra=(False,)):
                yield Node("edge", edge, _entity(edge), (), self.persistent_id(edge), IDENTITY, 0)
            for inst in self._list("SUEntitiesGetNumInstances", "SUEntitiesGetInstances",
                                   SUComponentInstanceRef, entities):
                yield Node("window", inst, _entity(inst), (), self.persistent_id(inst), IDENTITY, 0)
