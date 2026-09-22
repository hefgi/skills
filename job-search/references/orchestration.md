# Workflow 3: Sweep many sources at once

A sweep is mostly waiting on the network. One agent working through sources in
sequence spends nearly all its time on requests that could have been in flight
together. Spawning one subagent per source turns a long serial run into a short
parallel one.

You are the **orchestrator**, called `main` throughout this file. You do not
drive a browser. You plan the run, spawn agents, answer their questions, review
what they bring back, and own every write to the workspace.

**Establish how agents reach you before spawning anything, and verify it from
the messaging tool's own contract rather than assuming.** A subagent that blocks
mid-sweep and sends to a name that does not resolve is stranded, and a stranded
sweep agent is worse than a stranded application agent: an agent that cannot ask
what to do about a LinkedIn challenge may decide alone and retry into a block on
the user's real account.

In a harness where background subagents address the parent conversation as
`main`, that string is both this file's name for you and a real address, and
nothing needs substituting. Say so in the brief in as many words, because an
agent reading `main` in a document that uses angle-bracket placeholders elsewhere
may reasonably take it for one and try to substitute something.

Where the parent is not addressable that way, find the identifier that does
resolve and put that literal value in the brief and in every prompt. Fixing only
the prompts is a half fix: an agent that trusts the brief sends to the wrong
place.

Either way, tell agents never to reply to the sender label on an incoming
message. That is typically an agent type, not an address, and sending to it
fails.

If you cannot establish a reachable address at all, say so and run the sweep
yourself in sequence per `search.md`. Fan-out without a return path is worse than
serial work.

Read this file only as the orchestrator. Subagents read `search.md`,
`sources.md`, and the `ego-browser` skill. **Never give a subagent this file**:
an agent that reads "spawn one agent per source" will fan out again.

## Contents

