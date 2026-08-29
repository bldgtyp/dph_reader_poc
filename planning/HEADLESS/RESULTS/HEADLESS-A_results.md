# HEADLESS-A results — SketchUp C SDK feasibility

DATE: 2026-08-28
STATUS: ⛔ **BLOCKED at G0 — PARTIAL PASS on the half that documentation can answer**
PLAN: [`../HEADLESS-A_sdk-feasibility.md`](../HEADLESS-A_sdk-feasibility.md)

---

## Verdict

| | |
|---|---|
| **G0 boot** | ⛔ **BLOCKED — the SDK binary cannot be obtained.** Not a technical failure; a procurement one |
| **G1 glue** — *the decisive gate* | ✅ **YES at the documentation level.** Both directions of the glue query are published. ⚠ Behaviour untested |
| **G2 typed attributes** | ✅ API present · ⚠ behaviour untested |
| **G3 edges at depth** | ✅ API present · ⚠ behaviour untested |
| **G4 Marshal tables** | ✅ API present, incl. the length-aware string reads the NUL-truncation rule demands · ⚠ untested |
| **G5 live vs historical** | ⛔ **Documentation cannot answer this.** Only opening a real model can |
| **G6 net-vs-gross** | ✅ API present · ⛔ the *semantics* question is behavioural and stays open |
| **G7 world transforms** | ✅ API present · ⚠ behaviour untested |
| **G8 version coverage** | ✅ API present · ⛔ whether all 15 corpus files open is behavioural |

**Spike A does not close.** Its gate cannot be evaluated, so **hard rule 7 keeps Spike B shut**.
What *did* close is worth having, and it changes the phase's premise:

> **The SketchUp C SDK is no longer a free public download.** The overview's §2 sentence — "It is a
> free developer download from Trimble" — **is now false**, and the route the whole phase is built
> on has an access gate in front of it that no agent work can open.

---

## 1. The block, measured

Verified **live on 2026-08-28**, in Ed's own Chrome, signed in on his Trimble developer account
(the header showed "Ed M."): `https://extensions.sketchup.com/sketchup-sdk` renders a holding page.

> "Thank you for your interest in the SketchUp and LayOut C SDKs. They are not available for public
> download at this time. Please fill out the form to request access to the SDK or add yourself to a
> list of users we will contact when the SDKs are available again."

with a single **Request Access** button and no download list at all.

Corroborating evidence, in the order it was found:

1. The Extension Warehouse SPA bundle carries a feature toggle named **`SDK_HOLDING_PAGE`** and two
   mutually exclusive components — a real `ClientSdk`/`ArchivedVersions` download table, and the
   holding page above. The toggle is **on in production**.
2. The download API exists and is authenticated: `GET /api/developers/sdkBuilds` → **401
   Unauthorized**; `getSdkBuildUrl(id)` returns a signed `download_url`. So there is no static URL
   to guess — the download was always dynamically signed.
3. ⚠ **`extensions.sketchup.com` returns HTTP 200 with an identical 4387-byte SPA shell for every
   path, including nonsense ones.** Status-code probing against that host proves nothing. This
   invalidated the first round of URL probing in this session and is recorded so it is not repeated.
   (The doxygen docs under `/developers/sketchup_c_api/` are a *different* handler and do serve real
   content — 50 KB pages — which is how §2 below was possible.)
4. Wayback CDX holds URLs shaped `SDK_Mac_2019-0-752.zip`, so that naming convention was real — but
   every archived "capture" is the same ~1 KB SPA stub, not a file. Even the 2015 Drupal-era page
   only ever exposed a login-gated link. **There is no evidence a fetchable static SDK URL ever
   existed.**
5. No package manager ships it: Homebrew, conda-forge, vcpkg and Debian all return nothing
   (checked via their own APIs, not by search-result summary).

