# POC-1 — Runtime Shell — results

**Status: ✅ GATE CLOSED — PASS. Ed's SketchUp session ran 2026-08-21; all five clauses met (§7).**
**Date:** 2026-08-20, gated **2026-08-21** · **Plan:** [`../POC-1_runtime-shell.md`](../POC-1_runtime-shell.md)

> The extension skeleton exists, builds to a **6.72 MB `.rbz`**, and boots the whole stack in a real
> **Chromium 88** — the engine SketchUp 2022 embeds — in **3.4 s**, translating a 6-face extraction
> to valid HBJSON through the frozen `translate_json` seam. Two things POC-1's plan asked for are
> *deliberately not* the spike's code, and both are noted in §4. A four-angle review pass then found
> nine things worth fixing before the code became load-bearing for POC-2 and POC-3 (§6).

---

## 1. What was built

```
pocs/01_sketchup-export/
  Makefile                     the gate: `make ci`
  ext/
    dph_plus_poc.rb            loader stub, module DphPlusPoc
    dph_plus_poc/
      main.rb                  menu, Session (dialog + server lifecycle), bridge, file writing
      server.rb                the loopback server, extracted whole from the spike
      collector.rb             ⚠ a stub at POC-1 — **superseded by POC-2's real collector**
      fixtures/stub_extraction.json    6 classified faces, contract v2 shape
      html/{index.html, app.js, boot.py}
      vendor/                  staged payload (gitignored)
      build_info.json          written by build_rbz.py (gitignored)
    tests/test_static_server.rb
  py/
    dph_translator/{__init__,contract,report,translate,entry}.py
    tests/{conftest,test_contract,test_translate,test_entry,test_boot}.py
    pyproject.toml             pins + pytest/ruff/mypy config
  tools/{vendor_payload,build_rbz,verify_in_chrome}.py
  vendor/, dist/               download cache and build output (gitignored)
```

`pocs/01_sketchup-export/_private/` is gitignored and reserved for POC-2's real-corpus captures. It does not exist yet —
nothing in POC-1 touches client data.

**Superseded since:** POC-2 replaced `collector.rb`'s stub with the real walk, and POC-3 replaced
`translate.py` with the eleven-module translation core. The seam between them — `translate_json` —
is unchanged, which is what POC-1 existed to fix.

## 2. Measurements

Read off the self-test's own verdict JSON
([`baselines/poc1_chromium88.json`](baselines/poc1_chromium88.json)), not reported as prose.

| | POC-1, Chromium 88 | Phase 3, Chromium 88 | Phase 3, SketchUp 2022 |
|---|---|---|---|
| Pyodide ready | 1952 ms | — | — |
| Payload staged (9 archives fetched) | 1977 ms | — | — |
| Payload unpacked (`zipfile`) | 2218 ms | — | — |
| **Cold start to `import honeybee_ph`** | **3445 ms** | 3.5 s | 2.6 s |
| — of which Python-side imports | 1161 ms | — | — |
| Peak WASM heap | 28.8 MB | 28.8 MB | 28.8 MB |
| JS heap | 61 MB | — | — |
| `.rbz` | **6.72 MB** | 6.66 MB | 6.66 MB |
| Installed footprint | **20.79 MB** | 20.7 MB | 20.7 MB |
| Bridge round trip | 1 MB ok (probe ceiling) | 4 MB | 4 MB |
| Python | 3.11.3, Emscripten 3.1.45 | same | same |

**No regression.** Cold start is inside Phase 3's Chromium-88 figure and far inside POC-1 §6's
"boot regression past ~5 s" fail line. The `.rbz` grew **+60 KB** over Phase 3: the translator zip
(12 KB), the stub extraction fixture, and ~40 KB from dropping deflate from level 9 to level 6 —
which cut build time from 5.8 s to 2.1 s and costs 0.6 % of size, because 18 of the 20 MB is
already-compressed payload. The install footprint is the number the user feels; it is recorded
separately per the house lesson that a compressed download size is not a bundle size, and both come
from `build_info.json` rather than being recomputed at runtime.

The bridge probe stops at 1 MB by design. Phase 3 measured the ceiling at ≥4 MB each way; this is a
regression check on a restructured bridge, not a re-measurement, and Adelphi's real payload is
19 KB.

