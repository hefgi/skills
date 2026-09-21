# Workflow 4: Apply to many jobs at once

The user has several postings and wants them all applied to. One agent working
through them in sequence is slow, and the browser work is the slow part. Spawning
one subagent per posting turns a long serial run into a short parallel one.

You are the **orchestrator**, called `main` throughout this file. You do not
drive a browser. You spawn agents, answer their questions, approve their
submissions, and own the log.

Read this file only as the orchestrator. Subagents read `apply.md` and the
`ego-browser` skill. **Never give a subagent this file**: an agent that reads
"spawn one agent per posting" will fan out again.

## Deciding whether to fan out

Judgement, not a formula. The tradeoffs:

**Fan out when** there are enough postings that serial work would take long
enough to matter, they are on ordinary ATS boards, and the user's sessions are
already good. Parallel agents each hold their own browser context, so the total
wall-clock is roughly the slowest single application rather than the sum.

**Stay serial when:**

- There are only one or two postings. Two sequential applications usually finish
  before two spawned agents have finished reading the profile.
- Ego lite is not verified working yet. Debug it once yourself rather than
  watching five agents fail the same way.
- A posting needs account creation (Workday, Oracle, iCIMS) or a login the user
  must perform. An agent blocked on a human is a wasted slot, and the human is
  talking to you, not to it.
- The posting is LinkedIn Easy Apply. It is the expensive case, it needs the
  most turns, and it benefits least from delegation. Handle it yourself.

You can mix: fan out the straightforward boards and keep the awkward ones.

**Concurrency cap: `max_concurrent_applications` in `.job-apply/config.yaml`,
default 5.** `0` or `1` means do not fan out at all; work through the list
yourself. Refill slots as agents finish rather than launching everything.

The cap exists because **your attention is the real limit, not the machine's**.
Every agent stops and waits for you before submitting, and that gate is only
worth having if you actually read what you are approving. An orchestrator with
ten pending approvals rubber-stamps them, which is the same as having no gate at
all. If the user asks for more parallelism than this, say what the cap buys them
before raising it.

## Before spawning anything

**Dedupe the whole list once, yourself.** Check every URL against
`applications/log.csv`, and check for the same company and role arriving via two
different URLs. Five agents each checking only their own posting will not catch
two agents applying to the same role. Drop duplicates before spawning and tell
the user which you dropped.

**Keep your own list of what is in flight.** `log.csv` only gains a row when an
application finishes, so during a run it does not show what is currently being
worked on. Track, for each posting: the agent, its task space id, and its state
(spawned, blocked, awaiting approval, submitted, aborted). Dedupe anything added
mid-run against this list as well as against the log, and use it to notice an
agent you have not heard from.

**Load the workspace** as in `apply.md` Phase A. You need `profile/` and `qa/`
in your own context to verify what agents report back.

**Write the run brief** (below), once, before the first spawn.

## The run brief

Write it to `<workspace>/.job-apply/briefs/<YYYY-MM-DD>-run.md`, composed fresh
from the current skill and the current profile.

**The brief is a pointer and a work order. It is not a copy of the rules.** It
tells an agent which files to read and what its one job is. It never restates
what `apply.md` says, because a second copy of the rules drifts from the first,
and an agent that finds two versions of an instruction wastes its turns deciding
which to believe. When the skill changes, every agent picks the change up on its
next spawn, automatically, because it reads the skill rather than a copy.

Date the file rather than overwriting a fixed name, so a stale brief is visibly
stale, and so you are never rewriting a file that running agents are reading.

Contents:

```markdown
# Run brief: <YYYY-MM-DD>

Read these in full before anything else, and follow them exactly:
  <skill>/SKILL.md
  <skill>/references/apply.md
  the `ego-browser` skill

They are the rules. This brief does not restate them.

Workspace: <absolute path>
Today: <YYYY-MM-DD>

## Precedence
`profile/` and `qa/` hold decisions already made. A `#` comment above a key is
binding: follow it, do not re-derive it, do not ask about it.

