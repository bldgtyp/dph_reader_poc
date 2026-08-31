# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Minimal ctypes binding to the SketchUp C SDK — shared by every Spike A gate script.

⚠ **PROVENANCE.** The framework this loads is a **third-party re-host** of Trimble's proprietary,
EULA-gated `SketchUpAPI.framework` (`martijnberger/pyslapi` release 0.24), used here because the
official SDK is behind a Request Access form with no reported turnaround
(`planning/02_headless-reader/RESULTS/HEADLESS-A_results.md` §1). Ed authorised this **for time-boxed laptop
feasibility only, in parallel with filing Trimble's form** (2026-08-28). Nothing built on it ships,
and every gate result derived through it is labelled feasibility-only evidence — it must be re-run
against the official SDK before anything is trusted. **No EULA ships in that zip**, so licensing
task L1 remains unstartable.

Design notes, all of them load-bearing:

- **Every string read goes through `SUStringGetUTF8Length` + a counted copy.** Never `c_char_p`.
  designPH's Marshal blobs contain `0x00` bytes, and a NUL-terminated read would truncate them
  silently — the worst case being a *false PASS* on a partially decoded table
  (`HEADLESS-A_sdk-feasibility.md` G4).
- **`SU*Ref` handles are structs wrapping one pointer**, not bare pointers. Passing a bare
  `c_void_p` where the ABI expects a one-field struct happens to work on arm64 for *arguments* and
  is wrong in general; the real struct type is used so the binding stays honest.
- **`SUResult` is checked on every call.** `SU_ERROR_NO_DATA` is a normal answer (an entity with no
  attribute dictionaries), not a failure, so callers can opt into tolerating specific codes.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import importlib.util
import re
import sys
from ctypes import POINTER, byref, c_char, c_double, c_int32, c_int64, c_size_t, c_void_p
from pathlib import Path
from typing import Any

# SUResult codes we name. The full enum is larger; these are the ones that carry meaning here.
SU_ERROR_NONE = 0
SU_ERROR_NULL_POINTER_INPUT = 1
SU_ERROR_INVALID_INPUT = 2
SU_ERROR_NULL_POINTER_OUTPUT = 3
SU_ERROR_INVALID_OUTPUT = 4
SU_ERROR_OVERWRITE_VALID = 5
SU_ERROR_GENERIC = 6
SU_ERROR_SERIALIZATION = 7
SU_ERROR_OUT_OF_RANGE = 8
SU_ERROR_NO_DATA = 9
SU_ERROR_INSUFFICIENT_SIZE = 10
SU_ERROR_UNKNOWN_EXCEPTION = 11
SU_ERROR_MODEL_INVALID = 12
SU_ERROR_MODEL_VERSION = 13
SU_ERROR_LAYER_LOCKED = 14
SU_ERROR_DUPLICATE = 15
SU_ERROR_PARTIAL_SUCCESS = 16
SU_ERROR_UNSUPPORTED = 17
SU_ERROR_INVALID_ARGUMENT = 18
SU_ERROR_ENTITY_LOCKED = 19
SU_ERROR_INVALID_OPERATION = 20

RESULT_NAMES = {v: k for k, v in list(globals().items()) if k.startswith("SU_ERROR_")}

# ⚠ There is NO version-enum map here, deliberately. `SUModelGetVersion` sounds like it returns the
# `SUModelVersion` enum (`SUModelVersion_SU2021` and friends) and it does NOT — it writes three
# ints: major, minor, build. Inferring the two-arg enum signature from the doxygen *name* passed on
# Adelphi (returning 22, which happens to be its writer's major version) and SEGFAULTED on the next
# model, because two unprovided out-pointers were being written through. A published name is not a
# signature; `a3_header_audit.py` now checks every declaration below against the shipped headers.