## 3. Verification — everything provable without SketchUp

`make ci`, all green on 2026-08-20:

| Step | Result |
|---|---|
| `ruff check` + `ruff format --check` | clean |
| `mypy` (strict on the translator) | no issues, 5 files |
| `pytest` | **59 passed** |
| `ruby -c`, 5 files | OK |
| `ruby ext/tests/test_static_server.rb` | ALL CHECKS PASSED (19 checks) |
| `build_rbz.py` | 6.72 MB `.rbz`, 20.79 MB installed |
| `verify_in_chrome.py` on **Chromium 88.0.4324.0** | **PASSED** — 4 checks |

The Chromium 88 snapshot (rev `827102`) is cached at
`~/.cache/dph-plus/chromium-88/` — outside the repo, one `curl` to recreate; the download line is in
`verify_in_chrome.py`'s docstring. **The harness refuses any other major version**: pointing it at
the modern Chrome on the machine would pass everything Chromium 88 cannot do, which is a false
green and was the trap POC-1 §5 flagged.

⚠ `ruby -c` runs on the **system Ruby 2.6.10**, not 2.7. That is conservative in the right
direction — 2.7-only syntax fails here — but it does not prove 2.7 acceptance of anything 2.6
rejects. No file uses 2.7-only syntax.

## 4. Deviations from the plan, and why

| Plan said | What was built | Why |
|---|---|---|
| Port `verify_in_chrome.py`, "paths only" | Rewritten to **one mode** (serve the staged extension, stub the host), and it **refuses non-88 browsers** | Its `file`, `file-permissive` and `http` modes existed to answer the `file://` question. That is now hard rule 8, settled inside SketchUp. Keeping three dead modes and a `harness.html` that is not promoted would be carrying a decision that has already been taken. The version guard is new and closes POC-1 §5's own warning structurally |
| `spike.js`'s two-rung fetch ladder | **Dropped** — plain `fetch` only | Same reason. The ladder existed because `file://` was under test; the page is now only ever served over `http://127.0.0.1`, where `fetch` works. `SKETCHUP_RUNTIME.md` §4.3 |
| Bridge probe to 4 MB | 1 MB | See §2 |
| `vendor/` "generated by `vendor_payload.py`" | Two tiers: `pocs/01_sketchup-export/vendor/` (download cache) → `pocs/01_sketchup-export/ext/dph_plus_poc/vendor/` (staged, trimmed) | Same shape as the spike. It is what lets `verify_in_chrome.py` detect a staged tree that has drifted from source |

**Kept verbatim, and commented as untouchable:** `server.rb`'s worker-thread + sleeping-timer shape,
the log queue and its flush-before-kill, the 32-hex path token, the directory-escape guard, the
COOP/COEP headers, the MIME table, the 6-second "dialog asked for nothing" diagnostic, per-request
logging, `zipfile` unpack with no `micropip` anywhere, and `import honeybee_ph` last.

## 5. What POC-1 fixed for the phases that follow

- **The seam is `dph_translator.entry.translate_json(str) -> str`**, returning
  `{hbjson, report, verdict}` serialised (POC-1 §4.1). POC-3 replaces the *body*; the signature and
  the packaging do not move. `test_entry.py` pins the contract of the call, including that garbage
  input returns a verdict rather than raising — an exception crossing the wasm boundary loses its
  traceback and leaves the banner with nothing to show.
- **The translator ships as a zip installed by the same `zipfile` path as the eight wheels.** No
  packaging change is needed at integration.
- **Staleness is structurally impossible.** `build_rbz.py` records the translator's source hash in
  `build_info.json`; `--check` recomputes it, and `verify_in_chrome.py` calls that before driving
  anything. "Tests passed on code the `.rbz` doesn't contain" cannot happen quietly.
- **The verdict shape is fixed** — `{passed, checks:[{label, ok, detail}]}` — and rendered
  identically by the dialog banner, the closing message box, and the Chromium harness.
- **One code path, three hosts.** `boot.py` and the translator run under pytest on CPython 3.11, in
  Chromium 88, and in SketchUp. `test_boot.py` exercises the extension tree's own `boot.py` by
  path rather than a copy.
