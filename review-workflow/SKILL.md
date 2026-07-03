---
name: review-workflow
description: >
  Run an iterative code-review loop: a review workflow scores the diff by severity,
  Claude fixes every critical/major/minor issue (nits opportunistically), commits, then
  re-reviews — looping until the review comes back clean. Runs a configurable model
  ladder (default Sonnet → Opus; also sonnet, opus, or a custom models= list).
  Project-agnostic; any git repo. Use when the user asks to review-and-fix in a loop,
  do a feedback pass, or "keep reviewing until clean".
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
| Escalate models cheap → smart | **you (the main agent)** — run each tier of the chosen ladder to clean |

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

### 3. Choose the model suite (the escalation ladder)

The review runs on a **ladder** of models, cheap → smart: it converges on the first tier, then re-converges
on the next, and so on. Mechanical work (scope, file-listing) always runs on **Haiku** inside the workflow
regardless of the ladder.

Resolve `tiers` (an ordered list of review models) from `$ARGUMENTS`:

| In `$ARGUMENTS` | Resolved `tiers` |
|-----------------|------------------|
| `sonnet-opus` *(preset)* | `["sonnet", "opus"]` |
| `sonnet` *(preset)* | `["sonnet"]` |
| `opus` *(preset)* | `["opus"]` |
| `models=<a,b,c>` (explicit list) | that list, e.g. `models=haiku,sonnet,opus` → `["haiku","sonnet","opus"]` |

If no model suite is present in `$ARGUMENTS`, ask with **one** `AskUserQuestion` offering exactly these
options (recommended one first):

- **Sonnet → Opus** *(Recommended)* — Sonnet clears the obvious issues cheaply, then Opus does the final,
  smartest sign-off. → `["sonnet", "opus"]`
- **Sonnet only** — single cheaper/faster pass. → `["sonnet"]`
- **Opus only** — max quality from round one, higher cost. → `["opus"]`

Then run the ladder:
```
globalRound = 0
for tier in tiers:
    run the per-tier loop below with reviewModel = tier   # reset the no-progress guard at each tier
```

### 4. The per-tier loop (round-by-round, shared cap of 8 rounds across all tiers)

For each round in the current `tier`:

1. **Review** — call the bundled workflow:
   ```
   Workflow({
     scriptPath: "<this-skill-dir>/references/review-loop.mjs",
     args: { scopeMode, round: ++globalRound, paths, focus, reviewModel: tier }
     // include base only if the user pinned one; mechanicsModel defaults to haiku
   })
   ```
   It returns `{ round, base, scopeMode, files, confirmed, counts }` where `confirmed` is the
   adversarially-verified findings (each `{ severity, file, location, title, detail, suggestedFix }`)
   and `counts` is `{ critical, major, minor, nit }`. The review **and** its per-finding verify both run on
   `tier`.

2. **Tier-clean check** — if `counts.critical + counts.major + counts.minor === 0`, this tier is clean →
   **break** to the next tier (or, if this was the last tier, finish). Fix trivial nits opportunistically
   before moving on.

3. **No-progress guard** — build the identity set of the current unresolved (critical/major/minor) findings
   as `` `${file}::${title.trim().toLowerCase()}` ``. If it **equals the previous round's set within this
   tier**, stop the whole loop and report — the same issues keep coming back. **Reset this set when a new
   tier starts** (a smarter model is expected to surface different findings; that is progress, not a stall).

4. **Iteration guard** — if `globalRound === 8`, stop and report the remaining findings.

5. **Fix** — apply fixes for every `confirmed` critical/major/minor finding, using its `suggestedFix` as a
   starting point (verify it's correct against the actual code — don't apply blindly). Also fix `nit`
   findings when the change is low-risk and quick.

6. **Commit** — stage and commit the round's fixes:
   ```bash
   git add -A && git commit -m "Address code review feedback (round <globalRound>, <tier>)"
   ```
   **No Claude attribution** in the message or trailers. If the round produced no file changes, skip the
   commit (and treat as no progress for the guard).

7. Repeat from step 1.

### 5. Completion report

When the loop ends, summarize:
- The ladder run (e.g. sonnet → opus), total rounds, and why it stopped (**final tier clean** / no-progress
  / hit 8 rounds).
- Issues fixed per severity across all rounds; commits made (one per round).
- If stopped by a guard: list the remaining findings (file, severity, title) so the user can decide.

## Notes

- **Project-agnostic** — no repo-specific rules baked in; the workflow reads the nearest `CLAUDE.md` and
  treats its conventions as review criteria.
- **Reviewer agent** — the workflow prefers the `code-reviewer` agent (shipped by Claude Code's official
  review plugins) and **falls back** to the default workflow subagent when it isn't available, so the loop
  runs anywhere.
- **Model tiering (cost-efficient, configurable)** — mechanical work (scope, file-listing) runs on
  **Haiku**; the review ladder is chosen at invocation (default **Sonnet → Opus**; also `sonnet`, `opus`,
  or an explicit `models=…` list — see step 3). Each review round's verify phase runs on the same tier as
  its review. The skill passes `reviewModel`/`mechanicsModel` into the workflow `args`. Note: passing
  `reviewModel` overrides the `code-reviewer` agent's own model for that call, so the tier is applied
  uniformly.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
- **Nothing is copied into the repo** — the workflow runs from this skill's bundled `references/` path.
