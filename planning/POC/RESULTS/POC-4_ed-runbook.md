# POC-4 — SketchUp runbook **[Ed]**

**Status: ✅ COMPLETE — all four runs done, 2026-08-21. POC-4's gate is closed PASS.**

Kept as the record of what was asked and what came back. Results in
[`POC-4_results.md`](POC-4_results.md) §6.

> ### ▶ ~~Before the rest: `cd poc && make ed`, then restart SketchUp~~ — done
>
> Run A found one defect: the dialog banner showed a green **`PASSED`** while the message box beside
> it said **`PASSED WITH OMISSIONS`**, with 40 assemblies unresolved. It is fixed — but run B went
> ahead on run A's build (confirmed by file timestamp, not guessed), so the fix is still not
> installed. It changed nothing about run B, which is a claim about the collector.
>
> **In run D the banner should read `PASSED WITH OMISSIONS`, not `PASSED`.** That is the check.
> The offline harness now asserts it too, and was verified to fail on the old code.
>
> ⚠ **C1 added a second fix to the same build** — a refusal now writes an amber `NOTHING EXPORTED`
> banner instead of leaving the dialog on `booting…`. So `make ed` once more before C2/D.

**Actual cost: one session, ~25 minutes**, as budgeted — and unlike POC-2's, nothing had to be
re-captured, because this session asked no open questions.

⚠ **Read this first, from the last round:** *budget a re-capture into any session that also asks an
open question.* This session asks none — every question POC-4 had was settled offline — so if
something surprising turns up, the right move is to **stop and send it**, not to work around it.

**Everything here is read-only against designPH data.** Nothing writes to `DesignPH_dict`, nothing
writes to any model. ⚠ **COPIES ONLY** (hard rule 3): runs A, B and D use the copies already in
`~/Desktop/dph_poc_copies/`. Runs C use models you make on the spot and throw away.

---

## Setup

```
cd /Users/em/Desktop/dph_plus_testing/poc && make ed
```

Then **quit and reopen SketchUp 2022** (the extension is only re-read at launch).

Make the output folder:

```
mkdir -p ~/Desktop/dph_poc_copies/POC4
```

Everything you save goes in there, and I collect the lot at the end.

---

## Run A — the real export, end to end ✅ **DONE**

**Result: PASSED WITH OMISSIONS, exactly the expected numbers.** 82/82 faces, 46/46 apertures,
TFA 368.476 m² covered / 0 lost, HBJSON 323,779 bytes. Boot 2573 ms, walk 4180 ms, translate 180 ms.

**And it closed claim (a) outright** — the same extraction translated under CPython 3.11, Chromium
88 and real SketchUp 22.0.353 gives canonical `77a135bffe9375d8` on all three, at 323,779 bytes
each. Any later difference is now attributable to the host or the collector, never the translator.

⚠ **Two things this run corrected in the instructions below** — left in place, struck through, because
a runbook that quietly fixes its own wrong expectations teaches nothing:

- **Adelphi's walk is 4.2 s, not the ~200 ms this file predicted.** It visits **1,023,558** faces —
  8037 unique faces multiplied out by placement. The corpus's "100 ms to 9.7 s" range tracks
  *placements*, and Adelphi is placement-heavy despite being the simplest model in every other
  respect. The 200 ms guess came from assuming "simplest model" meant "fastest walk".
- The banner defect above.

### The original instructions, for the re-run

1. Open `~/Desktop/dph_poc_copies/adelphi-designph_COPY.skp`.
2. **Extensions ▸ DesignPH-PLUS POC ▸ Diagnostics ▸ Save extraction JSON** — tick it. It is off by
   default and this run needs it on: the extraction is what makes the byte-identity claim
   attributable.
3. **Extensions ▸ DesignPH-PLUS POC ▸ Export HBJSON…**
4. The dialog opens and boots (≈3 s). When the save panel appears, navigate to
   `~/Desktop/dph_poc_copies/POC4/` and accept the suggested name.

