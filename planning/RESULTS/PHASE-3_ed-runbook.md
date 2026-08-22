# Phase 3 — SketchUp runbook **[Ed]**

> ✅ **Done — 2026-08-19. The gate passed.** Kept as the record of what was run and what each step
> answered; nothing here needs repeating on macOS.
>
> The successful run is `~/Desktop/dph_phase3_copies/adelphi-designph_COPY__phase3_result_260819_213955.json`
> with its HBJSON beside it. Results and the gate:
> [`PHASE-3_results.md`](PHASE-3_results.md).
>
> **Still outstanding, and not runnable here:** Windows (step A on a Windows machine), and SketchUp
> 2021 to test PRD §7.4's floor. Until Windows is done the verdict stays *PASS-pending-Windows*.
>
> It took four rounds. Round 1 died on a Ruby thread that never ran, round 2 on blocking socket
> writes deadlocking the main thread, round 3 on modern Pyodide not parsing in Chromium 88, and
> round 4 worked. All four are recorded as Findings 30, 32, 34 and 38.

**Everything here is read-only.** Nothing writes to `DesignPH_dict`, nothing writes to the model.
The spike writes two files *beside the open `.skp`* — a result JSON and an HBJSON.

## Setup

| | |
|---|---|
| Extension | reinstalled — **restart SketchUp** so it picks up the fix |
| Working copy | `~/Desktop/dph_phase3_copies/adelphi-designph_COPY.skp` |
| Menu | **Extensions → DesignPH-PLUS Spike** |

Open **Window → Ruby Console** first. Everything reports there.

To remove afterwards:

```
rm -rf ~/Library/Application\ Support/SketchUp\ 2022/SketchUp/Plugins/dph_plus_spike ~/Library/Application\ Support/SketchUp\ 2022/SketchUp/Plugins/dph_plus_spike.rb
```

---

## B. Server only — menu item **3** *(skip unless A misbehaves)*

You already passed this one. Kept here because it isolates the socket from the dialog if round 3
misbehaves.

1. Open the model (any model — this run does not read it).
2. **Extensions → DesignPH-PLUS Spike → `3. Test the server only -- open the URL in a browser`**
3. The Ruby Console prints a URL. Open it in a browser. The server stays up for **2 minutes**.

| What you see | What it means |
|---|---|
| The spike page loads, console shows `request #1: 200 html/index.html` | ✅ The pump works. Go to Run 2 |
| Browser **hangs / spins** with no console line | The timer is not firing. Tell me — the socket is bound but starved, same class of bug as last time |
| `ERR_CONNECTION_REFUSED` | The server did not bind at all, or was already stopped. Copy the console |

The page will sit on `starting…` here, and that is correct — it says
*no `sketchup` host object* because you opened it outside the dialog. Serving is all this run tests.

---

## A. The spike through the dialog — menu item **1** ⚠ **THE GATE. Do this one.**

1. Open `~/Desktop/dph_phase3_copies/adelphi-designph_COPY.skp`
2. **Extensions → DesignPH-PLUS Spike → `1. Run spike -- local HTTP server (recommended)`**
3. Expect it to finish in **under 30 seconds**, then a message box with the result path.

| What you see | What it means |
|---|---|
| Log reaches `pyodide ready in … ms`, then `boot complete`, then a message box | **PASS.** Expect roughly 3–4 s to `pyodide ready` |
| `SyntaxError` or a `CompileError` about wasm | The Pyodide pin is still wrong for your CEF. Send me the result file |
| Blank dialog **and** `WARNING: 6 s after opening, the dialog has requested nothing` | HtmlDialog refused to load a loopback URL. That is a real finding — say so immediately |
| Blank dialog, but console shows `request #1: 200 …` lines | The page loaded and something inside it failed. Copy the console |
| Dialog opens but stays on `starting…` | The page loaded, its scripts did not. Copy the console |

⚠ Two things that look like hangs and are not. SketchUp goes **sluggish while the dialog is open** —
that is the server handing CPU to its worker threads, and it stops when you close the dialog. And it
goes **properly unresponsive for up to a minute** while Python round-trips the model; on Chromium 88
that check takes ~36 s for a big model. Writing the HBJSON is fast (~140 ms); it is the *verification*
that is slow, and v1 will not do it.

⚠ **The message box says "finished" whether it worked or not.** Last round it appeared over a failed
run. Trust the dialog log and the result file, not the box.

---

## C. ~~`file://`~~ — menu item **2** ✅ **done, no need to repeat**

**Answered 2026-08-19.** It failed as predicted —
`TypeError: Failed to fetch dynamically imported module: file:///…/pyodide.asm.js`, and the XHR shim
was refused too. SketchUp's CEF does **not** grant local file access, so the loopback server is
mandatory rather than merely preferred (Finding 37). Nothing more to run here.

---

## D. Face payload size — menu item **Report face payload size**

**Extensions → DesignPH-PLUS Spike → `Report face payload size (no dialog)`**

Two console lines: how many faces designPH has classified, how many carry `DesignPH_dict` at all, and
what each costs as JSON. No Pyodide, no dialog, no socket — so it works whatever the runs above did.

Worth repeating on a bigger model — `2414_Bluff Reach` or `2605 MacDonough` from
`~/Desktop/dph_phase1_copies/`. Adelphi has only 82 classified faces; a real project is the better
test of whether the bridge needs chunking.

---

## What I need back

Just **A**, and **D** if you have a spare moment. B and C are already answered.

⚠ **The runbook letters are not the menu numbers.** They used to be, and the collision sent a run to
the wrong menu item. The menu item to click is named in each heading in bold.

That closes the Mac half. Windows stays open regardless — the plan is explicit that Mac results do
not transfer, so even a clean sweep records as **PASS-pending-Windows**.