# SURefType / SUTypedValueType — READ FROM THE SHIPPED HEADERS, never hand-written.
#
# ⚠ These start empty and are filled in by `SDK._load_enums()` at load time, in place, so every
# module that did `from sdk import REF_TYPES` sees the corrected values.
#
# ⚠⚠ **A hand-copied enum is the same trap as a hand-copied signature, and it failed the same way.**
# The first version of this map was written from the published documentation and had
# `Face = 9`. In the shipped API 13.0 header, `SURefType` gained `Environment` and `Environments`
# at 8 and 9, so **`Face` is 11** and 9 is `Environments`. A host-face type check written against
# the doc order therefore rejected **every** glued host on every model — 0 of 239 — which reads
# exactly like "the glue query does not work" and is not. Spike A never noticed because none of its
# gates used this map; the contract-v2 collector's host test does.
#
# `SUTypedValueType` was correct as hand-written and is still parsed, for the same reason: being
# right once is not a reason to keep guessing.
REF_TYPES: dict[int, str] = {}

#: Hard rule 5 (type-check every attribute read) needs this: `areaGroupID` is a String `'n'` on
#: 1359 of Adelphi's 1441 tagged faces, and the tag is what says so.
TYPED_VALUE_TYPES: dict[int, str] = {}

#: (header file, enum name, member prefix) for each enum parsed out of the SDK's own headers.
_ENUMS = (
    ("model/defs.h", "SURefType", "SURefType_", REF_TYPES),
    ("model/typed_value.h", "SUTypedValueType", "SUTypedValueType_", TYPED_VALUE_TYPES),
)


class SUResultError(RuntimeError):
    def __init__(self, fn: str, code: int) -> None:
        super().__init__(f"{fn} -> {RESULT_NAMES.get(code, f'SU_ERROR_{code}')} ({code})")
        self.fn, self.code = fn, code


def load_module(path: Path, name: str) -> Any:
    """Import a module from a path — the one copy of the `importlib` dance.

    Four hand-written copies of these seven lines existed across the spike scripts, two of them
    defining the *same* `load_ruby_marshal` and both registering `sys.modules["ruby_marshal"]`, so
    a script importing both got whichever ran last. The repo's own rule — call the library's own
    function, even when it is one line — applies to your own loader; the boilerplate is exactly
    what makes copying feel cheaper than importing.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _ref(name: str) -> type[ctypes.Structure]:
    """An `SU*Ref` opaque handle: a struct wrapping a single pointer, exactly as the headers declare."""
    return type(name, (ctypes.Structure,), {"_fields_": [("ptr", c_void_p)]})


SUEntityRef = _ref("SUEntityRef")
SUModelRef = _ref("SUModelRef")
SUEntitiesRef = _ref("SUEntitiesRef")
SUFaceRef = _ref("SUFaceRef")
SUEdgeRef = _ref("SUEdgeRef")
SUVertexRef = _ref("SUVertexRef")
SULoopRef = _ref("SULoopRef")
SUComponentInstanceRef = _ref("SUComponentInstanceRef")
SUComponentDefinitionRef = _ref("SUComponentDefinitionRef")
SUGroupRef = _ref("SUGroupRef")
SUDrawingElementRef = _ref("SUDrawingElementRef")
SUOpeningRef = _ref("SUOpeningRef")
SUAttributeDictionaryRef = _ref("SUAttributeDictionaryRef")
SUTypedValueRef = _ref("SUTypedValueRef")
SUStringRef = _ref("SUStringRef")
SULayerRef = _ref("SULayerRef")


class SUPoint3D(ctypes.Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class SUVector3D(ctypes.Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("z", c_double)]


class SUTransformation(ctypes.Structure):
    """Column-major 4x4, same layout the contract's `transformation` array carries."""

    _fields_ = [("values", c_double * 16)]

    def as_list(self) -> list[float]:
        return list(self.values)


DEFAULT_FRAMEWORK = (
    Path(__file__).parent / "_private" / "sdk" / "sketchup_importer" / "SketchUpAPI.framework" / "SketchUpAPI"
)