**What you should see, in order:**

| Where | What |
|---|---|
| Status bar | `DesignPH-PLUS: reading the model… nnn entities`, then clear |
| Dialog banner | green, `PASSED WITH OMISSIONS` |
| Below the banner | a small table — faces / apertures / thermal bridges, each `in / translated / reported` — then a TFA line, then any omissions with reasons |
| Message box | the same headline, the same counts, and the three file paths |
| Folder | `adelphi-designph_COPY.hbjson`, `.report.json`, `.extraction.json` |

**Expected numbers** (from the corpus captures — a mismatch is a finding, not a formality):

```
faces            82 in    82 translated    0 reported
apertures        46 in    46 translated    0 reported
thermal bridges   0 in     0 translated    0 reported
TFA           368.5 m² covered, 0.0 m² lost
```

| What you see | What it means |
|---|---|
| The above | ✅ the run worked. Go to run B |
| `PASSED WITH OMISSIONS` with a non-zero **reported** column | Not necessarily wrong — a reported entity is a *named* one, which is the design. Send the `.report.json` |
| A red `FAILED` banner | Send the message box text and the Ruby Console |
| The dialog opens and never gets past `booting…` | Wait 60 s, then send the Ruby Console. This is the failure mode `SILENT_DIALOG_AFTER` diagnoses |
| The status bar freezes with no count | Note for how long. ~~Adelphi should be ~200 ms~~ → **Adelphi's walk is 4.2 s** (1,023,558 face visits) |
| No table under the banner | Cosmetic but worth knowing — send a screenshot |

⚠ **Do not save the model**, even if SketchUp offers on close.

---

## Run B — the same model again, in a fresh session ✅ **DONE**

**Result: claim (b) closed, byte-identical.** The two extractions match to the byte — 215,373 each,
including `generated_by` (which carries the *build* stamp, not a per-run one, so a single build
gives one string). Nothing in the extraction is per-run at all. Boot 2589 ms, walk 4101 ms,
translate 180 ms — all within noise of run A.

### The original instructions, for the re-run

**`cd poc && make ed`, then quit SketchUp and reopen it.** Then repeat run A exactly, **renaming the
files with a `_run2` suffix** in the save panel (`adelphi-designph_COPY_run2.hbjson`). The folder
does not matter — `~/Desktop/dph_poc_copies/` is fine, the `_run2` name is what keeps them apart.

⚠ **Watch the banner**: it must now say `PASSED WITH OMISSIONS`, matching the message box.

That is the whole run, and it tests something run A cannot: **for the same unedited model, are two
extractions identical?** The contract's path-qualified persistent ids (§2.1) are what make that hold.

⚠ **Run A already went most of the way to answering this, unplanned.** Its extraction is
content-identical to the POC-2 console capture taken hours earlier in a different session — every
field but `generated_by`, which carries a build stamp by design. So the same model, two sessions
*and* two different code paths (the console runner and the wired export) agree on all 82 faces, 46
windows, the libraries, the tables and the unclassified census. Run B narrows it further: same code
path, two sessions.

If the two extractions differ, that is a finding rather than a failure: it means either an id moved
or the live model drifted, and the diff says which.

---

## Run C — the two refusals

Both use models you create and discard. Neither touches a corpus file.

### C1 — a model that is not designPH at all ✅ **DONE**

**Refused correctly**, and found a second defect: the dialog was left reading `booting…` after the
message box was dismissed. Refusals now write an amber `NOTHING EXPORTED` banner too. ⚠ **That fix
is not in your installed build** — `make ed` again before run D if you want to see it; the message
box behaviour is unchanged either way.

#### The original instructions

1. **File ▸ New**. Draw a box. Do nothing else.
2. **Extensions ▸ DesignPH-PLUS POC ▸ Export HBJSON…**

Expect: the dialog opens and boots, then a message box headed
**`DesignPH-PLUS POC: nothing exported`** saying *"This model carries no designPH data at all…"*.
No file is written, nothing hangs.

