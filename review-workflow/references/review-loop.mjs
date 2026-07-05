export const meta = {
  name: 'review-loop',
  description: 'Adversarial multi-dimension review of a diff; verify findings, return them by severity. One round — invoke again after fixes (bump args.round) to continue the loop.',
  whenToUse:
    'Reviewing a branch/PR diff or working-tree changes for bugs and quality. Fans out reviewers by dimension, adversarially verifies each finding to drop false positives, and returns findings by severity plus counts. Runs one round; invoke again after applying fixes (bump args.round) to continue. Project-agnostic — no repo-specific rules.',
  phases: [
    { title: 'Scope', detail: 'derive base + changed files from git' },
    { title: 'Review', detail: 'parallel reviewers, one per dimension' },
    { title: 'Verify', detail: 'adversarially confirm each finding is real' },
  ],
}

// ---------------------------------------------------------------------------
// Inputs (all optional — sensible git-derived defaults). Pass via Workflow args:
//   {
//     scopeMode,      // 'branch' (default) | 'working' | 'paths'
//     base,           // explicit base ref (branch mode)
//     files,          // explicit file list (skips discovery)
//     paths,          // restrict discovery to these paths (paths mode)
//     round,          // review round number, for logging/labels
//     focus,          // free-text focus to weight the review
//     excludeGlobs,   // substring excludes overriding DEFAULT_EXCLUDES
//     dimensions,     // [{ key, prompt }] overriding DEFAULT_DIMENSIONS
//     reviewerAgentType, // review-phase agent type (default 'general-purpose');
//                     // must be a RUNTIME-registered agent, not just a file on disk
//     mechanicsModel, // model for scope/file-listing (default 'haiku')
//     reviewModel,    // model for the review + verify phases (this tier); e.g.
//                     // 'sonnet' then 'opus' across the skill's escalation ladder
//   }
// ---------------------------------------------------------------------------
const round = typeof args?.round === 'number' ? args.round : 1
const scopeMode = args?.scopeMode ?? 'branch'

// Model tiering (set by the driving skill's escalation ladder):
//   mechanicsModel — scope resolution, file listing, reviewer-agent probe. Cheap
//     mechanical work; defaults to haiku.
//   reviewModel    — the review AND verify phases for this tier. The skill runs
//     the loop on sonnet until clean, then re-runs on opus. Defaults to the
//     inherited session model when unset (omit the field so agents inherit).
const mechanicsModel = args?.mechanicsModel ?? 'haiku'
const reviewModel = args?.reviewModel ?? null
// Only attach a `model` opt when we actually have one — otherwise the agent
// inherits the session model (the Workflow contract's default).
const withModel = (opts, model) => (model ? { ...opts, model } : opts)

// Generated / vendored paths that shouldn't be hand-reviewed. Override via
// args.excludeGlobs (substring match on the path).
const DEFAULT_EXCLUDES = [
  'pnpm-lock.yaml',
  'package-lock.json',
  'yarn.lock',
  'Cargo.lock',
  'go.sum',
  'poetry.lock',
  '.snap',
  'dist/',
  'build/',
  '/generated/',
  '.generated.',
]
const excludes = Array.isArray(args?.excludeGlobs) ? args.excludeGlobs : DEFAULT_EXCLUDES

phase('Scope')

// Reviewer agent type. Workflow subagents resolve agentType against the RUNTIME
// registry (general-purpose, Explore, Plan, …), NOT against agent files on disk —
// a repo/plugin `code-reviewer.md` is invisible here and passing it throws
// "agent type not found", which would silently drop the reviewer to null. So the
// safe default is `general-purpose`. Callers who KNOW a custom review agent is
// registered at runtime can opt in via args.reviewerAgentType.
const reviewerAgentType = args?.reviewerAgentType ?? 'general-purpose'

// Build the review target as a shell diff spec + the file-discovery command,
// depending on scope mode. `branch` diffs base..HEAD; `working` diffs the
// working tree (staged + unstaged) against HEAD; `paths` restricts to args.paths.
const paths = Array.isArray(args?.paths) ? args.paths : []
const pathArgs = paths.length ? ' -- ' + paths.map((p) => `'${p}'`).join(' ') : ''