**Timeline and turnaround**, from the SketchUp developer forum thread *"SketchUp C SDK 2026 macOS
unavailable"* (`forums.sketchup.com/t/.../346672`) — ⚠ *reported, not independently verified here*:
the SDK went down before 2026-05-05; SketchUp staff described it as maintenance plus a new access
form intended to "understand more about who is using the C SDK and how they are using it"; the form
worked by 2026-05-14; **as of 2026-08-16 multiple developers report no response at all**, and there
is no stated SLA and no confirmation email.

### 1.1 The one route that exists, and why it is Ed's call and not an agent's

A **universal2 (arm64 + x86_64) `SketchUpAPI.framework`, with the complete public C header tree**,
is downloadable today, unauthenticated, from a third-party GitHub release: the Blender importer
`martijnberger/pyslapi`, release `0.24` (`sketchup_importer_0.24_macOS.zip`, 36 MB, HTTP 200). The
framework was built ~April 2025 (Xcode 15.4, `LSMinimumSystemVersion 11.7`) against a
SketchUp-2024/2025-generation API, and the repo claims it reads files up to SketchUp 2025.1.

⚠ **It is a personal re-host of Trimble's proprietary, EULA-gated binary — not an authorized
mirror.** Using it would mean acquiring, for a commercial service, the exact artifact Trimble has
just put behind an access form, from someone who has no right to redistribute it. That is the
opposite posture from the one this phase chose the SDK route *for*
(overview §2: "for a commercial service, Trimble's blessed API is the right legal posture"), and it
runs directly into licensing task **L1**, which cannot even start because the EULA ships with the
download nobody can get.

**This is a licensing decision, so it is not made here.** See §5.

⚠ Note the RedHaloStudio fork everyone links first is **Windows-only** in every current release —
its macOS assets are gone. The working macOS build is on the *upstream* repo it forked from. The
plan's §2 demotion of pyslapi ("pinned to an older SDK generation") is **half wrong**: the *binding*
is stale, but the *framework it ships* is a 2025-generation build, newer than every corpus writer.

---

## 2. What was closed anyway: the API surface (G1's decisive half)

**The reference documentation is still fully public** even though the binary is not, at
`https://extensions.sketchup.com/developers/sketchup_c_api/sketchup/`. That constrains the "does the
API *expose* this at all?" half of six gates without any binary — this repo's own rule (*ask what
the data already on hand constrains before booking the run you cannot get*) pointed at a blocker.

`planning/spikes/headless/a1_capi_surface.py` harvests all **1231 published `SU*` functions** across
89 struct pages plus the free-function headers, and checks them per gate. **Every function every
gate needs is present.** The ones that matter:

| Gate | Function | Note |
|---|---|---|
| **G1** | `SUComponentInstanceGetAttachedToDrawingElements` + `…GetNum…` | ✅ **the decisive one — instance → host.** `@since SketchUp 2018, API 6.0` |
| **G1** | `SUComponentInstanceGetAttachedInstances` | ⚠ points the *other* way; do not confuse the two |
| **G1** | `SUFaceGetOpenings` / `SUFaceGetNumOpenings` / `SUOpeningGetPoints` | the host-side cross-check exists too |
| **G3** | `SUEntityGetPersistentID` **and** `SUEntityGetID` | ★ **both id flavours the contract emits** — see §3 |
| **G4** | `SUStringGetUTF8Length` + `SUStringGetUTF8` | the length-aware read the NUL-truncation rule requires |
| **G6** | `SUFaceGetArea`, `SUFaceGetAreaWithTransform` | the second was not in the plan and matters for scaled instances |
| **G7** | `SUComponentInstanceGetTransform`, `SUGroupGetTransform`, `SUTransformationMultiply` | ⚠ `SUGroupGetTransform` is separate — a face-and-instance-only walk would miss group nesting |
| **G0** | `SUInitialize`, `SUTerminate`, `SUGetAPIVersion` | free functions in `initialize.h`, **not** on any struct |

⚠ **`SUModelGetVersionString` does not exist.** G8 must read `SUModelGetVersion` (an enum,
`SUModelVersion`) and/or `SUModelGetStatistics`; the plan's "record `SUModelGetVersion` or
equivalent" is satisfied, but only by the enum, which is a coarser answer than a version string.

