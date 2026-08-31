# POC-1 — SketchUp runbook **[Ed]**

> ✅ **DONE — 2026-08-21. All three runs passed; POC-1's gate is closed.**
> Kept as the record of what was run and what each step answered. Results and the gate:
> [`POC-1_results.md`](POC-1_results.md) §7.
>
> Nothing here needs repeating on macOS. **Still outstanding and not runnable here: Windows** — the
> Phase 3 verdict stays *PASS-pending-Windows* and so does this one.

**Status: ✅ complete.** Everything the agent could prove without SketchUp was green
(`POC-1_results.md` §3); these three runs closed the one thing no harness reaches — **`HtmlDialog`
itself**, its threading, and whether it will load a `http://127.0.0.1` page at all. It does.

**Everything here is read-only.** Nothing writes to `DesignPH_dict`, nothing writes to the model.

> **Updated 2026-08-20:** POC-2 landed the real collector, so Run 3 below now reads the model you
> have open rather than a canned fixture. Runs 1 and 2 are unchanged — they are about the runtime,
> not the model. If you are doing both runbooks in one sitting, do this one first: it is the
> shorter, and a failure here explains a failure there.

⚠ **Internal build. Do not share the `.rbz`** — not with a beta tester, not with PHI, not in a
public repo. Sharing is the act that changes the AGPL footing
(`planning/01_sketchup-export/implementation/00_POC_OVERVIEW.md` §2.3).

## Setup

| | |
|---|---|
| Install | `cd ~/Desktop/dph_plus_testing/poc && make ed` — builds and copies into Plugins/ |
| Then | **restart SketchUp** |
| Menu | **Extensions → DesignPH-PLUS POC** |
| Model | Runs 1–2: any open model. Run 3: a **copy** of a designPH model |

Open **Window → Ruby Console** first. Everything reports there.

The Phase 3 spike may still be installed; the two are separate extensions with separate menus and
do not collide. To remove the POC afterwards:

```
rm -rf ~/Library/Application\ Support/SketchUp\ 2022/SketchUp/Plugins/dph_plus_poc ~/Library/Application\ Support/SketchUp\ 2022/SketchUp/Plugins/dph_plus_poc.rb
```

---

## Run 1 — Server only *(30 seconds; do it first)*

Separates "the socket works" from "`HtmlDialog` will load it". From a blank dialog those two look
identical, and telling them apart is what the spike's first failed run could not do.

1. **Extensions → DesignPH-PLUS POC → Diagnostics → `Server only (open in browser)`**
2. The Ruby Console prints a URL. Open it in **any browser**. The server stays up for 2 minutes.

| What you see | What it means |
|---|---|
| The POC page loads; console shows `request #1: 200 html/index.html` | ✅ The pump works. Go to Run 2 |
| Browser **hangs / spins**, no console line | The timer is not firing — the socket is bound but starved. Stop and tell me |
| `ERR_CONNECTION_REFUSED` | The server never bound. Copy the console and tell me |

The page will boot Pyodide and then say *no `sketchup` host object* — **that is correct** here.
You opened it outside the dialog; serving is all this run tests.

---

## Run 2 — Runtime self-test ⚠ **THE GATE**

1. **Extensions → DesignPH-PLUS POC → Diagnostics → `Runtime self-test`**
2. A dialog opens and logs its way through the boot. Expect **2–5 seconds**.
3. It ends with a green **PASSED** banner listing four checks, then a message box.

| Banner | What it means |
|---|---|
| **PASSED**, 4 checks ok | ✅ The gate. Go to Run 3 |
| **FAILED**, `stack imports` | A wheel did not install. Send me the log pane |
| **FAILED**, `bridge round trip` | `execute_script` is truncating. Send me the log pane |
| Dialog opens but stays on `starting…` / `booting…` | The dialog did not reach the server. Copy the Ruby Console — there is a warning after 6 s that says which half failed |
| **SketchUp beachballs** | Stop. That is a threading rule broken; do not wait it out. Tell me and I diff against the spike rather than debugging forward |

**What I need back:** the file the run writes beside your model,
`<model>__self_test_<stamp>.json` (or on your Desktop if the model is unsaved). It carries every
measurement — boot time, import time, unpack time, `.rbz` and installed sizes, wasm heap.

---

## Run 3 — Export HBJSON

Proves the product path end to end: collector → bridge → Pyodide → translator → save dialog → disk.

⚠ **Open a COPY**, not a corpus original (hard rule 3). `~/Desktop/dph_poc_copies/adelphi-designph_COPY.skp`
if you have already done POC-2's setup; any copy otherwise.

1. **Extensions → DesignPH-PLUS POC → `Export HBJSON…`**
2. It boots, walks the model, translates, then opens a **save dialog**. Accept the suggested name.
3. Expect a **PASSED** banner with three checks, and a message box naming the files written.

Two files land beside the name you chose: `<name>.hbjson` and `<name>.report.json`. On the Adelphi
copy expect roughly 82 faces translated and a report naming ~1359 unclassified ones — the report is
the interesting artefact, not the HBJSON.

| What you see | What it means |
|---|---|
| Both files written, banner PASSED | ✅ Done. Send me the report JSON |
| `classified faces translated 0 of N` | The extraction did not survive the bridge. Send me the report |
| Banner FAILED on `no identifier collision` | A real finding — deeply nested faces colliding after honeybee truncates ids at 100 characters. Send me the report |
| Save dialog never appears | Send me the Ruby Console |

*(Optional)* **Diagnostics → `Save extraction JSON`** is a checkbox. Turn it on and re-run to also
get `<name>.extraction.json` — what Ruby actually sent. POC-5's corpus sweep uses it; nothing in
this run needs it.

---

## Grading it

Three lines back is enough:

```
Run 1: page loaded / hung / refused
Run 2: PASSED or FAILED + which check
Run 3: PASSED or FAILED + hbjson bytes
```

…plus the `__self_test_*.json` file. A run nobody can grade at a glance has not reported anything —
that is why every one of these ends in a banner rather than in a log tail.
