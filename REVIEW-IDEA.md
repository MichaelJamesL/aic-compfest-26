# Idea Review Guideline

How to review a product/feature idea in this repo. Posture: **senior partner at
McKinsey** running a pre-read on a client proposal. Not a cheerleader, not a
troll. The job is to find the one or two things that decide whether this wins,
say them first, and back them with evidence.

## 0. Reviewer posture

- **Answer first.** Open with the verdict and the top 3 issues. Never make the
  reader wade through analysis to find the recommendation.
- **So what?** Every observation must end in a consequence. "The market has 5
  competitors" is not a finding. "Three incumbents already ship our Primary FR
  list, so our wedge has to be X" is.
- **MECE.** Issues are grouped, non-overlapping, and cover the space. If two
  findings are the same finding, merge them.
- **Evidence or flag it.** Any number, competitor claim, or market assertion
  carries a source, or is explicitly marked `[ASSUMPTION]`. Fabricated
  precision is the fastest way to lose the room.
- **Disagree and commit.** Once a call is made, stop re-litigating; convert
  remaining doubts into risks with owners and triggers.

Inputs to collect before starting: the idea write-up, the competition/spec
guideline (default here: `docs/FR.md` + `AGENTS.MD`), the judging criteria,
the deadline, and the team's actual capacity.

---

## Phase 1 — Frame

Goal: agree on what is actually being proposed before judging it.

- Restate the idea in **one sentence**: *for [user] who [pain], this is a
  [category] that [benefit], unlike [alternative]*. If it can't be restated in
  one sentence, that is finding #1.
- Name the **decision** the review serves: build / cut / reshape / defer.
- Fix the **scope of judgment**: hackathon deliverable, or real product? The
  bar differs and mixing them produces mush.
- List **what would have to be true** for this idea to win. Those become the
  hypotheses the rest of the phases test.

Exit: one-sentence idea, decision named, 3–5 must-be-true hypotheses.

## Phase 2 — Spec / competition alignment (hard gate)

Goal: does it satisfy the rules? Failures here outrank everything else — a
brilliant idea that misses a Primary requirement scores zero.

- Build a **coverage table** against the given spec. For this repo, every row
  of `docs/FR.md`:

  | FR | Priority | Covered? | Where | Evidence |
  | --- | --- | --- | --- | --- |

  Status is one of: **Shipped** (demoable today), **Stubbed** (path exists, not
  real), **Planned**, **Missing**.
- **Primary Missing = blocker.** Secondary/tertiary Missing = risk, not blocker.
- Check **non-functional / submission rules** separately: deployment (Docker
  Compose runs from README), documentation, time limits, tech constraints,
  originality/licensing rules.
- Map the idea to the **judging criteria**, weight by weight. Effort spent on
  an unweighted dimension is waste, and should be called out as waste.
- Check **implicit spec intent**, not just the letter — e.g. "cocok untuk
  pabrik menengah" implies low adoption barrier, which is why the
  Starter/Standard/Professional packaging exists. An idea that raises the
  adoption barrier fights the spec even if it ticks every FR box.

Exit: coverage table, blocker list, judging-criteria map.

## Phase 3 — Problem & customer

Goal: is the pain real, and does anyone pay to remove it?

- **Who hurts?** Name the buyer, the user, and the saboteur (whoever loses
  power/budget if this ships). If buyer and user differ, say how the sale works.
- **How bad?** Quantify: downtime hours, cost per hour, frequency, current
  workaround. Mark estimates `[ASSUMPTION]`.
- **What do they do today?** The default competitor is a spreadsheet, a senior
  technician's memory, or nothing. Beating "nothing" needs a change-management
  story, not just a better output.
- **Is the pain urgent or aspirational?** Aspirational pain does not close deals
  and does not impress judges.

Exit: one paragraph on the buyer, one quantified pain statement, the named
status quo.

## Phase 4 — Market & competition

Goal: why does this exist next to what already exists?

- **Landscape map.** Three tiers: incumbents (CMMS/ERP suites), specialists
  (predictive-maintenance point tools), and the DIY/status-quo option. Name real
  products; a landscape with no names is a landscape you didn't research.
- **Positioning axes.** Pick the two axes that actually decide purchase
  (e.g. data-readiness required × depth of reasoning) and plot everyone,
  including us. If we land on top of an incumbent, the idea is undifferentiated.
- **The "why hasn't X done this" question.** Answer it honestly. Valid answers:
  new capability just became cheap, incumbent is structurally conflicted, market
  too small for them. Invalid: "they haven't thought of it."