⚠ **Stated limit on this evidence.** This is a *documentation* answer. It says the names exist and
what they claim to do. It says nothing about G5 (live vs historical), nothing about G6's actual
net-or-gross semantics, and nothing about whether the glue query returns 239 hosts on real designPH
models. Those four remain exactly as open as they were.

---

## 3. What the fixtures were made to say (and two things the docs had wrong)

`planning/spikes/headless/a0_expected_answers.py` re-derives every gate's *expected* answer from the
five live captures and the offline baseline, because the plan states them in prose from memory. It
paid for itself immediately.

**Confirmed unchanged**: 545 classified faces · 239 windows · 99 edges · `glued_to` resolves
**239/239** · Bluff Reach is the only model with edges · Linde carries 25 `layer_table_*` · the
version stamps (2.1.15 / 2.2.24 / 2.2.29).

### 3.1 ★ The counting basis is now mechanical instead of remembered

The contract-v2 `id` is built by `collector.rb:597` as
`([kind] + path_of_persistent_ids + [own_persistent_id]).join("_")`, and
`test_collector.rb:221` pins the two-placement case to `%w[face_50_51 face_52_51]`. Therefore:

- **the whole path-qualified id is the PLACEMENT identity**
- **the leaf segment is the ENTITY identity** (`persistent_id`)

So `counts.faces_tagged` is a **placements** count, and deduplicating on the leaf gives the entity
count — **2466 → 1791** on Linde and **2456 → 1781** on 250708, where 1781 is the offline baseline
exactly. ⚠ **Adelphi and Bluff Reach mask this completely** (nothing in either is placed twice),
which is why the POC's reconciler could conflate the two for as long as it did. The distinction no
longer needs to be remembered — it is one `rsplit`.

⚠ **And `entity_id` in the contract is `entity.entityID`, which is session-local — not
`persistent_id`.** It must never be compared across captures. **Spike B's identity gate has to key
on the path-qualified `id`, not on `entity_id`.** ★ `SUEntityGetPersistentID` exists in the C API,
so a headless reader *can* reproduce the same ids — which is the single most encouraging thing found
this session for Spike B.

### 3.2 The reconciliation that is exact on all five models

The one claim well defined on both sides:

> live classified **faces** + live tagged **edges** == offline integer-valued area groups

Bluff Reach **194 + 99 = 293** ✓ · Wellington 103 ✓ · Linde 74 ✓ · 250708 92 ✓ · Adelphi 82 ✓.
The offline number is **entity-type-blind** (the binary parser sees records, not entity classes),
which is precisely why the POC's reconciler read it as a 576-vs-194 contradiction. There is **no
well-defined offline "total tagged entities"** to compare against — the baseline reports totals per
*key*, not a union over entities — so `a0` deliberately reports only the exact figure rather than
manufacturing a union that would merely look rigorous.

### 3.3 Two documentation defects found and fixed

1. ⛔ **`00_Context/DATA_CONTRACTS.md` §2.1 carried the wrong coalesce key.** It read
   `dict["areaGroupID"] || dict["areaGroupIDAuto"]`. **`areaGroupIDAuto` does not exist.** The real
   fallback is `areaGroupAuto` — no `ID` — while `assemblyIDAuto` keeps it. This is the *same typo*
   the Phase 3 spike shipped (POC-2 finding 50), still standing in the foundation layer ten days
   after the POC recorded it. Adelphi masks it; Linde is the model that needs both keys (66 + 8 =
   its 74 classified faces). **Fixed**, with all three pairs spelled out and the asymmetry called
   out explicitly.
2. **The `loops.size > 1` trap is worse than recorded.** `AGENTS.md`, `CLAUDE.md` and
   `CONSTRAINTS.md` §4 all say it is true on "**2 of 16**" real Adelphi hosts. Measured from the
   capture: **1 of 16** — and **1 of 81** across all five models' distinct hosts. The correction
   makes the warning stronger, not weaker. *(Not yet propagated — see §6.)*