- **One place for each fact that two things depend on.** The wheel pins live only in
  `pocs/01_sketchup-export/py/pyproject.toml` — the Makefile installs from it and `vendor_payload.py` parses it, so the
  test venv and the shipped `.rbz` cannot come from different lists. `stub_extraction.json` is read
  by the Ruby collector, pytest *and* the Chromium harness from one location. `Collector.stub?` is
  derived from the payload rather than a flag POC-2 must remember to flip. The two size numbers come
  from `build_info.json` rather than being recomputed at runtime.
- **Failure granularity is set at the right layer.** `contract.parse` hard-fails only on what makes
  the *document* unreadable (wrong version, no `faces` list); a malformed individual record survives
  with an `error` and is named in the report. POC-3 adds window and edge parsing into that shape
  rather than having to invent a soft-failure channel.
- **`edges`, `windows` and `unclassified` are read by the contract layer**, not string-keyed out of
  `raw` at the call site — so POC-3 gives them types without moving their readers.

## 6. Findings

| # | Finding | Consequence |
|---|---|---|
| 42 | **A self-test that re-imports an already-imported stack reports 0.0 ms and reads as a pass.** The first Chromium 88 run graded "stack imports ok (0.0 ms)"; the imports had happened during boot and `import_stack()` was re-timing a warm `sys.modules` | `import_stack()` now memoises its first result. A measurement taken after the thing being measured has already happened is not a measurement, and it fails *green* — which is worse than failing red |
| 43 | **A second `Room` built from the same `Face` objects steals them.** honeybee's `Room.__init__` sets `face._parent`, so constructing a throwaway Room to read `geometry.is_solid` would silently re-parent every face of the real one | Build exactly one `Room` per run and measure it. Caught in review, before it shipped |
| 44 | The Chromium 88 snapshot survives as a **permanent local tool**, not a phase artifact | Cached at `~/.cache/dph-plus/`; POC-4 and POC-5 both need it. Recorded here so it is not re-derived |
| 45 | **honeybee truncates identifiers at 100 characters, silently** — and the contract's path-qualified ids are long | Five levels of component nesting overflows, and two faces under the same deep parent then differ only in a cut-off tail: **two envelope surfaces merging into one**. `translate` now checks for duplicate identifiers after cleaning and fails the verdict on one. Recorded in `HONEYBEE_STACK.md` §4 |
| 46 | **A hand-rolled identifier sanitiser hides that trap behind an `AssertionError`.** A local regex matching only honeybee's character class, without its length cap, lets a long model name raise from inside `Room()` — outside every per-face guard | Use `honeybee.typing.clean_string`. The rule belongs to honeybee; re-implementing half of it converts a reportable problem into an unattributable crash |
| 47 | **`__pycache__` was shipping inside the `.rbz`.** A "does not start with a dot" archive filter put 12 KB of stale bytecode from a test run into the artifact | The two size numbers this tool exists to report were wrong by whatever a lint run had left behind. Now an explicit skip set, mirroring `RUNTIME_SKIP` right beside it |
| 48 | **Max compression buys nothing on an already-compressed payload.** Level 9 took 1.94 s and saved 40 KB (0.6 %) over level 6's 0.54 s | 18 of the 20 MB is `python_stdlib.zip`, the `.wasm` and eight `.whl` — all already deflate. Build time 5.8 s → 2.1 s, and `make ci` builds every run |
| 49 | **An undecodable table and an absent table are different facts**, and dropping both to `None` merges them | Adelphi legitimately has no `connections_ud`; a Marshal decode failure is a collector bug. POC-3's tier resolution needs to tell them apart, so `parse` now returns the reason and `translate` reports it |

## 7. Gate

POC-1 §6's PASS clause: *self-test verdict `PASSED` inside SketchUp 2022 (boot, imports, bridge
echo, fixture HBJSON written via the save dialog); Chromium 88 harness green; server tests green;
cold start within 2× of Phase 3's 2.6 s.*

