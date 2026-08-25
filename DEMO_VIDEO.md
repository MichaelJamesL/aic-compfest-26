# Demo Video Guide

One factory, one failing machine (PUMP-01), full loop: input → analysis → approval → execution → verification → report. Record in one take if you can; every step below maps to a screen.

## 1. Prep (before recording)

```bash
docker compose up --build                              # app at http://localhost:5173
backend/.venv/bin/python demo-data/make_demo_data.py   # refresh timestamps to "now"
python3 demo-data/seed.py --api http://localhost:8000 --reindex
```

- `seed.py` prints QC batch ids — keep the terminal visible or note them down.
- Do a full dry run first. If a sick machine doesn't light up, `make_demo_data.py` would have failed — rerun it.
- Pre-record checklist: browser at 5173 logged in as coordinator demo headers, no notifications, clean tabs.

## 2. Narration beats (the story)

Say these out loud, in order — they're the judged claims:

1. **Positioning** (one line): "AI Maintenance Coordinator — turns machine data, QC results, SOPs, history, and business constraints into one accountable maintenance decision."
2. **Differentiator**: QC defects as a machine-condition signal, and business-constraint-aware decisions — not just an alert.
3. **Honesty**: numbers (health score, anomalies, window) are deterministic; the LLM explains them, doesn't invent them.
4. **Autonomy**: AI proposes, human approves, technician executes, AI verifies evidence.
5. **Scope**: everything synchronous, static parameters, no background jobs — deliberate, per the rulebook.

## 3. Recording flow

| # | Screen | What to show | Say |
| --- | --- | --- | --- |
| 1 | **Setup** | Assets (8 machines), uploaded SOP/manual PDFs, maintenance history | "Onboarding is uploading documents — no retraining per factory." |
| 2 | **Business Context** | Shifts, technician roster, sparepart stock + ETA | "Decisions know constraints: stock, schedules, people." |
| 3 | **Analyze** | Pick **PUMP-01**, attach readings CSV + QC batch, run | "One form, one synchronous analysis." |
| 4 | **Analysis Result** | Health score (~5) + deduction breakdown, anomalies (bearing temp 62→93 °C, vibration past ISO limit), RCA with citations, priority, recommended window + runner-up, sparepart shortage flag (stock 1 vs min 2) | **Key beat**: "No sensor alarm fired — the QC signal and history caught it first. Every number traces to a source." |
| 5 | **Work Orders** | Draft work order: SOP steps, parts, skills, safety, duration, assigned technician/slot | "AI prepares; it does not act." |
| 6 | Approve | Click **Approve** as coordinator | "Human-in-the-loop is a feature, not a limitation." |
| 7 | **Execute** | Switch to technician, submit result + findings | |
| 8 | Verification | Verdict: `resolved` / `partial` / `not_resolved` + evidence | "AI verifies the evidence — it never marks its own work done." |
| 9 | **Report** | Final report; note the completed WO is written back to the knowledge base | "Learning happens as documents, not weight updates — no retraining." |
| 10 | **Compare** | Same asset, partial input vs full input | "Adoption is gradual: analysis works with whatever input exists; more input → deeper decision." |

Optional, if time allows: the **QC Model** tab (fit the vision model on reference photos) — shows the fine-tuned/detection model is real.

## 4. Don't miss

- [ ] PUMP-01 end to end — it's the machine where sensor, SOP, history, stock, and operator report all line up.
- [ ] Show a **citation/source list** on the analysis — audit trail is a claim.
- [ ] Show the **runner-up window and why it lost** — that's what makes "optimal" a number.
- [ ] Mention out-of-stock sparepart + ETA blocking — constraint awareness, concrete.
- [ ] Don't say: "real-time", "fully automatic", "continuously monitors". Say: "synchronous, on request".

## 5. If something breaks mid-recording

- Engine slow/failed → `AI_ENGINE_ENABLED=true` and DeepSeek key are in `.env`; offline stub still produces deterministic signals, keep going and narrate the numbers.
- QC images missing → they're gitignored; rerun `make_demo_data.py` to fetch them.
- Duplicate docs → re-uploading PDFs duplicates; everything else in `seed.py` is idempotent.