## Scope
Apply to exactly the one posting in your prompt. Do not spawn agents.
Do not write to applications/log.csv. `main` owns it.
Do not edit anything in profile/, qa/, or cv/. They are read-only.

## The gate
Fill and verify the form. Then STOP and send a SUBMIT-REQUEST to `main`.
Submit only after `main` replies APPROVED.

## Escalation
Send `BLOCKED` and wait, on any of the triggers in `apply.md` under "When it
truly cannot proceed". I am your only route to the user. Do not guess.
```

## The agent prompt

Per posting, alongside the brief:

```
You are applying to ONE job on behalf of the user.

FIRST: read <workspace>/.job-apply/briefs/<date>-run.md and follow it exactly.

YOUR JOB:
  Company:   <company>
  Role:      <role>
  Location:  <location>
  URL:       <url>
  Platform:  <ATS, if known>
  Track:     <suggested track>

Name your ego-browser task space "<company>-<role-slug>" and print its numeric
spaceId in every message to me.

Report to me with SendMessage(to="main"). I am your only route to the user.
```

Add anything posting-specific you know: a quirk of that ATS, a framing the user
asked for, a fit concern worth flagging before it writes a cover letter.

Spawn them with the Agent tool, one per posting, as general-purpose agents.
They run in the background and report back by message, so spawn a wave and then
wait on their messages rather than polling.

**The track you suggest is advisory.** The agent picks the track from
`profile/targets.md` per `apply.md`, and your suggestion is a starting point. If
it disagrees, it should say so in its `SUBMIT-REQUEST` rather than silently
overriding you. It cannot ask the user directly, so when it is genuinely torn it
sends `BLOCKED` and you decide.

## The submit gate

**Every subagent stops before submitting and waits for your approval. This is
unconditional and `auto_submit` does not disable it.** `auto_submit` decides
whether *you* approve on the user's behalf or take it to them:

- **`auto_submit: true`** — you approve autonomously, having verified the report
  against `profile/` and `qa/`. The user stays hands-off.
- **`auto_submit: false`** — you batch the pending requests and put them to the
  user in one `AskUserQuestion`, rather than interrupting them once per agent.

The gate is worth its cost. Across one real run of nine agents it caught: a
posting that turned out to be a different company with no application form at
all, a required ethnicity dropdown with no option matching the user's profile, a
university missing from a constrained list, and a question about the user that
was nowhere in the workspace. Every one would otherwise have been submitted
wrong, and a submitted application cannot be withdrawn.

Expect momentum to work against the gate. An agent forty tool calls into a form
wants to finish. Hold the line.

### Message formats

Agents send four, all specified in `apply.md` so they are readable by an agent
that never sees this file: `SUBMIT-REQUEST` before submitting, `SUBMITTED` after,
`BLOCKED` when it needs something, and `ABORTED` when you call it off. Each
carries its task space id and application folder, and the two terminal ones carry
a ready-to-append `log-row`.

**Your replies to a `SUBMIT-REQUEST`** — exactly one of:

- `APPROVED` — submit now
- `CORRECT: <field> = <value>` (repeatable), then re-verify and re-request
- `ABORT: <reason>` — do not submit, report `ABORTED`, stand down

**Your replies to a `BLOCKED`** — answer the question, give it something specific
to try, take the application over yourself, or `ABORT` it. Answer from the
workspace where you can. Where you cannot, it is your call whether to ask the
user now or park the application: under `auto_submit: false` you are batching
questions anyway, so add it to the batch and tell the agent to wait or stand
down.

**Do not let `CORRECT` cycle forever.** Two rounds on the same field is enough.
If it still will not hold, the field is the problem, not the agent: `ABORT` to
`incomplete` and take it to the user with the rest of the batch. A field that
cannot be made to read back correctly is exactly the case the gate exists for.

### What to check before approving

You have the profile loaded and the agent does not have your overview. Check:

- Authorization answers are not inverted. "Authorized to work" and "requires
  sponsorship" are different questions with different answers.
- Salary is consistent with any band the posting stated.
- Demographic answers match `profile/demographics.md`, including the refusals.
- Location follows the identity rule rather than the office's city.
- Every upload is confirmed by a displayed filename, not by an empty check.
- The cover letter has no em dashes and no fabricated claim.

Approving without reading is worse than not gating, because it produces a record
that says someone checked.

## Owning the log

**You write every row in `applications/log.csv`. Agents never open it for
write.** Concurrent appends from several processes interleave and corrupt rows,
and a corrupt log breaks the duplicate check that every future application
depends on.

The agent sends its row as text in `SUBMITTED`; you append it. The agent
composes it because it knows things you do not, like how many questions it had
to ask and what was odd about the form. Run the column-count check from
`apply.md` Phase F after each append.

**Write a row for every agent you spawned, including the failures.** A closed
posting gets `failed`. An agent that aborted gets `incomplete` with the reason in
`notes`. A log that records only successes cannot answer the question it exists
to answer, which is what happened to all of them.

`SUBMITTED` and `ABORTED` both carry a `log-row`, so in the normal case you are
appending text the agent composed. When you have to write one yourself, because
an agent was stopped or went silent, fill what you know from your in-flight list
and put the reason in `notes` rather than leaving the posting unrecorded.

## Task spaces

One per agent, named `<company>-<role-slug>`, with the numeric `spaceId` carried
in every message. Never a second space for the same job, and never a new space to
escape a stuck page.

**All spaces share the browser profile's cookie jar.** That is mostly a gift: a
site the user is logged into is available to every agent at once, and a login
performed once serves the whole run. It also means an agent that signs out of
something, or clears state, breaks every sibling. Nobody clears browser state.

**Do not use clipboard paste under parallelism.** It goes through the real system
clipboard, which is a single global resource, so two agents pasting at the same
moment can put one user's cover letter into another application. Type or fill
instead.

When an agent needs a login you can perform, have it hand the browser over,
resolve it, and hand the *same* space back by id rather than starting fresh.

## When things go wrong

**Posting closed.** The agent checks before creating any files, so this costs
nothing. It sends `BLOCKED`; reply `ABORT`, log `failed`, move on.

**Agent stuck.** After three failed attempts on the same element it sends
`BLOCKED`. You have an advantage it does not: you may have watched a sibling
agent solve the same ATS ten minutes ago. Pass that on. Otherwise give it a
specific thing to try, take the job over yourself, or `ABORT` it to `incomplete`.

**Never spawn a replacement for a posting whose original agent still holds a task
space.** Two agents on one posting is how the same job gets applied to twice.
Stop the first, confirm it has actually stopped, then respawn against the
existing space by id rather than starting a fresh one.

**Agent silent.** Your in-flight list tells you who you have not heard from.
Ask before stopping: an agent mid-upload looks exactly like a wedged one, and a
wall-clock threshold will be wrong in both directions. If it is genuinely wedged,
stop it, log `incomplete`, and leave its task space alone so the filled form
survives.

A blocked agent holds a slot. If you are at the cap and waiting on an answer you
cannot give yet, park that application rather than letting it stall the queue:
`ABORT` it to `incomplete`, note what it needs, and revisit once the wave is
through.

## While the agents run

1. **Stay responsive.** Approval latency is the bottleneck, and a waiting agent
   is a browser session going stale and an ATS session edging toward timeout.
   Prioritise gate messages over everything else.
2. **Verify rather than rubber-stamp**, per the checklist above.
3. **Append the log row** on each `SUBMITTED`.
4. **Cross-pollinate.** When one agent works out an ATS quirk, tell the others on
   the same platform. You are the only one who can see across them.
5. **Do not drive a browser yourself** while orchestrating, unless taking over an
   aborted application. An orchestrator filling in a form is an orchestrator not
   answering gates.
6. **Harvest reusable answers once, at the end**, across the whole run. Five
   agents each offering to save "what is your notice period" is five
   interruptions for one answer.

## Reporting back

When the run finishes, tell the user: what was submitted with its confirmation,
what failed and why, what is still awaiting something, and every question that
came up. Then offer the harvested answers for `qa/answers.md`.
