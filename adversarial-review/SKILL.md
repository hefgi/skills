---
name: adversarial-review
description: >
  Try to break a diff instead of tidying it: threat-model the change into attack surfaces, send
  attacker agents at each one (intruder, state-breaker, profiteer), prove attacks with failing
  tests in an isolated worktree, and put the rest through a defender + judge contest. Claude fixes
  the confirmed attacks, keeps each proof as a regression test, then re-attacks the fixes looking
  for bypasses. Ends with a residual-risk report. Configurable at invocation: lens
  (security|correctness|economic|all), attacker cap, rounds, and models. Project-agnostic; any
  git repo. Use when the user asks for an adversarial review, a red-team pass, "try to break
  this", or a pre-merge review of risky code (auth, money, contracts, migrations). For a
  review-and-fix pass until clean, use /convergent-review instead.
invocations:
  - /adversarial-review
tags:
  - code-review
  - security
  - red-team
  - workflow
  - git
version: 1.0.0
---

# Adversarial Review

Assume the code can be broken and try to prove it. Each round runs:

```
Threat model → Attack (one agent per surface × persona) → Prove (failing test)
→ Contest (defender + judge, for what couldn't be proven) → [you fix + commit]
→ next round: re-attack the fixes → … → residual-risk report
```

How it differs from `/convergent-review`:

| | `/convergent-review` | `/adversarial-review` |
|---|---|---|
| Question | Is this clean? | Can this be broken? |
| Reviewers | Quality/security dimensions | Attackers with one goal each |
| A finding needs | A pointer to the code | Concrete steps, ideally a failing test |
| Verification | One skeptic per finding | Proof by test, else defender vs attacker before a judge |
| Re-review | Same review again | Attacks aimed at the fix itself |
| Ends when | Nothing left at the enforced severities | Attackers fail within budget; report lists what's left |

**Cost:** more expensive than a convergent round — roughly 1 threat model + up to 8 attackers + a prover
per provable attack + a defender and judge per unproven attack. Use it on risky diffs, not every PR.

## Lenses (attacker personas)

| Lens | Persona | Goal |
|------|---------|------|
| `security` | intruder | Do something you shouldn't be allowed to: act as someone else, reach their data/funds, inject, leak secrets |
| `correctness` | state-breaker | Reach a state the invariants forbid: double effects, lost updates, corruption, false success |
| `economic` | profiteer | Extract value: rounding drift, share/fee/price skew, oracle manipulation, MEV, reentrancy, griefing |
| `all` *(default)* | all three | The threat model sends each persona only where it's relevant (profiteer only where value moves) |

## How it works (two actors)

The bundled workflow (`references/adversarial-review.mjs`) runs one round and returns
`{ confirmed, uncertain, refuted, coverage, counts, threatModel }`. It can't edit your working tree or
commit, so **you** fix, add the proofs as regression tests, commit, and call it again. Nothing is copied
into the repo except the regression tests you choose to add.

## Instructions

When invoked with `/adversarial-review $ARGUMENTS`:

### 1. Prerequisites

- Confirm this is a git repo (`git rev-parse --git-dir`); if not, tell the user and STOP. Record
  `repoRoot = git rev-parse --show-toplevel`.
- If on `main`/`master`, create a working branch before committing fixes.
- **Uncommitted changes:** proofs run in a worktree created from `HEAD`, which doesn't contain uncommitted
  changes. If `git status --porcelain` shows changes to the files under review, ask the user to commit
  first (or accept `scopeMode: "working"`, which turns proving off, or pass `prove=inplace`).
- Locate the workflow:
  ```bash
  find -L ~/.claude ~/.agents . -type f -path '*adversarial-review/references/adversarial-review.mjs' 2>/dev/null | head -1
  ```
  If nothing is found, tell the user the workflow file is missing and STOP.

### 2. Ask what's missing (one question call)

Resolve from `$ARGUMENTS` first; ask for the rest in **one** `AskUserQuestion` call.

- **Scope** — `branch` *(default: merge-base with main/master..HEAD)*, `paths` (branch diff limited to
  paths the user names), or `working` (uncommitted changes; proving is off).
- **Lens** — `lens=all` *(Recommended)*, `security`, `correctness`, `economic`.
- **Models** — who attacks and who judges. Keep the judge on a **different** model from the attackers
  when you can, so it isn't grading its own model's reasoning:
  - **Sonnet attacks, Opus judges** *(Recommended)* → `attackModel: "sonnet", judgeModel: "opus"`
  - **Opus attacks, Sonnet judges** — deeper attacks, cheaper verdicts → `"opus"`, `"sonnet"`
  - **Opus for everything** — maximum depth, less independence → `"opus"`, `"opus"`
