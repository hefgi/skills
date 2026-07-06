---
name: review-workflow
description: >
  Run an iterative code-review loop: a review workflow scores the diff by severity,
  Claude fixes the issues at the chosen strictness, commits, then re-reviews — looping
  until the review comes back clean. Configurable at invocation: a model ladder
  (recommended Sonnet → Opus; also sonnet, opus, or a custom models= list) and a
  strictness set of severities to enforce (default critical+major+minor; e.g.
  strictness=critical,major). Asks if unspecified. Project-agnostic; any git repo. Use
  when the user asks to review-and-fix in a loop, do a feedback pass, or "keep
  reviewing until clean".
invocations:
  - /review-workflow
tags:
  - code-review
  - workflow
  - git
  - quality
version: 1.2.0
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
| Decide which severities to fix/enforce | **you (the main agent)** — the chosen strictness set |

You drive the outer loop; the workflow is the per-round review engine you call. The workflow is invoked
directly from this skill's bundled path — **nothing is written into the user's repo.**

## Instructions

When invoked with `/review-workflow $ARGUMENTS`:

### 1. Prerequisites

- Confirm this is a git repo (`git rev-parse --git-dir`). If not, tell the user and STOP.
- Determine the current branch. If on `main`/`master`, create a working branch first (do not commit review
  fixes onto the default branch).
- Resolve the absolute path to this skill's bundled workflow (`references/review-loop.mjs`, next to this
  `SKILL.md`) — you need it for the `Workflow` call below. The install location varies (global
  `~/.claude/`, tessl's `~/.agents/skills/` which `~/.claude/skills/` symlinks to, or a project checkout),
  so locate it rather than assuming. `-L` follows the tessl symlinks; trusted roots are searched before the
  cwd so a project-local copy can't shadow the installed one:
  ```bash
  find -L ~/.claude ~/.agents . -type f -path '*review-workflow/references/review-loop.mjs' 2>/dev/null | head -1
  ```
  Use the returned absolute path as `scriptPath`. If nothing is found, tell the user the skill's workflow
  file is missing and STOP.
- **Pick the reviewer agent.** The workflow reviews with a subagent; it must be a **runtime-registered
  agent type**, not a skill or an on-disk agent file. Check your available agent types (the ones you can
  actually spawn): if a **`code-reviewer`** agent is available in this project, set `reviewerAgentType =
  "code-reviewer"` so the review uses the project's specialized reviewer; otherwise leave it unset and the
  workflow defaults to `general-purpose`. (Only agents in the live registry work — a project's PR-review
  *skill* or an unregistered `code-reviewer.md` cannot be used as the reviewer.)

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

You can ask the scope, model, and strictness questions together in a single `AskUserQuestion` call (it
takes multiple questions) — that still counts as asking "once".

### 4. Choose strictness (which severities to enforce)

`enforce` is the **set of severities the loop both fixes and drives to zero** before a tier is clean.
Severities *not* in the set are ignored for the stop condition; anything in the set is fixed every round.

Resolve `enforce` from `$ARGUMENTS`:

| In `$ARGUMENTS` | Resolved `enforce` |
|-----------------|--------------------|
| `strictness=<a,b,…>` (explicit list) | that set, e.g. `strictness=critical,major` → `{critical, major}` |
| *(absent)* | ask, pre-checked to the default below |

If no strictness is present in `$ARGUMENTS`, ask with **one** multi-select `AskUserQuestion` listing all four
severities — `critical`, `major`, `minor`, `nit` — pre-checked to **`critical` + `major` + `minor`** (the
default; unchanged from prior behavior). The user ticks exactly the severities to enforce (any combination,
e.g. `critical` + `major` + `nit` to skip minor). At least `critical` should be selected; if the user picks
nothing, fall back to the default.

### 5. The per-tier loop (round-by-round, shared cap of 8 rounds across all tiers)

For each round in the current `tier`:

1. **Review** — call the bundled workflow:
   ```
   Workflow({
     scriptPath: "<this-skill-dir>/references/review-loop.mjs",
     args: { scopeMode, round: ++globalRound, paths, reviewModel: tier, reviewerAgentType }
     // reviewerAgentType from step 1 (omit/undefined → workflow uses general-purpose).
     // include base only if the user pinned one; mechanicsModel defaults to haiku.
     // Optional: pass focus:"<text>" to weight the reviewers toward a concern the
     // user called out in $ARGUMENTS.
   })
   ```
   It returns `{ round, base, scopeMode, files, confirmed, counts }` where `confirmed` is the
   adversarially-verified findings (each `{ severity, file, location, title, detail, suggestedFix }`)
   and `counts` is `{ critical, major, minor, nit }`. The review **and** its per-finding verify both run on
   `tier`.

2. **Tier-clean check** — if the sum of `counts` over the **enforced** severities is `0` (e.g. for
   `enforce = {critical, major}`, `counts.critical + counts.major === 0`), this tier is clean → **break** to
   the next tier (or, if this was the last tier, finish). Fix trivial non-enforced findings opportunistically
   before moving on.

3. **No-progress guard** — build the identity set of the current unresolved **enforced** findings
   as `` `${file.trim().replace(/^\.\//, '')}::${title.trim().toLowerCase()}` `` (normalize both halves so
   `./x` and `x` don't read as different findings). If it **equals `prevSet`** (the same issues keep
   coming back within this tier): **escalate, don't quit** — compare the sets by value (e.g. sort the keys
   and join to a string), not by object identity — `break` to the **next tier**, whose smarter
   model may fix or dismiss them. Only if this is already the **last tier** do you stop the whole loop and
   report. Then set `prevSet` to the current set for the next round. `prevSet` starts `null` at each tier
   (set in the ladder above), so round 1 of a tier never falsely trips this.

