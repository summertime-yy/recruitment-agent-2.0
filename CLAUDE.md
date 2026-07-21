# CLAUDE.md — Session Startup Guide for This Repository

> This file is auto-loaded by Claude Code when a session opens in this repo.
> It supplements (not replaces) `AGENTS.md` (repo conventions) and `HANDOFF.md` (progress).

## Read-First Order

When picking up work in this repo, read in this order **before doing anything else**:

1. **`HANDOFF.md`** — always start here.
   - The header shows the current stage and update date.
   - The last section (currently **§9 Stage 5 进行中**) has the freshest state: which PRs are merged, which is next, known hazards, and Stage 5.1 open items.
   - When you finish something significant, update HANDOFF.md's status table and (if applicable) the latest stage section — don't leave the doc stale.

2. **The most recent STEP6 report** under `docs/planning/stage5/PR*-STEP6-REPORT.md`.
   - The highest PR number that has a STEP6 report reflects the last completed merge.
   - Read its "验收三道门" section to know the current test/lint baseline.

3. **The latest KICKOFF-DECISION** at `docs/planning/stage5/PR*-KICKOFF-DECISION.md`.
   - If a `PR{N+1}-KICKOFF-DECISION.md` exists and the corresponding STEP6 report does not, that PR is **waiting to be executed** — its §executor action checklist tells you exactly what to do.
   - If you are an executor agent, `§行动清单` (or `§Executor action checklist`) is your contract. Do not deviate silently; if you must, log the deviation in the STEP6 report you write.

4. **`AGENTS.md`** — repo-wide conventions (Python/TypeScript style, commit format, PR policy, Stage 5 Redis conventions).
   - The `## Stage 5 Conventions` section has hard rules about Redis DI, SSE buffer keys, background task pytest patterns — violating them will cost you time.

5. **Authoritative planning docs** (only when the KICKOFF-DECISION references them or you're planning a new PR):
   - `docs/planning/PLAN-STAGE5.md`, `TASKS-STAGE5.md`, `TEST-PLAN-STAGE5.md` (top-level, merged double-blind-review versions)
   - **Never read** `docs/planning/stage5/commander/` or `docs/planning/stage5/executor/` — those are pre-review drafts, superseded by the top-level files.

## PR Workflow (Stage 5+)

Every code PR follows this loop:

```
1. Read KICKOFF-DECISION for the PR   →  understand scope, gates, boundaries
2. git checkout master && git pull    →  start from latest
3. git checkout -b feat/pr-NN-<slug>  →  branch name per AGENTS.md §4.1
4. Red-test commit                    →  test skeleton first (TDD)
5. Green commits per DECISION §commit split
6. Run the 3 acceptance gates locally
7. Push branch, write PR{N}-STEP6-REPORT.md
8. Report back to commander for FF merge review
```

**Docs-only changes** (no `backend/app/**`, `frontend/src/**`, `alembic/versions/**` touched) may commit directly to master per AGENTS.md §4.1. This includes KICKOFF questions/decisions and progress reports.

## Stop-and-Ask Boundaries

Every KICKOFF-DECISION has a `§求助边界 / stop-and-ask` section listing conditions under which you must halt and report instead of proceeding. **Respect these strictly** — they exist because the commander already thought about the sharp edges and pre-approved a report-back over a workaround. Silent workarounds destroy the trail.

If you hit a condition not on the list but that materially changes the PR's contract (e.g. an authoritative doc contradicts the DECISION), stop and report anyway.

## Test & Verify Before Claiming Done

- `cd backend && uv run pytest -q` — the baseline count is documented in the latest STEP6 report. Any drop is a regression, halt.
- `cd backend && uv run ruff check <changed dirs>` — 0 errors required.
- `cd frontend && npm run lint && npm run build` — only if you touched `frontend/src/**`.
- Don't mark a PR done or write a STEP6 "全绿" report until all three gates pass with output pasted into the report.

## Housekeeping

- Untracked files listed in the KICKOFF-DECISION's `§工作区清理` (like `backend/backend.err`, `backend/scripts/*`) are **not** yours to commit unless the DECISION says so — they are ongoing untracked artifacts.
- After a PR is FF-merged to master, delete the remote feat branch (`git push origin --delete feat/pr-NN-...`). Local branch may stay for a week as reference.
- Do not commit `backend/.env` (gitignored). Do not create tags without explicit instruction.

## When You Get Stuck

- Ambiguity in the KICKOFF-DECISION → re-read the relevant `§Q` and its 建议. If still ambiguous, that's a stop-and-ask trigger.
- Test hangs (especially with `asyncio.create_task`) → check HANDOFF.md §9.4 hazards; if the pattern matches, stop and report.
- Unfamiliar dependency (e.g. fakeredis, langchain-openai) → check `pyproject.toml` and existing test fixtures for precedent before adding new patterns.

---

_Last touched: 2026-07-21 (Stage 5, PR-13 kickoff decision merged; executor may begin.)_
