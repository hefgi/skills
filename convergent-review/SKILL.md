---
name: convergent-review
description: >
  Run an iterative review loop until the code converges: a review workflow scores the diff by
  severity through one or more lenses (code, security, or all), Claude fixes the issues at the
  chosen strictness, commits, then re-reviews — looping until every lens comes back clean.
  Configurable at invocation: lens (lens=code|security|all), a model ladder (recommended
  Sonnet → Opus; also sonnet, opus, or a custom models= list), a strictness per lens (default
  code critical+major+minor, security critical+major), a per-tier round cap (rounds=3/5/10 or
  until-fixed), and extra criteria files (e.g. a project's PR-review skill). Asks if unspecified.
  Project-agnostic; any git repo. Use when the user asks to review-and-fix in a loop, do a
  feedback pass, "keep reviewing until clean", or run a security pass that fixes as it goes.
  For trying to break the code (attack, prove, re-attack), use /adversarial-review instead.
invocations:
  - /convergent-review
tags:
  - code-review
  - security
  - workflow
  - git
  - quality
version: 2.0.0
---

# Convergent Review

Run an iterative **review → fix → commit → re-review** loop until the review comes back clean for every
lens you asked for.

**Lenses** decide what a round looks for:

| Lens | Reviewers (one per dimension) | Use for |
|------|-------------------------------|---------|
| `code` *(default)* | correctness · conventions · robustness/perf | Everyday feedback pass on a branch |
| `security` | access control · untrusted input · data/secrets/config | Security sweep that fixes as it goes |
| `all` | all six, **in the same round** | Pre-merge pass on a risky diff |

With `all`, both lenses review every round, so a security fix that makes the code messier (or a code fix
that drops a guard) gets caught on the next round. Running the lenses one after another would miss that.

This skill aims for breadth and a clean result. To try to **break** the code (threat model, attack, prove,
re-attack), use `/adversarial-review`.

## How it works (two actors)

A Claude Code **workflow** orchestrates subagents but **cannot edit the working tree or commit** — its
subagents run in isolated contexts. So the loop is split:

| Step | Who |
|------|-----|
| Review the diff → verified, severity-graded findings per lens | **the bundled workflow** (`references/convergent-review.mjs`) |
| Apply the fixes | **you (the main agent)** |
| Commit round N | **you (the main agent)** |
| Re-review (round N+1) | **the bundled workflow** |
| Escalate models cheap → smart | **you (the main agent)** — run each tier of the chosen ladder to clean |
| Decide which severities to fix/enforce, per lens | **you (the main agent)** — the chosen strictness |
| Cap the rounds per tier | **you (the main agent)** — `maxRounds` (3/5/10 or until-fixed, ceiling 20) |

You drive the outer loop; the workflow is the per-round review engine you call. The workflow is invoked
directly from this skill's bundled path — **nothing is written into the user's repo.**

## Instructions

When invoked with `/convergent-review $ARGUMENTS`:

### 1. Prerequisites

- Confirm this is a git repo (`git rev-parse --git-dir`). If not, tell the user and STOP.
- Determine the current branch. If on `main`/`master`, create a working branch first (do not commit review
  fixes onto the default branch).
- Resolve the absolute path to this skill's bundled workflow (`references/convergent-review.mjs`, next to
  this `SKILL.md`) — you need it for the `Workflow` call below. The install location varies (global
  `~/.claude/`, tessl's `~/.agents/skills/` which `~/.claude/skills/` symlinks to, or a project checkout),
  so locate it rather than assuming. `-L` follows the tessl symlinks; trusted roots are searched before the
  cwd so a project-local copy can't shadow the installed one:
  ```bash
  find -L ~/.claude ~/.agents . -type f -path '*convergent-review/references/convergent-review.mjs' 2>/dev/null | head -1
  ```
  Use the returned absolute path as `scriptPath`. If nothing is found, tell the user the skill's workflow
  file is missing and STOP.
- **Pick the reviewer agent.** The workflow reviews with a subagent; it must be a **runtime-registered
  agent type**, not a skill or an on-disk agent file. Check your available agent types (the ones you can
  actually spawn): if a **`code-reviewer`** agent is available in this project, set `reviewerAgentType =
  "code-reviewer"` so the code lens uses the project's specialized reviewer; otherwise leave it unset and
  the workflow defaults to `general-purpose`. The security lens always uses `general-purpose` unless the
  user passes `securityAgentType`.
- **Find extra review criteria.** A workflow can't run a skill, but its reviewers can *read* one. Build
  `criteria` (a `{ code: [...], security: [...] }` map of absolute paths):
  - If `$ARGUMENTS` has `criteria=<path>[,<path>…]`, use those for the code lens, and
    `security-criteria=<path>…` for the security lens.
  - Otherwise look for a project PR-review skill and use it for the code lens:
    ```bash
    find "$(git rev-parse --show-toplevel)/.claude/skills" -maxdepth 2 -path '*pr-review*/SKILL.md' 2>/dev/null
    ```
    (e.g. `.claude/skills/acme-pr-review/SKILL.md`). The reviewers apply its review rules and
    ignore its procedure (checking out branches, posting to GitHub). Tell the user which file you picked.

### 2. Ask what's missing (at most two question calls)

Resolve each setting from `$ARGUMENTS` first; ask only for what's missing. Put the first four in **one**
`AskUserQuestion` call, then ask strictness in a second call only if it's still missing.

**Scope** (`scopeMode`):

| Choice | `scopeMode` | What it reviews |
|--------|-------------|-----------------|
| Branch diff vs base *(default)* | `branch` | The whole branch: `merge-base(HEAD, main/master)..HEAD`. Best for a feature-branch feedback pass. |
| Working-tree changes only | `working` | Staged + unstaged changes vs `HEAD`. |
| Specific paths | `paths` | The branch diff (`merge-base..HEAD`) restricted to the paths the user names (ask for them). |

If the user picks **Specific paths** and hasn't listed the paths, a follow-up question to collect them is
allowed — never pass `scopeMode: "paths"` with an empty `paths`, or it silently reviews the whole branch.

**Lens** (`lens=code|security|all` in `$ARGUMENTS`). Options: **Code** *(Recommended)*, **Security**,
**All (code + security)**.

**Model suite** — the escalation ladder, cheap → smart:

| In `$ARGUMENTS` | Resolved `tiers` |
|-----------------|------------------|
| `sonnet-opus` *(preset)* | `["sonnet", "opus"]` |
| `sonnet` *(preset)* | `["sonnet"]` |
| `opus` *(preset)* | `["opus"]` |
| `models=<a,b,c>` (explicit list) | that list, e.g. `models=haiku,sonnet,opus` → `["haiku","sonnet","opus"]` |

Options when asking: **Sonnet → Opus** *(Recommended — Sonnet clears the obvious issues cheaply, Opus does
the final sign-off)*, **Sonnet only**, **Opus only**. Mechanical work (scope, file-listing) always runs on
**Haiku** inside the workflow regardless of the ladder.

**Max rounds per tier** (`rounds=N` or `rounds=until`). Options: **Run until fixed** *(Recommended,
ceiling 20)*, **3**, **5**, **10**. "Run until fixed" sets `maxRounds = 20` — a hard safety ceiling, since a
growing diff may keep surfacing findings and never fully converge.

**Strictness** — `enforce[lens]`, the set of severities the loop both fixes and drives to zero for that
lens. Severities outside the set never block a clean result.

| In `$ARGUMENTS` | Resolved `enforce` |
|-----------------|--------------------|
| `strictness=critical,major` | that set for **every** running lens |
| `strictness=code:critical,major,minor;security:critical,major` | per lens |
| *(absent)* | ask: one multi-select question **per running lens** (same call) |

Defaults (pre-checked when asking): **code → `critical` + `major` + `minor`**, **security → `critical` +
`major`**. Security defaults stricter-to-stop because chasing every minor security finding drifts into
hardening the code doesn't need. `critical` should always be selected; if the user picks nothing for a
lens, use its default.

### 3. Run the ladder

```
globalRound = 0
for tier in tiers:
    prevSet = null                # reset the no-progress guard at the start of EACH tier
    tierRound = 0                 # reset the per-tier round counter
    run the per-tier loop below with reviewModel = tier
```

### 4. The per-tier loop (`maxRounds` cap per tier; resets each tier)

Track `tierRound` (the round number **within the current tier**) alongside `globalRound` (used only for
commit-message labelling). For each round in the current `tier`:

1. **Review** — increment both counters (`++tierRound`, `++globalRound`), then call the bundled workflow:
   ```
   Workflow({
     scriptPath: "<this-skill-dir>/references/convergent-review.mjs",
     args: { scopeMode, round: globalRound, paths, lens, criteria, reviewModel: tier, reviewerAgentType }
     // reviewerAgentType from step 1 (omit → general-purpose); criteria from step 1 (omit if empty).
     // Include base only if the user pinned one; mechanicsModel defaults to haiku.
     // Optional: focus:"<text>" to weight the reviewers toward a concern from $ARGUMENTS.
   })
   ```
   It returns `{ round, base, scopeMode, lenses, files, confirmed, counts, countsByLens }`.
   `confirmed` is the verified findings, each
   `{ id, lens, severity, file, location, title, detail, suggestedFix, overlapsWith? }`; `countsByLens` is
   `{ code: {critical, major, minor, nit}, security: {…} }` for the lenses that ran. The review **and** its
   per-finding verify both run on `tier`.

2. **Tier-clean check** — the tier is clean when, **for every running lens**, the sum of
   `countsByLens[lens]` over `enforce[lens]` is `0`. If clean → **break** to the next tier (or finish if
   this was the last). Fix trivial non-enforced findings opportunistically before moving on.

3. **No-progress guard** — build the identity set of the current unresolved **enforced** findings as
   `` `${lens}::${file.trim().replace(/^\.\//, '')}::${title.trim().toLowerCase()}` ``. Compare it **by
   value** (sort the keys and join) with `prevSet`. If equal, the same issues keep coming back: **escalate,
   don't quit** — `break` to the next tier, whose smarter model may fix or dismiss them. Only on the
   **last** tier do you stop the whole loop and report. Then set `prevSet` to the current set. `prevSet`
   starts `null` each tier, so round 1 never trips this.

4. **Iteration guard** — if `tierRound >= maxRounds`, this tier has hit its cap → **break** to the next
   tier (or stop and report if last). The findings from this capped review are reported but not fixed on
   this tier. If the cap fires on the **first** round of an escalated tier (so that tier applied zero
   fixes), say so in the report.

5. **Fix** — apply fixes for every `confirmed` finding whose severity is in `enforce[finding.lens]`, using
   its `suggestedFix` as a starting point (verify it against the actual code — don't apply blindly).
   - **Overlapping findings** (`overlapsWith`) describe the same spot from two lenses: fix them together,
     in one change.
   - **Conflicts between lenses** — if a code finding asks to remove or loosen a check that a security
     finding relies on (or would re-open a security fix from an earlier round), **security wins**: skip the
     code finding and note it in the report. This stops the loop from flip-flopping.
   - Fix non-enforced findings opportunistically when low-risk and quick; they never block clean.

6. **Commit** — stage only the files you actually edited (do **not** `git add -A` or `git add .` — the
   working tree may hold untracked secrets like `.env`; prefer explicit paths, or `git add -u`), then:
   ```bash
   git add <the files you fixed>   # or: git add -u
   git commit -m "Address <lens> review feedback (round <globalRound>, <tier>)"
   ```
   with `<lens>` = `code`, `security`, or `code and security` depending on what the round fixed. **No
   Claude attribution** in the message or trailers. If the round produced no file changes, skip the commit
   (and treat as no progress for the guard).

7. Repeat from step 1.

### 5. Completion report

When the loop ends, summarize:
- Lens(es), the ladder run (e.g. sonnet → opus), the reviewer agent used, any criteria files read,
  `enforce` per lens, and `maxRounds`; total rounds run and why it stopped (**final tier clean** /
  no-progress / hit the `maxRounds` cap).
- Issues fixed **per lens and severity** across all rounds; commits made (one per round).
- Code findings skipped because they conflicted with security.
- If stopped by a guard: list the remaining findings (lens, file, severity, title) so the user can decide.
- Non-enforced findings surfaced but intentionally left unfixed, so the user knows they exist.

## Notes

- **Project-agnostic** — no repo-specific rules baked in. Reviewers read the nearest `CLAUDE.md` as
  review criteria, plus any `criteria` files (a project's PR-review skill is picked up automatically).
- **Reviewer agent** — only **live agent types** qualify: workflow subagents resolve `agentType` against
  the runtime registry, not against agent files on disk or skills. That's why a project's PR-review
  *skill* is passed as a criteria **file** rather than as the reviewer. If every reviewer of a lens fails,
  the workflow throws rather than reporting a false "clean".
- **Security lens vs `/security-review` vs `/adversarial-review`** — the built-in `/security-review` is a
  single read-only pass. The security lens here is the same kind of sweep, but it loops and fixes until
  clean. `/adversarial-review` goes deep instead of wide: it attacks the code and requires proof.
- **Model tiering** — mechanical work runs on **Haiku**; each round's review and verify run on the
  current tier. Passing `reviewModel` overrides the `code-reviewer` agent's own model for that call, so
  the tier is applied uniformly.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
- **Nothing is copied into the repo** — the workflow runs from this skill's bundled `references/` path.
