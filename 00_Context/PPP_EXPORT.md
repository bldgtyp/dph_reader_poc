# The `.ppp` Export — What We Know, and the Line We Drew

designPH's own export format, the file a consultant hands to PHPP. **We do not parse it, and this
document deliberately stops short of describing how it works.**

> ✅ **The format is now cataloged elsewhere, and the line below still holds.** 2026-08-19: the
> `.ppp` turns out to be a transfer file addressed to **PHPP's own named-range namespace** — every
> section name is a PHPP defined name, every declared `rows,cols` is that range's shape (verified
> 74/74 against `PHPP_EN_V10.6_Empty.xlsx`; the one exception is designPH's own header block).
> So the format is readable off a workbook BLDGTYP licenses, with nothing inferred about designPH.
>
> Full catalog: `bldgtyp/phi-rules` → `rulesets/designph-2x-r1/ppp/`, via the **`phi-rules` skill**.
>
> **This changes nothing about hard rule 1.** Writing a `.ppp` *writer* was always fine — PHX ships
> one. Writing a **parser** to extract a designPH model is what §2.4(a) reaches, and it stays out of
> scope for DesignPH-PLUS. See `ppp/D09` §4, which was written from this document's reasoning.

---

## 1. The rule

> **Hard rule 1: Never parse the `.ppp` export.** Reading it *by eye* for reference is fine; writing
> a parser is not.

The [designPH Licence Agreement](https://database.passivehouse.com/en/designph/licence-agreement/)
**§2.4(a)** prohibits attempts to "reconstruct or discover any source code, underlying ideas,
algorithms, **file formats or programming interfaces**." On a plain reading, writing a `.ppp` parser
is reverse-engineering a file format, named explicitly.

**§2.4(d)** permits derivative works "expressly authorized **in writing**", so PHI *can* authorise
`.ppp` access. That is a v2 conversation and is staged as Phase 5 (`planning/PHASE-5_phi-and-licence.md`).

## 2. Why this document exists at all

To stop the question being reopened. Someone will eventually notice that the `.ppp` contains
everything designPH knows — including the shading factors v1 omits — and reach for it. The answer is
already decided, and the reasoning is here so it does not have to be rediscovered or re-argued.

## 3. What is recorded, and why only this much

Observed by opening the file, which the rule permits. Nothing here required analysis, and nothing
here is enough to build on.

`_adephi_st_example_files/adelphi-designph_PHPP10.ppp`, 157,764 bytes:

- It is **text, UTF-16LE encoded**, not a binary container.
- It opens with a metadata block whose first data line is a **version banner** naming the exporting
  designPH build, the SketchUp version, and the platform.

That banner is the one genuinely useful fact, because it is how you tell which tool wrote a given
export — see §4.

**No structure, no field semantics, and no record layout is documented here, by policy.** If a
future authorised effort needs that, it starts from PHI's written permission, not from this file.

## 4. ⚠ Corpus caveat — the Adelphi `.ppp` and `.skp` are from different designPH versions

The banner in `adelphi-designph_PHPP10.ppp` reads:

```
designPH 2.4.0 BETA PRO | SketchUp 22.0.353 | arm64-darwin20
```

But `adelphi-designph.skp` beside it is stamped **2.1.15**.

So the export was produced by a **much newer designPH** than the one that last saved the model. This
matters whenever the `.ppp` is used to cross-check expectations: the two files are not two views of
one tool's output. It is consistent with the standing warning that the corpus formats are **only
approximately aligned** — a mismatch between them is not by itself evidence of a bug.

✅ **Now measured rather than warned about** (2026-08-21). The PHPP that came from this `.ppp` and
the `.skp` beside it **do not share an id space**: the same three constructions are `83ud`/`84ud`/
`85ud` in the model and `01ud`/`07ud`/`13ud` in the export, and only **3 of 14** in-model assemblies
have a name that appears on the PHPP side at all. Two of the three agree on U-value within 0.003
W/m²K; the third differs by 0.031, and the difference is explained on the PHPP side.

**Practical rule: join designPH data to PHPP data by NAME, never by id, and treat the PHPP as ground
truth for arithmetic and method rather than for identity.** That is exactly how it earned its keep —
the ISO 6946 multi-section derivation was checked against it (`DATA_CONTRACTS.md` §6.1). Being clear
about which kind of ground truth it is, is what stops an alignment artefact reading as a bug.

## 5. What we use instead

| Question | Where the answer comes from |
|---|---|
| What designPH stores about a face | `DesignPH_dict` in the user's own `.skp`, via Trimble's public API |
| Ground-truth areas, U-values, TFA | `adelphi-phpp.xlsm` — the PHPP itself |
| What a finished PHPP looks like | The `phi-rules` skill's per-worksheet cell map |
| Shading factors | **Nothing.** Omitted from v1 and explicitly marked `shading: not-computed` |

Reading `DesignPH_dict` is the defensible path: the data sits in the user's own `.skp` — SketchUp's
format, not designPH's — and is read through Trimble's public, documented Ruby API. That distinction
is the whole legal footing of the project, and it is why the `.ppp` line matters.

### 5.1 What the POC changed about the pressure on this rule

*(2026-08-21, POC-4 closed.)* §2 predicts that someone will eventually reach for the `.ppp` because
it "contains everything designPH knows". That is still true, but the gap it would close is now
measured rather than imagined, and it is **narrow**:

| | From `DesignPH_dict`, today | Only in the `.ppp` |
|---|---|---|
| Classified faces | **545 of 545** across the corpus | — |
| Apertures | **239 of 239**, hosts resolved | — |
| Thermal bridges | **99 of 99**, psi values from `connections_ud` | — |
| TFA | derived, 368.5 / 1491.9 / 448.2 m² | — |
| Assembly U-values | matched to designPH's own calculator, worst Δ **0.0005 W/m²K** | — |
| Frame / glazing constructions | ✅ in the model, in `frames_ud` / `glazing_ud` (§7.0.1) — on 3 of 5 models | the other 2 |
| **Shading factors** | **nothing** | ⚠ **yes — this is the real gap** |

So the honest statement of the temptation is not "the `.ppp` has everything" but **"the `.ppp` has
the shading factors, and a designPH-quality shading calculation is genuinely hard to reproduce"**.
That is a smaller and much better-defined reason to want it, and it is the one to put in front of
PHI in Phase 5 — a specific ask beats a general one.

⚠ It does **not** weaken hard rule 1 by one inch. A narrower motive is still a motive, and §2.4(a)
does not care how much of the file you wanted.

## 6. Where the `.ppp` still appears

- **`PHX.to_PPP`** — our own stack *writes* a `.ppp`-shaped output, and Phase 2 found it pure and
  reachable. Writing a format is not reverse-engineering one, but the distinction is worth stating
  before anyone conflates them.
- **Phase 4 §4.4** reads the version banner of a designPH 3.0 export — **by eye, no parser** — to
  confirm what the new version stamps.
- **Phase 5** may seek written authorisation under §2.4(d).

## 7. Not settled

The licence carries the standard carve-out for what applicable law protects. EU Software Directive
2009/24/EC Art. 6 permits decompilation **for interoperability**, and PHI is German — but whether
that reaches a US developer depends on governing law. **Unresolved, and for counsel** (PRD §9).

That question is separate from, and must not be conflated with, the AGPL question about our own
vendored dependencies (`planning/RESULTS/PHASE-3_licence-question.md` §6).