⚠ It *does* open the dialog first, and that is correct: with no version stamp anywhere, "this is
not a designPH model" cannot be decided until the walk comes back empty.

### C2 — a designPH version this reader will not read ✅ **DONE**

**Refused pre-walk. No dialog opened at all** — which is the actual test. The box named `"3.0.1"`.

#### The original instructions

⚠ **This one does not stamp a model.** The obvious way to test it is to write
`designPH_version = "3.0.1"` into a scratch model's `DesignPH_dict` — and hard rule 2 says never
write to `DesignPH_dict`, full stop. There is no need to bend it: what has to be proved here is
that a 3.x *stamp* produces the refusal, and the refusal reads the stamp through one function.

In the **Ruby Console**, with any model open (a blank one is fine):

```ruby
module DphPlusPoc::Gate
  def self.stamps(_model); ["3.0.1"]; end
end
```

Then **Extensions ▸ DesignPH-PLUS POC ▸ Export HBJSON…**.

Expect: **no dialog opens at all** — that is the point of the check running before the walk — and a
message box naming `"3.0.1"` and saying the reader understands designPH 2.x.

Then put it back (or just restart SketchUp, which is simpler):

```ruby
load "/Users/em/Library/Application Support/SketchUp 2022/SketchUp/Plugins/dph_plus_poc/gate.rb"
```

**Send me the message box text from both.** A refusal that does not say what it saw is the failure
here, not the refusal itself.

---

## Run D — the big one, for the timings ✅ **DONE**

**194/194 faces, 40/40 apertures, 99/99 thermal bridges, TFA 1491.862 m², HBJSON 686,479 bytes.**
Walk **10.9 s** over 2,556,183 face visits; translate 340 ms. Banner read `PASSED WITH OMISSIONS`,
confirming run A's fix in SketchUp.

⛔ **And the answer to the status-bar question: there is nothing to see, and there could not be.**
`Sketchup.status_text=` writes to the bottom-left of the *main SketchUp window* — behind the dialog
— and, more fundamentally, a synchronous main-thread walk repaints nothing at all. See
[`POC-4_results.md`](POC-4_results.md) §6.7.

#### The original instructions

Open `~/Desktop/dph_poc_copies/2414_Bluff Reach_COPY.skp` and export it into
`~/Desktop/dph_poc_copies/POC4/`.

This is the corpus's slowest walk and its only thermal-bridge model. Two things to watch and note:

- **the status bar** — roughly how long it counts for before the dialog takes over. The corpus range
  is 100 ms to 9.7 s and it tracks *placements*, not model size, so this is the model that says
  whether the progress signal was worth building.
- **the counts**: expect `194 faces / 40 apertures / 99 thermal bridges`, TFA 1491.9 m².

Its HBJSON is ~930 KB, the largest in the corpus.

---

## When you are done

Quit SketchUp and tell me. The folder should hold:

```
~/Desktop/dph_poc_copies/POC4/
  adelphi-designph_COPY.hbjson        .report.json        .extraction.json
  adelphi-designph_COPY_run2.hbjson   _run2.report.json   _run2.extraction.json
  2414_Bluff Reach_COPY.hbjson        .report.json        .extraction.json
```

Plus the message box text from C1 and C2, and your note on run D's status bar.

## What happens next (no action from you)

I run three comparisons, and they answer three different questions:

```
sha256  A.hbjson  vs  the same extraction under CPython 3.11 and Chromium 88
        → (a) does the TRANSLATOR behave identically on every host?

diff    A.extraction.json  vs  B.extraction.json
        → (b) does the COLLECTOR produce the same reading twice?

diff    A.extraction.json  vs  the POC-2 fixture captured yesterday
        → has anything drifted since the corpus sweep?
```

Keeping (a) and (b) apart is the whole point. Once (a) holds, any difference SketchUp shows is
attributable to the host or the collector, and never to the translation.