- [Deciding whether to fan out](#deciding-whether-to-fan-out)
- [The two tiers](#the-two-tiers)
- [Before spawning anything](#before-spawning-anything)
- [The run brief](#the-run-brief)
- [The agent prompt](#the-agent-prompt)
- [Reviewing what comes back](#reviewing-what-comes-back)
- [Merging and upserting](#merging-and-upserting)
- [Owning the shared writes](#owning-the-shared-writes)
- [Task spaces and the shared session](#task-spaces-and-the-shared-session)
- [When things go wrong](#when-things-go-wrong)
- [Reporting back](#reporting-back)

## Deciding whether to fan out

Judgement, not a formula.

**Fan out when** there are enough sources that serial work would take long
enough to matter. The clearest case is a workspace with a long
`profile/boards.md`: nineteen board slugs is nineteen independent HTTP fetches, and
sharding those across agents is nearly free.

**Stay serial when:**

- The run is one or two sources. Two sequential fetches finish before two
  spawned agents have finished reading the skill.
- Ego lite is not verified working yet. Debug it once yourself rather than
  watching three agents fail the same way.
- The user asked for a quick top-up of one board.

There is **no submit gate here, and that is the important difference from
`job-apply`.** That skill gates every application because a submitted
application cannot be withdrawn. A sweep reads pages and returns rows; nothing
it does is irreversible. Do not port the gate. It would add latency and no
safety, and an orchestrator waiting on approvals it does not need is an
orchestrator not reviewing harvests.

## The two tiers

The split is by what a source touches, not by how fast it is.

### Tier 1: no browser, no session, fan out freely

Ashby boards, Greenhouse boards, and career-page ATS probes. `sources.md` says
it directly: "Neither API needs a logged-in session, so a plain Node `fetch()`
outside the browser works too."

These agents open **no ego-browser task space at all**. That is what makes them
free to parallelise: with no space, they cannot touch the shared cookie jar,
cannot be challenged, and cannot affect a sibling. They are plain HTTP against
public endpoints that are not the user's accounts.

Shard the slug list across agents. With sixteen slugs, three to five agents is
the right size: enough to parallelise, few enough that each still does real work.

Cap: `max_concurrent_sweeps` in `.job-apply/config.yaml`, default 6.

### Tier 2: one task space each, one agent per domain

LinkedIn, YC, Wellfound, Google, and bespoke career pages. These drive the
user's real logged-in session.

Cap: `max_concurrent_browser`, default 3. And one rule that is not negotiable:

**Never two agents on one domain.** LinkedIn always has exactly one agent. This
is not caution about ego lite, which handles many spaces fine. It is that
`search.md`'s pacing rules are written per *run*, and splitting a domain quietly
breaks three of them at once:

- The per-source request budget becomes N times what it says.
- The 3 to 6 second randomized delay degrades into a faster aggregate cadence.
  Three agents each politely waiting 3 to 6 seconds produce a combined 1 to 2
  second rhythm at the session, which is both quicker and more regular than the
  fixed gap the rule specifically warns against.
- The three-strikes counter is per-source state. Two agents each reaching two
  strikes means neither retires, and the sweep grinds against a dead board.

Keep one agent per domain and all three rules keep meaning what they say, with
no modification.

## Before spawning anything

**Reconcile first**, per `search.md` Phase A. Do it once, yourself, before any
agent exists. Everything applied to since the last sweep is then already marked,
so no agent wastes a request on it.

**Plan the queries**, per `search.md` Phase B, and shard them. Agents receive a
concrete work order, not a set of criteria to interpret. Deciding centrally is
also what keeps the per-domain budgets coherent.

**Load the workspace** into your own context: `profile/search.md`,
`profile/targets.md`, `applications/log.csv`. You need them to review what agents
report, and you are the one who will run `upsert`.

**Check nothing else is driving the browser.** `search.md` says not to sweep
while an application is in progress. Under fan-out that collision is likelier,
so run `listTaskSpaces()` and look before spawning.

**Keep an in-flight list.** Nothing on disk shows what is being worked on
mid-run. Track per agent: the source, the domain, its tier, its task space id if
tier 2, requests used against budget, strikes so far, and its state
(`spawned`, `sweeping`, `blocked`, `returned`, `retired`). Use it to notice an
agent you have not heard from, and to answer the question that matters when
something blocks: who else is on that domain?

**Write the run brief**, once, before the first spawn.

## The run brief

Write it to `<workspace>/.job-apply/briefs/<YYYY-MM-DD>-sweep.md`, composed fresh
from the current skill and the current criteria.

**The brief is a pointer and a work order. It is not a copy of the rules.** It
names which files to read and what one source to sweep. It never restates what
`search.md` and `sources.md` say, because a second copy drifts from the first and
an agent that finds two versions of an instruction wastes its turns deciding
which to believe. When the skill changes, every agent picks the change up on its
next spawn, because it reads the skill rather than a copy.

Date the file rather than overwriting a fixed name, so a stale brief is visibly
stale and you are never rewriting a file that running agents are reading.

```markdown
# Sweep brief: <YYYY-MM-DD>

Read these in full before anything else, and follow them exactly:
  <skill>/references/search.md
  <skill>/references/sources.md
  the `ego-browser` skill, only if your source is tier 2

They are the rules. This brief does not restate them.

Workspace: <absolute path>
Run id:    <run-id>
Today:     <YYYY-MM-DD>

## Precedence
profile/search.md holds decisions already made. A `#` comment above a key is
binding: follow it, do not re-derive it, do not ask about it.

## How to reach me
Send with SendMessage(to="main"), exactly as written.

`main` is a real address, established from the messaging tool's contract and
confirmed working. It is NOT a placeholder: do not substitute anything for it.
(Replace this whole line with your actual address before writing the brief if
`main` is not what resolves in your harness, and say the same thing about it.) Use it for every message including replies.
Never send to the sender label on a message you receive: that is an agent type
and will not resolve.

## Scope
Sweep exactly the one source in your prompt. Do not spawn agents.
Write your rows to your own shard file and nothing else.

Do NOT run `pipeline.py upsert`. Do NOT write search/pipeline.csv.
Do NOT edit profile/search.md or profile/boards.md.
Do NOT write the run report. The orchestrator owns all of those.

Report discovered ATS slugs to me in a SLUGS message instead of writing them.

## Do not filter
Collect everything with title similarity. Do not drop blockers, do not dedupe
against the log, do not decide a row is a duplicate. One place decides what gets
dropped, and it is the orchestrator's single upsert. Filtering in an agent makes
the run report's counts untrue.

## Your shard
Write to: <workspace>/search/runs/<run-id>.<source>.partial.json

  {"rows": [...], "blocked": [...], "slugs": [...]}

Rewrite the whole file as you go. It is the only state that survives, and it is
yours alone: never write another agent's shard or a shared file.

## Messages
Formats are in search.md under "Messages to an orchestrator". Send HARVEST when
done, BLOCKED the moment a source challenges you, RETIRED on three strikes,
SLUGS for newly discovered boards.

## If you are blocked
Stop that source immediately. Do not retry, do not try to solve a challenge, do
not fall back to an unauthenticated fetch. Send BLOCKED with the exact URL and
say whether it was a challenge or a login wall. Then wait. I am your only route
to the user.
```

## The agent prompt

Per source, alongside the brief:

```
You are sweeping ONE job source on behalf of the user.

FIRST: read <workspace>/.job-apply/briefs/<date>-sweep.md and follow it exactly.

YOUR SOURCE:
  Source:   <ashby | greenhouse | linkedin | ai-boards | career-pages>
  Tier:     <1 = plain fetch, no browser | 2 = one ego-browser task space>
  Targets:  <the slugs or query terms assigned to you, verbatim>
  Budget:   <requests allowed, from search.md Pacing>
  Shard:    <workspace>/search/runs/<run-id>.<source>.partial.json

<tier 1 only>
Do not open an ego-browser task space. Use plain Node fetch(). Your endpoints
are public and need no session.

<tier 2 only>
Name your ego-browser task space "sweep-<source>" and print its numeric spaceId
in every message to me. You are the ONLY agent on <domain>. The pacing in
search.md is yours alone to consume, so follow it exactly.

Report to me with SendMessage(to="<address>"), the same one the brief gives.
I am your only route to the user. Use it every time, including when replying,
and never send to the sender label on an incoming message.
```

Spawn with the Agent tool, as general-purpose agents. They run in the background
and report by message, so spawn a wave and wait on messages rather than polling.

Add anything source-specific you know: a slug that 404'd last run, a board that
renders late, a quirk a sibling already worked out.

## Reviewing what comes back

This is the review the user asked for, and it is a check on the **batch**, not on
each job. Individual jobs are decided deterministically by `upsert`; what a
machine cannot judge is whether a harvest is real.

Per `HARVEST`, before accepting it:

**1. Extraction sanity.** `sources.md` documents the signature: a card with no
location means the extraction missed it, not that the posting has no location. A
batch where every row lacks a location is a broken selector, not data. This is
not hypothetical: it shipped once, and it silently dropped the work
authorization text that the `us-work-auth` blocker reads, so a US-only posting
would have entered the pipeline as an ordinary row. Reject the batch and have the
agent re-extract against the recipe.

**2. Blocked reported honestly.** A source that returned nothing must say which
it was: swept and empty, or blocked. `search.md` is emphatic that these lead to
different actions. An agent reporting zero rows with no blocked entry and no
explanation gets asked before its batch is accepted.

**3. Plausibility.** Roles look like job titles, companies like companies, URLs
point at the domain the agent was assigned. A row whose company is the ATS
vendor rather than the employer means the slug resolution went wrong, and that
corrupts `job_key` permanently.

**4. Budget respected.** Compare requests used against what you allocated. An
agent well over budget on a tier 2 domain is the early warning for a challenge.

What you do **not** do is read every row and decide keep or drop. A sweep returns
hundreds of rows; a per-row gate would either take an hour or become a
rubber stamp, and it would re-introduce exactly the judgement the no-scoring
decision removed.

## Merging and upserting

**Only you run `upsert`, and it runs exactly once.** Two concurrent upserts each
read the pipeline and write it back, so the second silently discards the first.
The run-level `--max-new` cap would also be applied N times.

```bash
"$PIPELINE" merge \
  --shard "$W/search/runs/<run-id>.ashby.partial.json" \
  --shard "$W/search/runs/<run-id>.linkedin.partial.json" \
  --shard "$W/search/runs/<run-id>.greenhouse.partial.json" \
  --out   "$W/search/runs/<run-id>.merged.json"

"$PIPELINE" upsert \
  --pipeline "$W/search/pipeline.csv" \
  --log      "$W/applications/log.csv" \
  --criteria "$W/profile/search.md" \
  --run-id   "<run-id>" \
  --max-new  60 \
  < "$W/search/runs/<run-id>.merged.json"
```

**Keep the shards after a successful upsert; delete only the merged file.**
`search.md` Phase E says to delete the scratch `.partial.json`, which is right
for a serial run where that file is a resumption checkpoint and nothing else.
Under fan-out the shards are the only record of which agent found what, and the
report is generated from the pipeline rather than from them, so deleting them
throws away the audit trail. If you do delete them, carry the per-agent counts
into the report first.

`merge` also collects every shard's `blocked` and `slugs` lists, deduplicated,
and flags empty shards. Read that summary: an empty shard you were not expecting
is worth a question before the upsert, not after.

**Dedup across agents needs nothing from you.** `upsert` resolves all three axes
in one pass, and it is order-independent: the same rows merged in either order
produce the same row with the same `job_key` and both URLs retained. Only which
URL becomes canonical differs. A fan-out run and a serial run over the same rows
produce an identical pipeline.

Report the counts it prints rather than reciting rows: added, `cross_post_merged`
(the same job found by two agents), `already_applied`, `seen_again`, dropped by
reason. Name individually only what needs a human: rows `upsert` flagged as
ambiguous on track, and any near-match it deliberately kept as two rows.

## Owning the shared writes

**You write `search/pipeline.csv`, the run report, and `profile/search.md`.
Agents write only their own shard.**

Each is a read-modify-write that corrupts under concurrency. The pipeline loses
rows. `profile/boards.md` loses slugs: agents send `SLUGS`, you merge them once,
at the end, after the upsert, with `pipeline.py boards --add-company`.

Write the report with every blocked source named, per `search.md` Phase F, using
one `--blocked` flag per source.

**Write a shard's worth of truth for every agent you spawned, including the
failures.** An agent that went silent or was stopped still happened. Put it in
the report as blocked or unknown rather than letting it vanish, for the same
reason `job-apply` logs failed applications: a record that only shows successes
cannot answer the question it exists to answer.

## Task spaces and the shared session

Tier 1 agents have no task space. Tier 2 agents have one each, named
`sweep-<source>`, with the numeric `spaceId` in every message.

**All spaces share the browser profile's cookie jar**, and so do the user's own
tabs. Ego lite handles many concurrent spaces without trouble; the shared jar is
mostly a gift, since a site the user is logged into is available to every agent
at once. It also means an agent that signs out of something breaks every sibling.

**Nobody clears browser state.** A profile-wide cookie clear is unrecoverable and
reaches the user's own tabs. This is the one action in a sweep that can do real
damage, and no sweep ever needs it.

**One agent per domain**, for the pacing reasons above. Never a second space for
the same source, and never a new space to escape a stuck page.

## When things go wrong

**A source challenges an agent.** The agent stops itself and sends `BLOCKED`.
Your job is the part it cannot do: **a challenge is evidence about the session,
not about that agent.** Check the in-flight list for anyone else on that domain
and halt them too. Then record it as blocked and let the run continue. Do not
respawn against the same domain this run.

This propagation is the main safety reason to orchestrate a sweep at all. You
are the only party that can see across agents.

**An agent is stuck.** After three strikes it sends `RETIRED`. You may have
watched a sibling solve the same board shape minutes ago, so pass that on. This
cross-pollination is not an optimisation here; it is how one agent's discovery
becomes everyone's.

**An agent is silent.** The in-flight list tells you who. Ask before stopping: an
agent mid-pagination looks like a wedged one. If it is genuinely wedged, stop it,
record its source as incomplete in the report, and leave its shard alone. The
rows it did write are still good and `merge` will pick them up.

**Never spawn a replacement for a source whose agent still holds a task space.**
Two agents on one domain is exactly the case the tiering exists to prevent. Stop
the first, confirm it stopped, then respawn.

**An agent returns a broken batch.** Ask it to re-extract once against the
recipe in `sources.md`. If the second attempt is also broken, the recipe is the
problem rather than the agent: record the source as blocked, say what the
extraction returned, and flag the recipe to the user. Do not accept a batch you
know is wrong to keep the run moving, and do not silently drop it either.

## Reporting back

When the run finishes, tell the user: how many new rows and from which sources,
the drop counts by reason, which sources were blocked and at which URL, anything
that reappeared, and any slug additions. Then how to apply to what was found,
per `references/handoff.md`.

Say plainly if a source was never swept. A fan-out run that quietly covered four
of five sources looks the same as one that covered all five, and the difference
is a board the user thinks is dry.