- **Rounds** — `rounds=N`, the cap on attack → fix → re-attack rounds. Options: **3** *(Recommended)*,
  **1** (report only, no fixing), **5**.

Defaults that aren't asked unless given in `$ARGUMENTS`:
- `fix=critical,major` — severities you fix. Others are reported, not fixed.
- `attackers=8` → `maxAttackers`.
- `prove=worktree` → `proveMode` (`inplace` runs provers one at a time in the real checkout with
  prefixed temp files; `off` skips proving and contests everything).
- `focus="<text>"` — a concern to weight the threat model toward.

### 3. The round loop

```
round = 0; threatModel = null; previous = []; fixedFiles = []
while round < rounds:
    round += 1
    result = Workflow({ scriptPath, args: {
        scopeMode, paths, round, lens, repoRoot, proveMode, maxAttackers, focus,
        attackModel, judgeModel,
        threatModel,            // null on round 1; reuse round 1's afterwards
        previous, fixedFiles    // empty on round 1
    }})
    if round == 1: threatModel = result.threatModel
    toFix = result.confirmed with severity in fix
    if toFix is empty: stop — "attackers failed at the enforced severities"
    if round == rounds: stop — report toFix as open (cap reached)
    fix + prove + commit (below)
    previous = the attacks you fixed;  fixedFiles = the files you changed
```

`result.confirmed` items look like
`{ id, title, severity, persona, surfaceId, file, location, invariant, preconditions, steps, badState,
suggestedFix, evidence: "reproduced" | "judged", proof?: { status, testPath, testCode, runCommand,
detail }, defense?, judgeReason?, bypassOf? }`.

**Fix, prove, commit** — for each attack in `toFix`:

1. **Add the proof first.** If it has `proof.testCode`, write it to `proof.testPath` (adjust the path to
   the project's test layout if needed) and run `proof.runCommand`. It must **fail**. If it passes before
   your fix, the proof is wrong — note it and treat the attack as judged.
   No proof (`evidence: "judged"`)? Write a minimal failing test yourself when the steps allow; otherwise
   fix from the steps and say in the report that there's no regression test.
2. **Fix** the code. Use `suggestedFix` as a starting point, not an instruction — fix the root cause so
   the whole class of attack is blocked, not just the exact steps.
3. **Run the proof again.** It must now pass. Run the related test suite too.
4. **Commit** the test and the fix together. Stage only the files you touched (never `git add -A` /
   `git add .`):
   ```bash
   git add <test file> <fixed files>
   git commit -m "Block <short attack title>"
   ```
   **No Claude attribution** in the message or trailers.

`uncertain` attacks depend on something the code alone can't settle (deployment config, an external
contract, runtime data). **Don't fix them silently** — list them for the user with what would settle them.

If `proveMode` was `inplace`, run `git status --porcelain` after each round and delete any leftover
`__adversarial_poc_*` files.

### 4. Residual-risk report

The run ends with a report, not "all clear". Include:

- **Setup:** lens, models (attacker / judge), proveMode, rounds run and why it stopped (attackers failed at
  the enforced severities / round cap).
- **Fixed:** each attack — title, severity, persona, evidence (reproduced by test or judged), the
  regression test path, the commit.
- **Bypasses:** any attack from round 2+ with `bypassOf` — a fix that didn't hold the first time.
- **Open:** confirmed attacks not fixed (below `fix` severities, or cap reached), with their steps.
- **Uncertain:** what each one depends on and how to settle it.
- **Refuted:** one line each with the blocking mechanism — this is the evidence the code holds there.
- **Coverage:** surfaces attacked, `coverage.notAttacked` (dropped by the attacker cap), and
  `coverage.failedAttackers`. Say plainly that unlisted surfaces and pairings were **not** attacked.

## Notes

- **No anchoring:** attackers, defenders and judges never see commit messages or PR descriptions — only
  the code. Comments claiming something is safe are treated as claims to test.
- **Proof beats argument:** an attack reproduced by a failing test is confirmed without a contest. Without
  a proof, the defender has to name the specific guard that stops it, or the attacker wins.
- **Fail loud:** if the threat model fails, or every attacker fails, the workflow throws — "no attacks"
  must never come from a broken run. A judge that dies leaves the attack **uncertain**, never refuted.
- **Worktrees:** provers symlink dependencies (e.g. `node_modules`, Foundry `lib/`) from `repoRoot`
  instead of installing, and clean up so the worktree is auto-removed. If the project can't run tests in
  a worktree, proofs come back `could-not-run` and those attacks go to the contest instead — nothing is
  dropped.
- **Pairs with:** `/convergent-review` (run it first to clear ordinary issues cheaply) and the built-in
  `/security-review` (a broad security checklist). This skill goes deep on a few surfaces instead.
- **No attribution** — never add `Co-Authored-By: Claude` or "Generated with Claude Code" to commits.
