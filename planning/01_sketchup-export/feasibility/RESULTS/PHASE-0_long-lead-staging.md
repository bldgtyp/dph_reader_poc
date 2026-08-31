# Long leads, staged for Ed

Both items are **Ed's to execute**. The agent's job was to stage them: draft the opener, list what
the purchase needs, name the decisions. Nothing here has been sent, bought, or committed.

## ⏸ Deferred — fire each at its own phase (Ed, 2026-08-19)

| Item | Fires at | Section here |
|---|---|---|
| designPH 3.0 licence | ⛔ **ON HOLD — cannot be bought yet** (Ed, 2026-08-21). Not a scheduling choice | [§A](#a-designph-30-licence) |
| PHI opener | **Phase 5 §5.0**, day one | [§B](#b-the-phi-conversation--opener) |

Phase 0 originally started both so their latency would run in the background. Ed's call moves them to
their evaluation phases; work proceeds up to those boundaries. **The tradeoff:** the 1–3 week
procurement wait and the open-ended PHI reply wait are now on the critical path rather than off it.
Budget for them there.

Everything below stays valid and ready to fire — the point of staging was that neither phase should
have to start by drafting anything.

---

## A. designPH 3.0 licence

> ### ⛔ ON HOLD — **the 3.0 licence cannot be bought yet** (Ed, 2026-08-21)
>
> This is a **procurement constraint, not a scheduling preference**, and it does not expire when
> Phase 4 starts. Nothing anywhere in this repo should plan, budget, or wait on acquiring designPH
> 3.0 until Ed says otherwise. ⚠ Phase 4 is therefore blocked on something no amount of agent work
> can unblock — do not propose starting it.
>
> **What is unaffected**, and deliberately so: the POC's version gate *refuses* a 3.x stamp and
> names it (`pocs/01_sketchup-export/ext/dph_plus_poc/gate.rb`). That costs nothing, needs no licence, and is tested
> against a synthetic stamp — a reader that meets a 3.0 model in the wild must say so rather than
> half-read it, whether or not we own a copy.

**Fires:** [Phase 4](../PHASE-4_designph-3-compat.md) §4.0, day one — whether v1 can serve the market
that actually exists. Realistically 1–3 weeks from order to working install, and that wait is now
inside Phase 4.

### Why it is the first action of Phase 4, not a later one

Phase 4 asks whether designPH 3.0 broke our reader. Every model in the corpus is 2.1.10–2.2.29, and
the only 2.4-generation sample is a BETA test file with six faces. **The corpus contains no 3.0 data
at all**, and 3.0 is what the market runs. designPH already renamed its face keys once, at 2.2 — a
schema change at 3.0 is a live possibility, not a hypothetical.

### Checklist

- [ ] Order designPH 3.0 — PHI's shop at <https://designph.org> / the PHI component database store.
- [ ] Confirm what the licence is keyed to (machine, dongle, or PHI account) and whether it can run
      **alongside** the existing installs.
- [ ] **Keep 2.2.29 and the 2.4.0 BETA installed.** Version spread is the asset here — a machine that
      can open the same model in three generations is what makes Phase 4 cheap. Do not let an
      installer silently upgrade them.
- [ ] Confirm SketchUp-version compatibility. This environment is SketchUp 2022 / Ruby 2.7; if 3.0
      requires a newer SketchUp, that is a Phase 4 finding in itself and needs recording.
- [ ] On arrival: open one corpus copy (**a copy** — hard rule 3, never a corpus original) in 3.0,
      save under a new name, and re-run the Phase 0 baseline against it. A key-name diff against
      [`PHASE-0_corpus-baseline.md`](PHASE-0_corpus-baseline.md) is Phase 4's first data point.

### Open question for Ed

Is there a PHI/designPH **beta or partner channel** worth asking about at the same time? Early access
to schema changes would convert Phase 4 from reactive testing into something maintainable, and it is
a natural thing to raise alongside a purchase.

---

## B. The PHI conversation — opener

**Fires:** [Phase 5](../PHASE-5_phi-and-licence.md) §5.0, day one — the only existential risk in the
plan. Every technical obstacle found so far has a workaround; *"PHI actively objects"* does not.

### ⚠ Read this before sending — the deferral changed what this draft should be

The draft below was written for a **Phase 0** send: cold, with nothing built yet. Phase 0 and Phase 5
pulled in different directions —

- **Phase 0** wanted the conversation *opened* immediately, because relationships have weeks of latency.
- **Phase 5** says *"show a working HBJSON in ph-navigator before requesting anything."*

— and the draft resolves that by carrying **no ask at all**: it introduces the work and opens a
channel, with nothing in it to say no to.

**Sending it from Phase 5 instead removes the tension entirely, and the draft should be revised to
take advantage.** By then there is a working HBJSON, so the opener can lead with a demonstration
rather than an abstract heads-up — which is what §5.1 wanted in the first place. Concretely: keep the
introduction and the `dPH+` prior art, replace *"I'd just like you to know it's coming"* with an
actual offer to show it, and still keep the two asks (comfort on §2.4(a), written §2.4(d)
authorisation for `.ppp` access) **out of first contact**. Those belong to the conversation that
follows, not the message that starts it.

### Before sending

- [ ] Confirm the right recipient. designPH is PHI's product; the useful contact is whoever owns it
      rather than a general inbox. If there is an existing relationship from certification work or
      from the `dPH+ Rooms` / `dPH+ Windows` era, use it — a warm introduction is worth more than a
      cold one, and slower is fine.
- [ ] Decide whether to mention `dPH+ Rooms` and `dPH+ Windows` by name. **Recommend yes.** They are
      public prior art for the companion-not-competitor pattern, PHI never objected, and raising them
      unprompted is much stronger than having them surface later.
- [ ] **Do not** present the legal reading. Counsel's view on §2.4(a) and on EU Software Directive
      2009/24/EC Art. 6 is for our own posture (PRD §9), not for this conversation. Leading with a
      legal argument turns a collaboration into a negotiation.

### Draft — for Ed's review, not to send as-is
*(Written for a cold Phase 0 send. Revise per the note above before sending it from Phase 5.)*

> **Subject:** designPH → open data, a companion tool we're building
>
> Hello [name],
>
> I'm Ed May, co-founder of BLDGTYP in Brooklyn — we're a two-person Passive House consultancy and
> have been certifying to PHI since 2010. designPH is where most of our envelope modelling starts.
>
> I wanted to give you a heads-up on something we're building, well before it's finished, because
> it touches designPH and I'd rather you heard it from me first.
>
> It's a free, open-source SketchUp extension that reads a designPH model and writes HBJSON — the
> Honeybee/Ladybug interchange format. Everything it reads comes out of the user's own `.skp`
> through Trimble's public SketchUp API. It does not touch the `.ppp` export, and it does not write
> the envelope to PHPP — that stays designPH's job, unchanged.
>
> What it opens up is the downstream side: once a designPH model is in a standard format, it can be
> viewed in a browser, checked by QA tooling, handed to a certifier as structured data, or pushed
> into a reporting pipeline. Today that work gets redone by hand in Rhino or entered twice. For us,
> the practical effect is that designPH becomes the starting point for more of our projects rather
> than fewer — every user of this is a designPH user.
>
> We've done a smaller version of this before: `dPH+ Rooms` and `dPH+ Windows`, two little companion
> extensions we published a few years back, one of them with Sustainable Engineering in New Zealand.
> Same spirit, much smaller scope.
>
> I'm not asking for anything at this stage. I'd just like you to know it's coming, and I'd rather
> build it in a way that works for you than find out later that it doesn't. When there's something
> running I'd be glad to show it to you — and if any of it looks like something designPH should
> simply do itself, that's a good outcome as far as I'm concerned, and I'll say so.
>
> Happy to talk any time.
>
> Ed

### What to listen for in the reply

The reply is Phase 5's first data point. Log it in `PHASE-5_results.md` when that phase runs, and
read it against the outcome table in
[`PHASE-5_phi-and-licence.md`](../PHASE-5_phi-and-licence.md) §5.1:

| Signal | Reading |
|---|---|
| Curiosity, questions about the format, "show us" | **Enthusiastic.** Bring the §2.4(d) ask forward |
| Polite acknowledgement, no engagement | **Neutral.** Proceed as planned; v2 shading stays blocked |
| Questions about scope, competition, or what else it will do | **Concerned.** Re-emphasise complementarity before asking for anything |
| Points at the licence agreement | **Objects.** Stop. Do not route around it — PRD §9 is explicit that this is the one true deal-breaker |

Silence is not a signal. Follow up once, then treat it as Neutral.