### 3.4 Smaller things worth keeping

- **Wellington's capture self-reports `model.file_name` as `"2523 Weiilington"`** — the *backup's*
  misspelling, and the only one of the five without the `_COPY` suffix — while its data matches the
  Wellington row. This is `Sketchup::Model#path`'s documented untrustworthiness (CONSTRAINTS §9)
  surfacing in the name field. **Spike B must key captures on the file, never on `model.file_name`.**
- **New corpus material exists that postdates the Phase-0 baseline**: `2618 {BP} Lavoie
  Certification.skp` + backup, **146 MB each**, saved 2026-08-28 — ~13× the largest baselined model.
  It can grade nothing (no baseline, no live capture) but it is the natural scale probe once a
  reader exists.

---

## 4. Deliverables produced

| Artifact | State |
|---|---|
| `planning/spikes/headless/a0_expected_answers.py` | ✅ runs; all 5 cross-checks agree |
| `planning/spikes/headless/a1_capi_surface.py` | ✅ runs; all gates covered, verdict `ALL GATES COVERED` |
| `planning/spikes/headless/_private/` + `MANIFEST.md` | ✅ staged — 15 corpus `.skp` **copies**, the 5 live captures, the offline baselines. Gitignored, hash-manifested |
| `00_Context/DATA_CONTRACTS.md` §2.1 | ✅ corrected (§3.3 item 1) |
| G0–G8 behavioural results | ⛔ not produced — blocked |
| SDK EULA (task L1) | ⛔ not obtainable — it ships with the download |

---

## 5. ⛔ The decision this spike cannot make

Spike A cannot proceed without a macOS SDK binary, and there are exactly three ways to get one.
**All three are Ed's call**, and two of them are not technical:

| Route | What it costs | What it risks |
|---|---|---|
| **A. Request Access** via Trimble's form | Ed fills one form; then waiting | Public reports say **no response in ~3 months**. Correct posture, unknown and possibly infinite latency |
| **B. Third-party re-host** (`martijnberger/pyslapi` 0.24 macOS) | One download, works today, universal2 + full headers | ⚠ **Personal redistribution of a proprietary EULA-gated binary.** Directly contradicts why the SDK route was chosen. L1 cannot be satisfied — the EULA is inside the download nobody can get |
| **C. Abandon the SDK premise** | — | Reopens the overview §2 decision. The alternatives it ruled out (grow the offline binary parser; a from-scratch `.skp` parser such as npm `openskp`) were ruled out on *technical* grounds that still stand, but "the blessed API" is no longer freely available, which was half the argument |

⚠ **Route B for a `.skp`-reading *spike on the laptop* and route B for a *shipped commercial
service* are different questions with different answers.** A time-boxed feasibility spike against a
third-party build might be defensible where shipping on it is not — but that is a judgment about
Trimble's EULA, which nobody in this session has read, because it is inside the gated download.

---

## 6. Follow-on work, explicitly not done

1. **Propagate the `1 of 16` correction** (§3.3 item 2) into `AGENTS.md`, `CLAUDE.md` and
   `00_Context/CONSTRAINTS.md` §4. Left undone deliberately: those three files state it identically,
   and a single consistent edit is better made in one pass than mid-block.
2. **Rewrite overview §2's "free developer download"** sentence. It is now false.
3. **L1 remains unstartable.** L2 (AGPL §13) and L3 (designPH posture) are unaffected.
4. **Spike B stays shut** (hard rule 7). Its H0 revision pass should fold in §3.1 — the identity gate
   must key on the path-qualified `id`, never on `entity_id`.

---

## Changelog

- 2026-08-28 — written. Spike A blocked at G0 on SDK availability; the documentation-answerable half
  of G1–G4/G6–G8 closed; expected-answer derivation and evidence staging completed; two
  documentation defects found, one fixed.