// Resolve the base ref (branch mode only): explicit arg > merge-base with the
// first existing default branch > HEAD~1 fallback.
let base = args?.base ?? null
if (scopeMode === 'branch' && !base) {
  base = await agent(
    `Determine the git base ref to diff this branch against, for a code review of "the work on this branch".
Run these and reason about the output:
  git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null   # often points at the default branch
  git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD master 2>/dev/null
  git log --oneline -1
Prefer the merge-base of HEAD with the repo's default branch (main/master, remote or local). If none resolve, use HEAD~1.
Return ONLY the resolved base commit SHA or ref — no prose.`,
    withModel({ label: 'scope:base', phase: 'Scope', agentType: 'Explore' }, mechanicsModel),
  ).then((s) => {
    // Take the last whitespace-token and strip any trailing prose punctuation
    // (a model that ignores "no prose" might return "…base is abc123.").
    const tok = (s ?? '').trim().split(/\s+/).pop() ?? ''
    return tok.replace(/[^A-Za-z0-9_/~^.-]+$/, '')
  })
  // A blank/failed base would make `git diff ..HEAD` an empty diff — i.e. a
  // silent false-clean. Fall back to HEAD~1 rather than reviewing nothing.
  if (!base) {
    log('scope:base returned empty — falling back to HEAD~1')
    base = 'HEAD~1'
  }
}

// The diff spec used in every reviewer/verifier prompt.
const diffSpec =
  scopeMode === 'working'
    ? `git diff HEAD${pathArgs}   # working-tree changes (staged + unstaged)`
    : scopeMode === 'paths'
      ? `git diff HEAD${pathArgs}   # changes restricted to the requested paths`
      : `git diff ${base}..HEAD${pathArgs}`

const nameOnlyCmd =
  scopeMode === 'working' || scopeMode === 'paths'
    ? `git diff --name-only HEAD${pathArgs}`
    : `git diff --name-only ${base}..HEAD${pathArgs}`

// Resolve the changed-file list: explicit arg > name-only diff minus excludes.
const files =
  Array.isArray(args?.files) && args.files.length > 0
    ? args.files
    : await agent(
        `List the source files changed for code review.
Run: ${nameOnlyCmd}
Then DROP any path containing any of these substrings (generated/vendored, not hand-reviewed):
${excludes.map((e) => '  - ' + e).join('\n')}
Return the remaining repo-relative paths. If none remain, return an empty list.`,
        {
          label: 'scope:files',
          phase: 'Scope',
          agentType: 'Explore',
          model: mechanicsModel,
          // StructuredOutput requires a top-level object schema, so wrap the list.
          schema: {
            type: 'object',
            additionalProperties: false,
            required: ['files'],
            properties: { files: { type: 'array', items: { type: 'string' } } },
          },
        },
      ).then((r) => r?.files ?? [])

if (!files || files.length === 0) {
  log('No reviewable (non-generated) files changed — nothing to review.')
  return { round, base, scopeMode, files: [], confirmed: [], counts: { critical: 0, major: 0, minor: 0, nit: 0 } }
}

log(
  `Round ${round}: reviewing ${files.length} file(s) [${scopeMode}] with ${reviewerAgentType} agent on ${reviewModel ?? 'session'} model`,
)

const FINDING_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'file', 'title', 'detail', 'suggestedFix'],
        properties: {
          severity: { type: 'string', enum: ['critical', 'major', 'minor', 'nit'] },
          file: { type: 'string' },
          location: { type: 'string', description: 'symbol or line hint' },
          title: { type: 'string' },
          detail: { type: 'string', description: 'why it is a problem' },
          suggestedFix: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['isReal', 'severity', 'reason'],
  properties: {
    isReal: { type: 'boolean' },
    severity: { type: 'string', enum: ['critical', 'major', 'minor', 'nit'] },
    reason: { type: 'string' },
  },
}

// Shared context every reviewer/verifier gets. Reviewers read the diff AND the
// full current file (rewritten files aren't captured by hunks alone), plus the
// nearest CLAUDE.md for project conventions — so no conventions need to be
// pasted in here.
const focusBlock = args?.focus ? `\nFOCUS FROM THE REQUESTER (weight these):\n${args.focus}\n` : ''
const CONTEXT = `Code review, round ${round}.

SCOPE — restricted to these files:
${files.map((f) => '  - ' + f).join('\n')}

To review, run and read:
  git log --oneline -5
  ${diffSpec}
Then READ THE FULL CURRENT CONTENT of each file (a rewritten file's hunks hide context).
Ignore generated/vendored files.

PROJECT CONVENTIONS: read the nearest CLAUDE.md (repo root and any closer to the
changed files) and treat its rules as review criteria — flag violations. If no
CLAUDE.md exists, apply general best practices for the language/framework in use.
${focusBlock}
SEVERITY: critical = data loss/crash/security/wrong results shipped; major = real
bug or convention violation with user impact; minor = correctness-neutral quality
(naming, dead code, weak tests, a11y polish); nit = trivial. Do NOT invent work —
only report what you can point to in the actual code.`