- **Moat / defensibility.** Rank what we have: data, workflow lock-in,
  integration depth, domain corpus, or nothing but a prompt. Say plainly if the
  answer is "a competitor could clone this in a weekend" — for a hackathon that
  may be acceptable, for a product it isn't.
- **Substitutes and channel.** Who already sits in the customer's stack and
  could bundle this away? How would we reach the buyer at all?

Exit: named landscape, positioning claim in one sentence, honest moat rating
(strong / thin / none).

## Phase 5 — Solution & feasibility

Goal: can this team ship a credible version in the time available?

- **Critical path.** What must work end to end for the demo to be believable?
  Everything else is decoration and should be scheduled last.
- **Riskiest technical assumption.** Name it, and name the cheapest experiment
  that kills or confirms it this week.
- **Trust & correctness.** For AI-shaped ideas: what is deterministic vs.
  generated, how is it evaluated, and what stops a hallucinated number from
  reaching the user? Judges probe exactly here.
- **Capacity check.** Compare remaining scope to remaining person-days, at the
  team's demonstrated velocity, not its optimistic one.
- **Demo-ability.** An unshowable capability scores near zero. If it can't be
  seen in the demo window, either make it visible or cut it.

Exit: critical path, riskiest assumption + experiment, go/no-go on capacity.

## Phase 6 — Value case

Goal: does the math work for the customer and for us?

- **Customer value in their units**: avoided downtime × cost/hour, technician
  hours saved, spare-part carrying cost, scrap avoided. One honest calculation
  beats five vague benefits.
- **Cost to serve**: inference, storage, integration, support. Check that a
  single analysis run costs sane money at target volume.
- **Pricing / packaging fit**: does the tiering map to real willingness to pay
  and real data readiness, or is it decoration?
- **Break-even**: how many machines/plants before this is worth building?

Exit: one quantified value statement with its assumptions listed.

## Phase 7 — Risks & kill criteria

Goal: know in advance what would make us stop.

- Top 5 risks in a 2×2: **impact × likelihood**. Each gets an owner, a
  mitigation, and a **trigger** ("if the eval hit-rate is still <60% by Friday,
  we cut X").
- Separate **fatal** risks (invalidate the idea) from **manageable** ones.
- State the **kill criteria** explicitly. A review with no conditions under
  which the answer becomes "no" is not a review.

Exit: risk table with triggers, explicit kill criteria.

## Phase 8 — Verdict

One page, in this order:

1. **Verdict**: Proceed / Proceed with changes / Reshape / Stop. One line of why.
2. **Top 3 findings**, each: observation → so what → recommended move.
3. **Scorecard** (below).
4. **Next 3 actions**, each with owner and date.
5. **Open questions** — what we could not answer and what evidence would settle it.

---

## Scorecard

Score 1–5, then weight. Anything scoring 1–2 needs a named fix or an accepted
kill.

| Dimension | Weight | What a 5 looks like |
| --- | --- | --- |
| Spec/guideline compliance | 25% | All Primary FRs Shipped, submission rules met, judging criteria mapped |
| Problem severity & buyer clarity | 15% | Named buyer, quantified urgent pain, known status quo |
| Differentiation vs. market | 20% | Named competitors, clear axis where we win, non-trivial moat |
| Feasibility in the timebox | 20% | Critical path already runs end to end; risky assumption tested |
| Value case | 10% | One credible quantified benefit with stated assumptions |
| Demo/narrative strength | 10% | The win is visible in 5 minutes without narration crutches |

Rule of thumb: **any Primary FR Missing caps the total at "Proceed with
changes" at best**, regardless of the other scores.

---

## Red flags (call these out by name)

- Idea can't be stated in one sentence.
- Competitor section with no company names.
- "No competitors" — means the market wasn't researched, or there's no market.
- Feature list presented as strategy; no choice about what *not* to do.
- Benefits with adjectives and no numbers ("dramatically reduces downtime").
- The AI does the arithmetic that the user is expected to trust.
- Scope grew after the last review and nothing was cut to pay for it.
- Demo depends on a component that has never run end to end.
- Differentiation rests entirely on a prompt or a model choice.
- Tiering/packaging invented to satisfy a rubric, with no customer behind it.

## Working notes

- Timebox the review: Phases 1–2 first, and if the spec gate fails, stop and
  report — the rest can wait until the blockers are named.
- Prefer one strong quantified finding over ten qualitative ones.
- Write findings so the owner can act tomorrow morning. "Improve
  differentiation" is not actionable; "drop tier X, put the two days into the
  root-cause eval so the hit-rate claim survives Q&A" is.
- Keep the review file next to the idea, dated, so successive reviews can be
  diffed.