| Clause | State |
|---|---|
| Chromium 88 harness green | ✅ PASSED, 4 checks |
| Server tests green | ✅ 19 checks |
| Cold start within 2× of 2.6 s (≤5.2 s) | ✅ **2577 ms in SketchUp**, 3.2 s on Chromium 88 |
| Self-test `PASSED` **inside SketchUp 2022** | ✅ **PASSED**, 4 checks, 2026-08-21 |
| HBJSON written via the save dialog | ✅ — and against a **real model**, not the fixture |

**Verdict: ✅ PASS.** No FAIL condition triggered: no silent hang, no boot regression (2577 ms
against a ~5 s line).

### 7.1 What Ed's session established, 2026-08-21

SketchUp **22.0.353**, macOS arm64-darwin20, Ruby **2.7.2**.

| Run | Result |
|---|---|
| **1 — server only** | 19 requests, all 200, **including `pyodide.asm.wasm` at 8,995,509 bytes**. That single response is what deadlocked the main thread in the Phase 3 spike's round 2; the worker-thread + sleeping-timer shape holds on real hardware |
| **2 — runtime self-test** | **PASSED**, 4 checks. Boot 2577 ms, bridge 1 MB round trip in 201 ms, wasm heap 28.8 MB |
| **3 — export HBJSON** | **PASSED**, 82 of 82 faces, 96,179 bytes, written via the save dialog |

Three incidental confirmations worth keeping:

- **Ruby 2.7.2 accepted all 8 files.** `ruby -c` runs on the system 2.6.10 — conservative, and now
  confirmed rather than assumed.
- ⚠ **SketchUp's CEF boots *faster* than the headless Chromium 88 snapshot** (2577 vs 3216 ms). The
  offline harness is a **pessimistic** proxy, which is the safe direction, and the opposite of what
  one would guess. `SKETCHUP_RUNTIME.md` §12.
- ⚠ **`UI.messagebox` blanks the dialog while it is up** — CEF cannot repaint from a blocked main
  thread. It repaints intact on dismiss. Alarming once; not a defect.

### 7.2 Two cosmetic defects found in the same session — ✅ both fixed 2026-08-21

| | Defect | Fix |
|---|---|---|
| 1 | **The verdict banner reads `booting…` forever on a standalone page load.** With no `sketchup` host object the page never dispatches an action, so nothing writes a verdict — a run that *succeeded* showing a banner that implies it is still working. Finding 41's failure mode in miniature | The standalone path now writes its own verdict: boot succeeded, nothing dispatched |
| 2 | **The server's request log skips a sequence number.** `favicon.ico` increments the counter and returns before logging, so the log shows `#4, #6, #7` with no `#5`. Harmless, and a gap in a sequence is exactly what a silently-dropped request would look like — which defeats the point of numbering them | `favicon.ico` is logged too (`204`). The sequence is contiguous, so a gap means something |

## 8. Deliberately not fixed — carried to POC-4

Two efficiency findings are real, were measured, and are **not** POC-1's to act on:

| | Finding | Why it waits |
|---|---|---|
| **Every dialog open re-downloads the 18 MB runtime.** A fresh port, a fresh path token and `Cache-Control: no-store` stack into three independent cache-busters; more than half of the 3.4 s cold start is re-fetching byte-identical assets | The fix — one server per process, plus `ETag`/`Last-Modified` on `vendor/` — changes the `Session` lifetime and `server.rb`'s headers. `server.rb` is the file whose shape four silent SketchUp hangs paid for, and POC-1 has no evidence about how CEF revalidates. **Measure it in POC-4, with SketchUp in the loop** |
| **The HBJSON still crosses the bridge inside a JSON envelope.** JS no longer re-serialises it (the translator's string is forwarded verbatim), but Ruby still parses the envelope to reach it | At POC-1's 27 KB this is nothing; at POC-3's output it is a real cost, and the fix (a fourth callback that hands Ruby the HBJSON string alone) is only worth designing once the payload sizes are known. ✅ **They are known now** (2026-08-21): extractions 334–501 KB in, HBJSON 324–686 KB out, against a 4 MB verified bridge. Still comfortable, and the envelope parse is now the largest single avoidable cost on the path |

## 9. Out of scope, unchanged

Real collection (POC-2), real translation (POC-3), any UI beyond the verdict banner and the save
dialog, Windows, other SketchUp versions.