class _ReadOnlyLib:
    """A `CDLL` that can only hand back symbols the binding **declared**.

    ⛔ **This is the structural half of "never save an opened model."**
    `SUEntityGetAttributeDictionary` is a get-or-CREATE, so a C-SDK reader mutates the in-memory
    model as a side effect of reading it — the only thing standing between that and a violation of
    hard rule 2 is that nothing ever writes the file back
    (`HEADLESS-A_results.md` §3.2). An *intention* not to save is not a check; a reader that
    **cannot resolve `SUModelSaveToFile`** is.

    The allow-list is `SDK.declared`, derived from the signature table itself, so it cannot drift
    from the binding: adding a writer to the table is the only way to make one reachable, and that
    is a visible edit rather than an accident.
    """

    def __init__(self, lib: ctypes.CDLL, allowed: frozenset[str]) -> None:
        self._lib = lib
        self._allowed = allowed

    def __getattr__(self, name: str):
        if name not in self._allowed:
            raise PermissionError(
                f"{name} is not declared by this binding, and this SDK handle is read-only. "
                "A headless reader must be incapable of saving an opened model "
                "(HEADLESS-B §2.2, hard rule 2)."
            )
        return getattr(self._lib, name)


class SDK:
    """A loaded SketchUpAPI framework, with `SUInitialize` already called.

    `read_only=True` wraps the library in `_ReadOnlyLib`, which is what the headless collector
    uses — see that class for why the property is structural rather than procedural.
    """

    def __init__(self, framework: Path | None = None, read_only: bool = False) -> None:
        self.path = Path(framework) if framework else DEFAULT_FRAMEWORK
        if not self.path.exists():
            raise SystemExit(
                f"SketchUpAPI framework not found at {self.path}\n"
                "Stage it first — see planning/02_headless-reader/RESULTS/HEADLESS-A_results.md §1.1"
            )
        self._raw_lib = ctypes.CDLL(str(self.path))
        self.headers = self.path.parent / "Headers"
        self._load_enums()
        self._configure()
        # Assigned exactly once. An earlier version bound `self.lib` to the raw library first so
        # `_configure` could use it, then rebound it to the wrapper — leaving `self.lib` meaning two
        # different things at two points of one constructor, in the class whose whole purpose is
        # that the guarded handle is the only one callers touch.
        self.lib = _ReadOnlyLib(self._raw_lib, self.declared) if read_only else self._raw_lib
        self._raw_lib.SUInitialize()
        self._initialized = True

    # -- plumbing ---------------------------------------------------------

    def _load_enums(self) -> None:
        """Fill `REF_TYPES` / `TYPED_VALUE_TYPES` from the framework's OWN headers, in place.

        Parsed rather than transcribed, because the published order and the shipped order are not
        the same thing: API 13.0's `SURefType` inserted `Environment`/`Environments` at 8 and 9, so
        every member after `Edge` sits two higher than the documentation's list. See the note beside
        `REF_TYPES`.
        """
        for relative, enum_name, prefix, target in _ENUMS:
            path = self.headers / relative
            if not path.is_file():
                raise SystemExit(
                    f"{enum_name} cannot be read: {path} is missing.\n"
                    "The enum values are NOT safe to assume — see the note beside REF_TYPES."
                )
            body = path.read_text(errors="replace")
            start = body.find(f"enum {enum_name} {{")
            if start < 0:
                raise SystemExit(f"{enum_name} not found in {path}")
            block = body[start : body.index("}", start)]
            target.clear()
            value = 0
            for member in re.finditer(rf"\b{prefix}(\w+)\b\s*(?:=\s*(\d+))?", block):
                if member.group(2) is not None:
                    value = int(member.group(2))
                target[value] = member.group(1)
                value += 1


    def _configure(self) -> None:
        """Declare argtypes/restype for everything used. ctypes defaults to int for untyped returns,
        which silently truncates a returned pointer on 64-bit — so nothing here is left undeclared."""
        L = self._raw_lib
        sig = [
            ("SUInitialize", [], None),
            ("SUTerminate", [], None),
            ("SUGetAPIVersion", [POINTER(c_size_t), POINTER(c_size_t)], c_int32),
            ("SUModelCreateFromFile", [POINTER(SUModelRef), ctypes.c_char_p], c_int32),
            ("SUModelRelease", [POINTER(SUModelRef)], c_int32),
            ("SUModelGetVersion",
             [SUModelRef, POINTER(c_int32), POINTER(c_int32), POINTER(c_int32)], c_int32),
            ("SUModelGetName", [SUModelRef, POINTER(SUStringRef)], c_int32),
            ("SUModelGetGuid", [SUModelRef, POINTER(SUStringRef)], c_int32),
            ("SUModelGetEntities", [SUModelRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUModelGetNumComponentDefinitions", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetComponentDefinitions",
             [SUModelRef, c_size_t, POINTER(SUComponentDefinitionRef), POINTER(c_size_t)], c_int32),
            ("SUModelGetNumGroupDefinitions", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetGroupDefinitions",
             [SUModelRef, c_size_t, POINTER(SUComponentDefinitionRef), POINTER(c_size_t)], c_int32),
            ("SUModelGetNumAttributeDictionaries", [SUModelRef, POINTER(c_size_t)], c_int32),
            ("SUModelGetAttributeDictionaries",
             [SUModelRef, c_size_t, POINTER(SUAttributeDictionaryRef), POINTER(c_size_t)], c_int32),
            # strings — length-aware only
            ("SUStringCreate", [POINTER(SUStringRef)], c_int32),
            ("SUStringRelease", [POINTER(SUStringRef)], c_int32),
            ("SUStringGetUTF8Length", [SUStringRef, POINTER(c_size_t)], c_int32),
            ("SUStringGetUTF8", [SUStringRef, c_size_t, POINTER(c_char), POINTER(c_size_t)], c_int32),
            # entities containers
            ("SUEntitiesGetNumFaces", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetFaces", [SUEntitiesRef, c_size_t, POINTER(SUFaceRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumEdges", [SUEntitiesRef, ctypes.c_bool, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetEdges",
             [SUEntitiesRef, ctypes.c_bool, c_size_t, POINTER(SUEdgeRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumInstances", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetInstances",
             [SUEntitiesRef, c_size_t, POINTER(SUComponentInstanceRef), POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetNumGroups", [SUEntitiesRef, POINTER(c_size_t)], c_int32),
            ("SUEntitiesGetGroups", [SUEntitiesRef, c_size_t, POINTER(SUGroupRef), POINTER(c_size_t)], c_int32),
            # entity identity + attributes
            # ⚠ returns the enum DIRECTLY; not an out-param call, and not SU_RESULT.
            ("SUEntityGetType", [SUEntityRef], c_int32),
            ("SUEntityGetID", [SUEntityRef, POINTER(c_int32)], c_int32),
            ("SUEntityGetPersistentID", [SUEntityRef, POINTER(c_int64)], c_int32),
            ("SUEntityGetNumAttributeDictionaries", [SUEntityRef, POINTER(c_size_t)], c_int32),
            ("SUEntityGetAttributeDictionaries",
             [SUEntityRef, c_size_t, POINTER(SUAttributeDictionaryRef), POINTER(c_size_t)], c_int32),
            ("SUEntityGetAttributeDictionary",
             [SUEntityRef, ctypes.c_char_p, POINTER(SUAttributeDictionaryRef)], c_int32),
            ("SUAttributeDictionaryGetName", [SUAttributeDictionaryRef, POINTER(SUStringRef)], c_int32),
            ("SUAttributeDictionaryGetNumKeys", [SUAttributeDictionaryRef, POINTER(c_size_t)], c_int32),
            ("SUAttributeDictionaryGetKeys",
             [SUAttributeDictionaryRef, c_size_t, POINTER(SUStringRef), POINTER(c_size_t)], c_int32),
            ("SUAttributeDictionaryGetValue",
             [SUAttributeDictionaryRef, ctypes.c_char_p, POINTER(SUTypedValueRef)], c_int32),
            # typed values
            ("SUTypedValueCreate", [POINTER(SUTypedValueRef)], c_int32),
            ("SUTypedValueRelease", [POINTER(SUTypedValueRef)], c_int32),
            ("SUTypedValueGetType", [SUTypedValueRef, POINTER(c_int32)], c_int32),
            ("SUTypedValueGetString", [SUTypedValueRef, POINTER(SUStringRef)], c_int32),
            ("SUTypedValueGetInt32", [SUTypedValueRef, POINTER(c_int32)], c_int32),
            ("SUTypedValueGetDouble", [SUTypedValueRef, POINTER(c_double)], c_int32),
            ("SUTypedValueGetBool", [SUTypedValueRef, POINTER(ctypes.c_bool)], c_int32),
            # faces / loops / geometry
            ("SUFaceGetArea", [SUFaceRef, POINTER(c_double)], c_int32),
            # ⚠ SUFaceGetArea takes NO transform, so it returns the face's LOCAL area. The Ruby
            # collector calls `face.area(transform)` (collector.rb:377), i.e. the WORLD area. On an
            # unscaled model the two agree and the difference is invisible; on a scaled one they do
            # not. This is the C analogue of the Ruby call — use it, rather than scaling the local
            # value locally, which would be re-implementing half of the library's rule.
            ("SUFaceGetAreaWithTransform",
             [SUFaceRef, POINTER(SUTransformation), POINTER(c_double)], c_int32),
            ("SUFaceGetOuterLoop", [SUFaceRef, POINTER(SULoopRef)], c_int32),
            ("SUFaceGetNumInnerLoops", [SUFaceRef, POINTER(c_size_t)], c_int32),
            ("SUFaceGetInnerLoops", [SUFaceRef, c_size_t, POINTER(SULoopRef), POINTER(c_size_t)], c_int32),
            ("SUFaceGetNormal", [SUFaceRef, POINTER(SUVector3D)], c_int32),
            ("SUFaceGetNumOpenings", [SUFaceRef, POINTER(c_size_t)], c_int32),
            ("SUFaceGetOpenings", [SUFaceRef, c_size_t, POINTER(SUOpeningRef), POINTER(c_size_t)], c_int32),
            ("SULoopGetNumVertices", [SULoopRef, POINTER(c_size_t)], c_int32),
            ("SULoopGetVertices", [SULoopRef, c_size_t, POINTER(SUVertexRef), POINTER(c_size_t)], c_int32),
            ("SUVertexGetPosition", [SUVertexRef, POINTER(SUPoint3D)], c_int32),
            ("SUEdgeGetStartVertex", [SUEdgeRef, POINTER(SUVertexRef)], c_int32),
            ("SUEdgeGetEndVertex", [SUEdgeRef, POINTER(SUVertexRef)], c_int32),
            # instances / definitions / transforms
            ("SUComponentInstanceGetDefinition",
             [SUComponentInstanceRef, POINTER(SUComponentDefinitionRef)], c_int32),
            ("SUComponentInstanceGetTransform",
             [SUComponentInstanceRef, POINTER(SUTransformation)], c_int32),
            ("SUComponentInstanceGetName", [SUComponentInstanceRef, POINTER(SUStringRef)], c_int32),
            ("SUComponentInstanceGetNumAttachedToDrawingElements",
             [SUComponentInstanceRef, POINTER(c_size_t)], c_int32),
            ("SUComponentInstanceGetAttachedToDrawingElements",
             [SUComponentInstanceRef, c_size_t, POINTER(SUDrawingElementRef), POINTER(c_size_t)], c_int32),
            ("SUComponentDefinitionGetEntities",
             [SUComponentDefinitionRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUComponentDefinitionGetName", [SUComponentDefinitionRef, POINTER(SUStringRef)], c_int32),
            ("SUGroupGetEntities", [SUGroupRef, POINTER(SUEntitiesRef)], c_int32),
            ("SUGroupGetTransform", [SUGroupRef, POINTER(SUTransformation)], c_int32),
            ("SUGroupGetName", [SUGroupRef, POINTER(SUStringRef)], c_int32),
            # tags — the contract ships a SketchUp tag (layer) name on every unclassified face.
            ("SUDrawingElementGetLayer", [SUDrawingElementRef, POINTER(SULayerRef)], c_int32),
            ("SULayerGetName", [SULayerRef, POINTER(SUStringRef)], c_int32),
        ]
        #: Every symbol this binding declares. ⛔ **There is no writer in it** — no
        #: `SUModelSaveToFile`, no `SUEntityAddAttributeDictionary`, no `SU*Set*` — and
        #: `read_only=True` turns that from a fact about this list into a property of the process:
        #: the reader cannot resolve a symbol it did not declare, so it cannot save. See
        #: `_ReadOnlyLib`.
        self.declared = frozenset(name for name, _, _ in sig)
        for name, args, res in sig:
            fn = getattr(L, name, None)
            if fn is None:
                continue  # reported by `missing()`, not fatal at load time
            fn.argtypes = args
            if res is not None:
                fn.restype = res

    def missing(self, names: list[str]) -> list[str]:
        """Which of these symbols the loaded binary does not export. A doc name is not a symbol.

        Asks the **raw** library on purpose: this is a question about what the binary exports, not
        about what this handle may call. `a7_capability_probe.py` uses it to report that the write
        symbols are present and therefore worth refusing (`_ReadOnlyLib`).
        """
        return [n for n in names if not hasattr(self._raw_lib, n)]

    def check(self, name: str, code: int, tolerate: tuple[int, ...] = ()) -> int:
        if code != SU_ERROR_NONE and code not in tolerate:
            raise SUResultError(name, code)
        return code

    def call(self, name: str, *args: object, tolerate: tuple[int, ...] = ()) -> int:
        return self.check(name, getattr(self.lib, name)(*args), tolerate)

    # -- strings ----------------------------------------------------------

    def read_string(self, su_string: SUStringRef) -> bytes:
        """Read an `SUStringRef` as RAW BYTES via the length-aware API.

        ⚠ Returns `bytes`, not `str`, deliberately. designPH's Marshal tables come back through this
        path and contain `0x00` and arbitrary non-UTF-8 sequences; decoding here would corrupt them.
        Callers that want text decode explicitly.
        """
        length = c_size_t()
        self.call("SUStringGetUTF8Length", su_string, byref(length))
        n = length.value
        buf = (c_char * (n + 1))()
        out = c_size_t()
        self.call("SUStringGetUTF8", su_string, n + 1, buf, byref(out))
        return bytes(buf[: out.value])

    def string_out(self, fn: str, *args: object) -> bytes:
        """Call an SU function whose last out-param is an SUStringRef, and return its raw bytes."""
        s = SUStringRef()
        self.call("SUStringCreate", byref(s))
        try:
            self.call(fn, *args, byref(s))
            return self.read_string(s)
        finally:
            self.lib.SUStringRelease(byref(s))

    # -- counted list helper ---------------------------------------------

    def get_list(self, count_fn: str, get_fn: str, ref_type, *head: object, extra: tuple = ()):
        """The SDK's universal two-call idiom: GetNumX then GetX into a caller-allocated array."""
        n = c_size_t()
        self.call(count_fn, *head, *extra, byref(n))
        if n.value == 0:
            return []
        arr = (ref_type * n.value)()
        got = c_size_t()
        self.call(get_fn, *head, *extra, n.value, arr, byref(got))
        return list(arr[: got.value])

    # -- lifecycle --------------------------------------------------------

    def api_version(self) -> tuple[int, int]:
        major, minor = c_size_t(), c_size_t()
        self.lib.SUGetAPIVersion(byref(major), byref(minor))
        return major.value, minor.value

    def open_model(self, path: Path) -> SUModelRef:
        model = SUModelRef()
        self.call("SUModelCreateFromFile", byref(model), str(path).encode("utf-8"))
        return model

    def close_model(self, model: SUModelRef) -> None:
        self.lib.SUModelRelease(byref(model))

    def model_version(self, model: SUModelRef) -> tuple[int, int, int]:
        """(major, minor, build) of the SketchUp that wrote the file — NOT the `SUModelVersion` enum."""
        major, minor, build = c_int32(), c_int32(), c_int32()
        self.call("SUModelGetVersion", model, byref(major), byref(minor), byref(build))
        return major.value, minor.value, build.value

    def entity_type(self, entity: SUEntityRef) -> str:
        """`SURefType` name. Returns the enum directly — no out-param, no SUResult."""
        return REF_TYPES.get(self.lib.SUEntityGetType(entity), "?")

    def terminate(self) -> None:
        if getattr(self, "_initialized", False):
            self._raw_lib.SUTerminate()
            self._initialized = False
