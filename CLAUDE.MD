# Guide for Claude Code

- **Read [`docs/INDEX.md`](docs/INDEX.md) first, in every session.** It maps
  every document to the task it answers, so you can load two or three files
  instead of exploring the repo. Then read
  [`docs/STATUS.md`](docs/STATUS.md) to see where work stands.
- See [`AGENTS.MD`](AGENTS.MD) for the engineering posture and framework rules.
- Tick a checklist box only when the feature is implemented **and** a test that
  exercises it passes — the rule is in `docs/INDEX.md`. Update the checklist in
  the same commit as the code.
- **Git workflow** (full version in `docs/INDEX.md`): branch per unit of work,
  run the area's checks, commit, push, then merge to `main` with `--no-ff`.
  Never commit directly to `main`.
- Commit messages are **3–5 words total**, including the Conventional Commits
  prefix. Don't mention Claude when committing.
