---
name: review-workflow
description: >
  Run an iterative code-review loop: a review workflow scores the diff by severity,
  Claude fixes every critical/major/minor issue (nits opportunistically), commits, then
  re-reviews — looping until the review comes back clean. Runs a configurable model
  ladder chosen at invocation (recommended Sonnet → Opus; also sonnet, opus, or a
  custom models= list — asks if unspecified). Project-agnostic; any git repo. Use
  when the user asks to review-and-fix in a loop, do a feedback pass, or "keep
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
| Escalate models cheap → smart | **you (the main agent)** — run each tier of the chosen ladder to clean |

You drive the outer loop; the workflow is the per-round review engine you call. The workflow is invoked
directly from this skill's bundled path — **nothing is written into the user's repo.**

## Instructions

When invoked with `/review-workflow $ARGUMENTS`:

### 1. Prerequisites

- Confirm this is a git repo (`git rev-parse --git-dir`). If not, tell the user and STOP.
- Determine the current branch. If on `main`/`master`, create a working branch first (do not commit review
  fixes onto the default branch).
- Resolve the absolute path to this skill's bundled workflow (`references/review-loop.mjs`, next to this
  `SKILL.md`) — you need it for the `Workflow` call below. The install location varies (project
  `.claude/skills/`, global `~/.claude/`, or a tessl cache path), so locate it rather than assuming:
  ```bash
  find . ~/.claude ~/.tessl -type f -path '*review-workflow/references/review-loop.mjs' 2>/dev/null | head -1
  ```
  Use the returned absolute path as `scriptPath`. If nothing is found, tell the user the skill's workflow
  file is missing and STOP.

### 2. Ask scope (once)

Use **one** `AskUserQuestion` to pick what to review, then run the rest autonomously:

| Choice | `scopeMode` | What it reviews |
|--------|-------------|-----------------|
| Branch diff vs base *(default)* | `branch` | The whole branch: `merge-base(HEAD, main/master)..HEAD`. Best for a feature-branch feedback pass. |
| Working-tree changes only | `working` | Staged + unstaged changes vs `HEAD`. |
| Specific paths | `paths` | The branch diff (`merge-base..HEAD`) restricted to the paths the user names (ask for them). |

If the user already stated the scope in `$ARGUMENTS`, skip the question and use it. If they pick **Specific
paths** and haven't listed the paths, a follow-up question to collect the path list is allowed (this is the
one exception to "one question") — never pass `scopeMode: "paths"` with an empty `paths`, or it silently
reviews the whole branch.

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
    prevSet = null                # reset the no-progress guard at the start of EACH tier
    run the per-tier loop below with reviewModel = tier
```

### 4. The per-tier loop (round-by-round, shared cap of 8 rounds across all tiers)

For each round in the current `tier`:

1. **Review** — call the bundled workflow:
   ```
   Workflow({
     scriptPath: "<this-skill-dir>/references/review-loop.mjs",
     args: { scopeMode, round: ++globalRound, paths, reviewModel: tier }
     // include base only if the user pinned one; mechanicsModel defaults to haiku.
     // Optional: pass focus:"<text>" to weight the reviewers toward a concern the
     // user called out in $ARGUMENTS.
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
   as `` `${file.trim().replace(/^\.\//, '')}::${title.trim().toLowerCase()}` `` (normalize both halves so
   `./x` and `x` don't read as different findings). If it **equals `prevSet`** (the same issues keep
   coming back within this tier): **escalate, don't quit** — `break` to the **next tier**, whose smarter
   model may fix or dismiss them. Only if this is already the **last tier** do you stop the whole loop and
   report. Then set `prevSet` to the current set for the next round. `prevSet` starts `null` at each tier
   (set in the ladder above), so round 1 of a tier never falsely trips this.

4. **Iteration guard** — if `globalRound >= 8`, stop and report the remaining findings. (`>=`, not `===`,
   so a tier that escalated at round 8 can't push `globalRound` to 9 and slip past the cap.) This caps the
   run at 8 *reviews*: the 8th review's findings are reported but not fixed/committed, so at most 7
   fix-commit rounds occur. That's intentional — a hard backstop, not a target.

5. **Fix** — apply fixes for every `confirmed` critical/major/minor finding, using its `suggestedFix` as a
   starting point (verify it's correct against the actual code — don't apply blindly). Also fix `nit`
   findings when the change is low-risk and quick.

6. **Commit** — stage only the files you actually edited (do **not** `git add -A`/`-A` — the working tree
   may hold untracked secrets like `.env`; prefer explicit paths, or `git add -u` for tracked-only), then
   commit:
   ```bash
   git add <the files you fixed>   # or: git add -u
   git commit -m "Address code review feedback (round <globalRound>, <tier>)"
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
- **Reviewer agent** — the workflow reviews with the `general-purpose` workflow subagent by default, so it
  runs anywhere. (Workflow subagents resolve agent types against the runtime registry, not agent files on
  disk, so a repo/plugin `code-reviewer.md` is *not* usable here.) If a custom review agent is registered
  at runtime, pass its name via `reviewerAgentType` in `args`. If every reviewer fails, the workflow throws
  rather than reporting a false "clean" — so a broken review can never be mistaken for a passing one.
- **Model tiering (cost-efficient, configurable)** — mechanical work (scope, file-listing) runs on
  **Haiku**; the review ladder is chosen at invocation (default **Sonnet → Opus**; also `sonnet`, `opus`,
  or an explicit `models=…` list — see step 3). Each review round's verify phase runs on the same tier as
  its review. The skill passes `reviewModel`/`mechanicsModel` into the workflow `args`. Note: passing
  `reviewModel` overrides the `code-reviewer` agent's own model for that call, so the tier is applied
  uniformly.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
- **Nothing is copied into the repo** — the workflow runs from this skill's bundled `references/` path.
