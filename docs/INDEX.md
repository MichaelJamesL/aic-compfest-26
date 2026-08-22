# Documentation index

**Read this file first in every new session.** It says which document answers
which question, so you can load two or three files instead of the whole repo.

## Reading order

| If your task is… | Read, in this order |
| --- | --- |
| Anything at all | `docs/INDEX.md` (this file) → `docs/STATUS.md` → `docs/TODO.md` |
| Backend / API work | `docs/requirements/BACKEND.md` → `docs/API.md` → `docs/DEFECTS.md` |
| AI engine work | `docs/requirements/AI_ENGINE.md` → `docs/ARCHITECTURE.md` → `docs/DEFECTS.md` |
| Frontend work | `docs/requirements/FRONTEND.md` → `docs/design/VISUAL_LANGUAGE.md` → `docs/design/SCREENS.md` → `docs/API.md` |
| "Should we build X?" | `docs/FINAL_IDEA.md` §12 → `docs/DECISIONS.md` |
| Writing copy, proposal, video script | `docs/FINAL_IDEA.md` §15–16 (fixed wording — do not paraphrase) |

Do **not** read `docs/FINAL_IDEA.md` or `docs/DECISIONS.md` in full for a coding
task. They are long and product-facing. The engineering docs below already carry
what a coding task needs.

## The documents

### Product truth — edit here first, then propagate to code

| File | What it is | Read when |
| --- | --- | --- |
| [`FINAL_IDEA.md`](FINAL_IDEA.md) | **Single source of truth for the idea.** Positioning, the QC→failure-mode differentiator, the definition of "optimal", autonomy boundary, scope in/out, fixed wording (§15) and banned words (§16). | Scope questions, naming, any user-visible copy. Wins over every other document on conflict. |
| [`DECISIONS.md`](DECISIONS.md) | Locked decisions D0–D11 with their rationale, plus the competition rulebook constraints each one answers, plus the demo chain and the cut-order if time runs out. | Before proposing an architecture change, or when you need to know *why* something is the way it is. |
| [`FR.md`](FR.md) | The 36-row functional-requirement table submitted to the competition, plus the roadmap exclusions and the adoption ladder. | Checking whether a feature is in scope and what it is officially called. |

### Engineering truth — the docs a coding session actually needs

| File | What it is | Read when |
| --- | --- | --- |
| [`TODO.md`](TODO.md) | The execution schedule to the deadline: what to do in what order, in which track, with time boxes and the cut-order if we fall behind. Supersedes the plan table in `DECISIONS.md`. | Deciding what to pick up next. |
| [`STATUS.md`](STATUS.md) | The scoreboard: every FR row mapped to an owning area and its current state (done / partial / broken / not started). Roll-up only — details live in the three checklists. | Start of every session, to know where to continue. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the code is laid out, the module boundaries, the request→result data flow, and the invariants that must never be broken (what is deterministic vs what the LLM writes). | Before adding a module, changing the engine contract, or moving logic across the backend/ai-engine boundary. |
| [`API.md`](API.md) | The HTTP contract between frontend and backend: every route with its real, verified request/response shape, the error envelope, and the routes that are still missing. | Any frontend↔backend work. Frontend must not guess a payload shape from source. |
| [`DEFECTS.md`](DEFECTS.md) | Verified bugs in the current code, each with a reproduction, the reason it is wrong, and the intended fix. Every entry was reproduced by running the code, not read off. | Before touching `backend/app/main.py` or `ai-engine/src/signals.py`, and whenever a checklist item says **broken**. |

### Requirement checklists — one per area, the working surface

| File | Owner | Read when |
| --- | --- | --- |
| [`requirements/AI_ENGINE.md`](requirements/AI_ENGINE.md) | AI engineer | Working in `ai-engine/`. |
| [`requirements/BACKEND.md`](requirements/BACKEND.md) | Backend engineer | Working in `backend/`. |
| [`requirements/FRONTEND.md`](requirements/FRONTEND.md) | Frontend engineer | Working in `frontend/`. Also carries the stack decision and folder layout. |

