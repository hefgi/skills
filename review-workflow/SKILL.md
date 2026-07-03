---
name: review-workflow
description: >
  Run an iterative code-review loop: a review workflow scores the diff by severity,
  Claude fixes every critical/major/minor issue (nits opportunistically), commits, then
  re-reviews — looping until the review comes back clean. Project-agnostic; any git repo.
  Use when the user asks to review-and-fix in a loop, do a feedback pass, or "keep
  reviewing until clean".
invocations:
  - /review-workflow
tags:
  - code-review
  - workflow
  - git
  - quality
version: 1.0.0
---

# Review Workflow Skill

Run an iterative **review → fix → commit → re-review** loop until a code review comes back clean.

## How it works (two actors)

A Claude Code **workflow** orchestrates subagents but **cannot edit the working tree or commit** — its
subagents run in isolated contexts. So the loop is split:

| Step | Who |
|------|-----|
| Review the diff → verified, severity-graded findings | **the bundled workflow** (`references/review-loop.mjs`) |
| Apply the fixes | **you (the main agent)** |
| Commit round N | **you (the main agent)** |
| Re-review (round N+1) | **the bundled workflow** |

You drive the outer loop; the workflow is the per-round review engine you call. The workflow is invoked
directly from this skill's bundled path — **nothing is written into the user's repo.**

## Instructions

When invoked with `/review-workflow $ARGUMENTS`:

### 1. Prerequisites

- Confirm this is a git repo (`git rev-parse --git-dir`). If not, tell the user and STOP.
- Determine the current branch. If on `main`/`master`, create a working branch first (do not commit review
  fixes onto the default branch).
- Note this skill's directory — you need the absolute path to `references/review-loop.mjs` for the
  `Workflow` call below. It sits next to this `SKILL.md`.

### 2. Ask scope (once)

Use **one** `AskUserQuestion` to pick what to review, then run the rest autonomously:

| Choice | `scopeMode` | What it reviews |
|--------|-------------|-----------------|
| Branch diff vs base *(default)* | `branch` | The whole branch: `merge-base(HEAD, main/master)..HEAD`. Best for a feature-branch feedback pass. |
| Working-tree changes only | `working` | Staged + unstaged changes vs `HEAD`. |
| Specific paths | `paths` | Only the paths the user names (ask for them). |

If the user already stated the scope in `$ARGUMENTS`, skip the question and use it.

### 3. The loop (round N = 1, 2, …, up to 8)

For each round N:

1. **Review** — call the bundled workflow:
   ```
   Workflow({
     scriptPath: "<this-skill-dir>/references/review-loop.mjs",
     args: { scopeMode, round: N, paths, focus }   // include base only if the user pinned one
   })
   ```
   It returns `{ round, base, scopeMode, files, confirmed, counts }` where `confirmed` is the
   adversarially-verified findings (each `{ severity, file, location, title, detail, suggestedFix }`)
   and `counts` is `{ critical, major, minor, nit }`.

2. **Stop check** — if `counts.critical + counts.major + counts.minor === 0`, the review is clean → exit
   the loop (still fix any nits opportunistically if trivial, then finish).

3. **No-progress guard** — build the identity set of the current unresolved (critical/major/minor)
   findings as `` `${file}::${title.trim().toLowerCase()}` ``. If it **equals** the previous round's set
   (the same issues keep coming back), stop and report — you're not making progress. Healthy churn (a fix
   surfacing *new* issues) changes the set and does not trip this.

4. **Iteration guard** — if N === 8, stop and report the remaining findings.

5. **Fix** — apply fixes for every `confirmed` critical/major/minor finding, using its `suggestedFix` as a
   starting point (verify it's correct against the actual code — don't apply blindly). Also fix `nit`
   findings when the change is low-risk and quick.

6. **Commit** — stage and commit the round's fixes:
   ```bash
   git add -A && git commit -m "Address code review feedback (round N)"
   ```
   **No Claude attribution** in the message or trailers. If the round produced no file changes, skip the
   commit (and treat as no progress for the guard).

7. Increment N and repeat from step 1.

### 4. Completion report

When the loop ends, summarize:
- Rounds run and why it stopped (**clean** / no-progress / hit 8 rounds).
- Issues fixed per severity across all rounds; commits made (one per round).
- If stopped by a guard: list the remaining findings (file, severity, title) so the user can decide.

## Notes

- **Project-agnostic** — no repo-specific rules baked in; the workflow reads the nearest `CLAUDE.md` and
  treats its conventions as review criteria.
- **Reviewer agent** — the workflow prefers the `code-reviewer` agent (shipped by Claude Code's official
  review plugins) and **falls back** to the default workflow subagent when it isn't available, so the loop
  runs anywhere.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
- **Nothing is copied into the repo** — the workflow runs from this skill's bundled `references/` path.