// Default review lenses. Override with args.dimensions: [{ key, prompt }].
const DEFAULT_DIMENSIONS = [
  {
    key: 'correctness',
    prompt:
      'You are a CORRECTNESS reviewer. Hunt for logic bugs, off-by-one and boundary errors, timezone/locale issues in date math, null/undefined handling, incorrect async/await, race conditions, and whether tests actually assert the intended invariants (vs. tautological or overly-permissive assertions). Return findings by severity.',
  },
  {
    key: 'conventions',
    prompt:
      'You are a CONVENTIONS/quality reviewer. Enforce the CLAUDE.md rules; flag DRY violations, reimplementations of existing shared utilities, dead code, unsafe type casts, poor naming, and framework anti-patterns. Return findings by severity.',
  },
  {
    key: 'robustness',
    prompt:
      'You are a ROBUSTNESS/perf/security reviewer. Consider unbounded queries/memory, N+1 and hot-loop costs, missing error/loading/empty states, input validation at boundaries, accessibility, and any injection/authz/secret-handling risks. Return findings by severity.',
  },
]
const dimensions = Array.isArray(args?.dimensions) && args.dimensions.length > 0 ? args.dimensions : DEFAULT_DIMENSIONS

// Reviewer opts. reviewerAgentType is always a real runtime agent type
// (general-purpose by default), so it's always passed. The tier's review model
// overrides any agent-definition default so the escalation ladder controls the
// tier uniformly.
const reviewerOpts = (key) =>
  withModel({ label: `review:${key}`, phase: 'Review', schema: FINDING_SCHEMA, agentType: reviewerAgentType }, reviewModel)

phase('Review')
const reviews = await parallel(dimensions.map((d) => () => agent(`${CONTEXT}\n\n${d.prompt}`, reviewerOpts(d.key))))

// Fail loud, not silent: a reviewer that throws becomes null via parallel(). If
// EVERY reviewer failed, "0 findings" is a broken review, not a clean one —
// returning clean counts here would let the driving loop declare success on a
// review that never actually ran. Surface it instead.
const okReviews = reviews.filter(Boolean)
if (okReviews.length === 0) {
  throw new Error(
    `Round ${round}: all ${dimensions.length} reviewers failed (agentType="${reviewerAgentType}", model="${reviewModel ?? 'session'}"). This is a review failure, not a clean result — check the agent type is valid.`,
  )
}

const allFindings = okReviews.flatMap((r) => r.findings ?? [])
log(`Round ${round}: ${allFindings.length} raw findings from ${okReviews.length}/${dimensions.length} reviewers`)

if (allFindings.length === 0) {
  return { round, base, scopeMode, files, confirmed: [], counts: { critical: 0, major: 0, minor: 0, nit: 0 } }
}

phase('Verify')
const verified = await parallel(
  allFindings.map((f) => () =>
    agent(
      `${CONTEXT}\n\nAdversarially VERIFY this single finding. Read the actual code and decide whether it is a REAL issue worth fixing. Default to isReal=false if it is speculative, already handled elsewhere, a false positive, an intentional/documented tradeoff, or contradicts the project conventions. Re-grade severity honestly (a "critical" that's really cosmetic should come back minor/nit).\n\nFINDING:\nseverity=${f.severity}\nfile=${f.file}\nlocation=${f.location ?? ''}\ntitle=${f.title}\ndetail=${f.detail}\nsuggestedFix=${f.suggestedFix}`,
      withModel(
        {
          label: `verify:${f.severity}:${String(f.file).split('/').pop()}`,
          phase: 'Verify',
          schema: VERDICT_SCHEMA,
          agentType: 'Explore',
        },
        reviewModel,
      ),
    ).then((v) => (v && v.isReal ? { ...f, severity: v.severity, verifyReason: v.reason } : null)),
  ),
)

const confirmed = verified.filter(Boolean)
const order = { critical: 0, major: 1, minor: 2, nit: 3 }
confirmed.sort((a, b) => order[a.severity] - order[b.severity])
log(`Round ${round}: ${confirmed.length} confirmed after adversarial verify`)

const counts = {
  critical: confirmed.filter((f) => f.severity === 'critical').length,
  major: confirmed.filter((f) => f.severity === 'major').length,
  minor: confirmed.filter((f) => f.severity === 'minor').length,
  nit: confirmed.filter((f) => f.severity === 'nit').length,
}

return { round, base, scopeMode, files, confirmed, counts }