### Design

| File | What it is | Read when |
| --- | --- | --- |
| [`design/VISUAL_LANGUAGE.md`](design/VISUAL_LANGUAGE.md) | The design system extracted from `docs/ref/ui-ref.jpg` — sampled colour values, type scale, spacing, radii, elevation rules, the restricted glass rule, and an explicit list of banned patterns. | Before writing any UI code or CSS. Non-negotiable. |
| [`design/SCREENS.md`](design/SCREENS.md) | Screen-by-screen specification: layout, regions, states (empty / loading / partial input / error), and which API call feeds each region. | Building or changing a screen. |
| [`ref/ui-ref.jpg`](ref/ui-ref.jpg) | The visual reference. Colours in `VISUAL_LANGUAGE.md` were sampled from this file. | Only if `VISUAL_LANGUAGE.md` does not answer the question. |

## Session protocol

1. Read `INDEX.md` + `STATUS.md`.
2. Read the one or two docs for your area from the table above.
3. Do the work. Follow `AGENTS.MD` for engineering posture (framework-first, no
   hand-rolling what a library provides).
4. **Update the checklist in the same commit as the code.** Tick a box only when
   the rule below is satisfied.
5. If you discover a new bug you are not fixing right now, add it to
   `DEFECTS.md` with a reproduction.

## Git workflow

Never commit straight to `main`. One branch per unit of work, merged when it is
green.

```bash
git checkout -b <type>/<short-slug>      # feat/ fix/ docs/ chore/
# … work …
cd frontend && npm run test && npm run build     # or the area's own checks
git add -A && git commit -m "feat: three to five words"
git push -u origin HEAD
git checkout main && git merge --no-ff <branch> && git push origin main
```

Rules:

- **Commit messages are 3–5 words total**, including the Conventional Commits
  prefix (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`). Conventional Commits
  are required by the rulebook. Never mention the assistant.
- **Run the area's checks before committing**, not after. A red commit on a
  shared branch costs someone else an hour.
- **Update the area checklist in the same commit as the code.** A tick and its
  feature land together or neither does.
- **Merge with `--no-ff`** so each unit of work stays a visible group in the
  history.
- Never rewrite published history. No force-push to `main`, ever.
- Nothing in the repo may identify an educational institution — rulebook
  requirement, and it applies to commit messages and author names too.

## Checklist rules

A box is ticked **only** when the feature is fully implemented *and* a test that
exercises it passes. "It looks right" is not tested. "The server starts" is not
tested.

```
- [x] Feature — verified: <the exact command that proves it>
- [ ] Feature — **partial**: <what exists> / missing: <what does not>
- [ ] Feature — **broken**: see DEFECTS.md#<id>
- [ ] Feature — not started
```

Never tick a box in the same edit that writes the feature unless you also ran
the test in that session and can paste the command. Untick a box the moment its
test fails.

## Conventions

- **Language.** Engineering docs (this file and everything under
  `requirements/`, `design/`, plus `ARCHITECTURE`, `API`, `STATUS`, `DEFECTS`)
  are written in English, matching `AGENTS.MD` and the code comments. Product
  docs (`FINAL_IDEA`, `DECISIONS`, `FR`) stay in Indonesian — they feed the
  proposal and the video. Quote the fixed Indonesian wording from
  `FINAL_IDEA.md` §15 verbatim in user-facing UI copy; do not translate it.
- **Commits.** Conventional Commits (`feat:` / `fix:` / `refactor:` / `docs:`).
  Required by the rulebook. Never mention the assistant in a commit message.
- **Scope.** If a feature is on the roadmap list in `FR.md`, do not build it,
  even if it seems easy. Overbuilding is scored against us
  (`DECISIONS.md` D0).
