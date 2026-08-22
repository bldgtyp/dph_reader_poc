# Phase 5 — PHI Relationship and Licence Decision (S6)

> ⏸ **TABLED (Ed, 2026-08-19).** The PHI opener has not been sent. The POC completed on the recorded working assumption that PHI will agree, and "something working to show" now exists — this phase is the natural first *external* move of any V-0 effort. Drafts: [`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md).

**Box:** weeks of calendar time, hours of work
**Gate:** the only existential risk in the project
**Prerequisite:** ideally something working to show

---

## 5.0 — Send the PHI opener **[Ed]** — do this the day Phase 5 opens

Originally a Phase 0 background item; **deferred here by Ed on 2026-08-19.** The reply latency is now
on this phase's critical path, so sending is the *first* action of Phase 5.

The deferral has one genuine upside worth naming: Phase 0's staging doc had to write the opener with
**no ask at all**, precisely because Phase 5 wants something working shown first and Phase 0 would
have been sending it cold. Opening the conversation *here* removes that tension — by now there is a
working HBJSON to show, so the opener can lead with a demonstration rather than an abstract heads-up,
which is what §5.1 wanted all along.

The draft is written and ready:
[`RESULTS/PHASE-0_long-lead-staging.md`](RESULTS/PHASE-0_long-lead-staging.md) §B — recipient
checklist, the drafted text, and a table for reading the reply. **Revise it to lead with the working
demo before sending**, and keep the two asks (§5.1) out of first contact regardless.

## Objective

Two outcomes: (1) know where PHI stands, and (2) decide what licence DesignPH-PLUS ships under.

Every technical obstacle found so far has a workaround. **"PHI actively objects" does not.**

## 5.1 — The PHI conversation

### Position

Per PRD §9 and §14. Complementary, not competitive:

- designPH's core value is 3D authoring plus the shading calculation. **We replace neither.**
- v1 does not write the envelope to PHPP. That stays designPH's job, unchanged.
- v1 does not parse the `.ppp`. We read `DesignPH_dict` from the user's own `.skp`, through Trimble's
  public documented API — SketchUp's format, not designPH's.
- We are free and open-source. Every DesignPH-PLUS user is a designPH user; **this sells licences.**
- If PHI wants to absorb the mechanical-authoring idea into designPH proper, that is a good outcome
  and we will say so.
- **Precedent: BLDGTYP has done this before, publicly, without objection.** Two small designPH
  companion extensions — `dPH+ Rooms` (~2021) and `dPH+ Windows` (co-developed with Sustainable
  Engineering Ltd NZ, written up on Passive House Accelerator) — sit at
  `~/Dropbox/bldgtyp-00/00_PH_Tools/design-ph-plus/`. Bring them to the conversation: the
  companion-not-competitor pattern already exists and PHI never pushed back on it.

**Lead with what it unlocks for designPH, not with an ask.** Show a working HBJSON in ph-navigator
before requesting anything.

### The two asks

1. **Comfort** that reading `DesignPH_dict` via the public SketchUp API is not considered a §2.4(a)
   issue. This is not strictly needed — it is a defensible reading — but having it removes the risk
   entirely and costs nothing to request.
2. **Written authorisation under §2.4(d)** to read the `.ppp` export, for shading in v2. This is the
   valuable one, and it is exactly the carve-out the clause provides for.

### Preparation

- Have counsel's read on §2.4(a) and on whether EU Software Directive 2009/24/EC Art. 6
  (decompilation for interoperability) reaches a US developer under this agreement's governing law.
  **Do not** present a legal argument to PHI — this is for our own posture, not the conversation.
- Bring Phase 4's findings. If 3.0 changed the schema, "a supported interface would help us both" is
  a much stronger opening than an abstract request.

### Outcomes

| Outcome | Consequence |
|---|---|
| **Enthusiastic** — wants to collaborate | Best case. Ask about a supported data interface; consider co-announcing |
| **Neutral** — no objection, no help | Proceed as planned. v2 shading stays blocked; revisit later |
| **Concerned** — worried about competition | Re-emphasise complementarity; offer to constrain scope in writing; consider giving PHI right of first refusal on the authoring feature |
| **Objects** | **Stop and reassess.** Not a technical problem and not one to route around. Options: negotiate, narrow to `.skp`-only with explicit blessing, or abandon |

## 5.2 — The licence decision

Deferred from PRD §23 until Phase 3 settled the runtime. Now decidable.

**If Phase 3 PASSED (Pyodide):** we vendor `honeybee-core`, which is **AGPL-3.0**. Our own
`honeybee_ph` and `PHX` are GPL-3.0. The extension must therefore be AGPL-3.0.

**The consequence to think through is v3, not v1.** AGPL §13's network clause covers *modified*
versions offered over a network; using unmodified honeybee as a library in a hosted service is a
different situation from conveying a combined work. Which one the hosted viewer/QA/reporting product
lands in is genuinely unclear and **is worth an hour of counsel's time before v1 ships**, not after —
by then the architecture is expensive to change.

**If Phase 3 FAILED (Ruby writer):** we link nothing. File formats are not copyrightable, so the
licence is a free choice and the hosted products are unconstrained. Recommend GPL-3.0 anyway for
consistency with the rest of PH-Tools and because the ecosystem-standard ambition (PRD §12) is better
served by copyleft than by permissive — but this is now a preference rather than an obligation.

## Gate

**PASS** — PHI is neutral or better, and the licence is chosen with its v3 implications understood.
v1 implementation proceeds.

**PASS WITH CHANGES** — PHI has conditions. Record them in the PRD as constraints, not footnotes.

**FAIL** — PHI objects. Stop. Reassess with Ed and John before any further work.

## Deliverables

- `planning/RESULTS/PHASE-5_results.md` — what PHI said, verbatim where possible
- A licence decision recorded in the PRD, with reasoning
- Counsel's read on the AGPL/v3 question, if Pyodide was adopted
- If PHI is positive: a written note of what was agreed, so it survives staff changes on both sides