4. **Iteration guard** — if `globalRound >= 8`, stop and report the remaining findings. (`>=`, not `===`,
   so the cap can't be skipped past if an escalation lands `globalRound` on 9.) This caps the run at ~8
   *reviews* (at most one extra if a tier escalation happens to run a 9th review before the guard fires);
   the final review's findings are reported but not fixed/committed. That's intentional — a hard backstop,
   not a target. If the guard fires on the **first** round of an escalated tier (so that tier applied zero
   fixes), say so in the report and suggest re-running `/review-workflow <that tier>` on a fresh branch.

5. **Fix** — apply fixes for every `confirmed` finding whose severity is in `enforce`, using its
   `suggestedFix` as a starting point (verify it's correct against the actual code — don't apply blindly).
   Also fix non-enforced findings opportunistically when the change is low-risk and quick, but they never
   block the tier-clean check.

6. **Commit** — stage only the files you actually edited (do **not** `git add -A` or `git add .` — the
   working tree may hold untracked secrets like `.env`; prefer explicit paths, or `git add -u` for
   tracked-only), then commit:
   ```bash
   git add <the files you fixed>   # or: git add -u
   git commit -m "Address code review feedback (round <globalRound>, <tier>)"
   ```
   **No Claude attribution** in the message or trailers. If the round produced no file changes, skip the
   commit (and treat as no progress for the guard).

7. Repeat from step 1.

### 6. Completion report

When the loop ends, summarize:
- The ladder run (e.g. sonnet → opus), the reviewer agent used (`code-reviewer` or `general-purpose`), and
  enforced severities (e.g. critical+major); total rounds, and why it stopped (**final tier clean** /
  no-progress / hit 8 rounds).
- Issues fixed per severity across all rounds; commits made (one per round).
- If stopped by a guard: list the remaining findings (file, severity, title) so the user can decide.
- Note any non-enforced findings surfaced but intentionally left unfixed, so the user knows they exist.

## Notes

- **Project-agnostic** — no repo-specific rules baked in; the workflow reads the nearest `CLAUDE.md` and
  treats its conventions as review criteria.
- **Reviewer agent** — the skill auto-detects a runtime-registered `code-reviewer` agent (step 1) and uses
  it when present, so on projects that ship one (e.g. onyx) the review uses that specialized reviewer;
  otherwise it falls back to the `general-purpose` workflow subagent, so it runs anywhere. Only **live
  agent types** qualify — workflow subagents resolve `agentType` against the runtime registry, not against
  agent files on disk or skills, so a project's PR-review *skill* or an unregistered `code-reviewer.md`
  cannot be the reviewer. You can also force a specific agent by passing `reviewerAgentType` in `$ARGUMENTS`.
  If every reviewer fails, the workflow throws rather than reporting a false "clean" — so a broken review
  can never be mistaken for a passing one.
- **Model tiering (cost-efficient, configurable)** — mechanical work (scope, file-listing) runs on
  **Haiku**; the review ladder is chosen at invocation (default **Sonnet → Opus**; also `sonnet`, `opus`,
  or an explicit `models=…` list — see step 3). Each review round's verify phase runs on the same tier as
  its review. The skill passes `reviewModel`/`mechanicsModel` into the workflow `args`. Note: passing
  `reviewModel` overrides the `code-reviewer` agent's own model for that call, so the tier is applied
  uniformly.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
- **Nothing is copied into the repo** — the workflow runs from this skill's bundled `references/` path.
