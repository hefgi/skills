# Workflow 2: Sweep

Find live postings and merge them into the pipeline. Produces new rows in
`search/pipeline.csv` and a report in `search/runs/`.

The phases run in order. Reconciling before sweeping is what stops the run
offering jobs already applied to, and buffering until the end is what lets one
job cross-posted to two boards collapse into one row.

## Contents

- [Phase A: load and reconcile](#phase-a-load-and-reconcile)
- [Phase B: plan the queries](#phase-b-plan-the-queries)
- [Phase C: open the browser](#phase-c-open-the-browser)
- [Phase D: sweep each source](#phase-d-sweep-each-source)
- [Phase E: upsert](#phase-e-upsert)
- [Phase F: report and finish](#phase-f-report-and-finish)
- [Pacing](#pacing)
- [When a source blocks](#when-a-source-blocks)
- [Harvest format](#harvest-format)
- [Messages to an orchestrator](#messages-to-an-orchestrator)

## Phase A: load and reconcile

Read `profile/search.md`, `profile/targets.md`, `profile/logistics.md`, and
`.job-apply/config.yaml`. If `search.md` is missing or empty, run Setup first.

Then reconcile, before anything else:

```bash
scripts/pipeline.py reconcile --pipeline "$W/search/pipeline.csv" \
                              --log "$W/applications/log.csv"
```

This marks rows **already in the pipeline** that have since been applied to. It
does not back-fill the whole application log, so a reconcile reporting `0` on a
log of a hundred applications is normal and not a failure: it means none of them
matched a row the pipeline was already tracking. Jobs applied to but never in the
pipeline are caught later, by axis-1 dedup during `upsert`.

Running it first is what guarantees a job is never offered twice: by the time new
rows are evaluated, everything already submitted is marked.

Pick a run id: `<ISO date>-<n>`, incrementing `n` if a sweep already ran today.

## Phase B: plan the queries

Build the query list before opening a browser, so the browser time is spent
fetching rather than deciding.

- **Terms**: `query_terms_<track>` from `search.md`, one query per term per
  source that supports search. Weight the tracks by their ratio in the
  application log, since that is how the user splits their real effort.
- **Locations**: from `geography`.
- **Sources**: `sources:` order from `search.md`, minus `sources_disabled`.
  The order matters because a run that gets cut short should already have swept
  the most productive board.
- **Recency**: bound it. A weekly sweep that does not filter by date re-reads
  the same postings every time and finds nothing new for the cost of everything.

Tell the user the plan in one line before starting: how many queries, which
sources, and roughly how long. A sweep is slow by design, and a user who knows
that will not interrupt it at source three.

## Phase C: open the browser

**Check ego lite is ready before the first browser call**, not after. Phases A
and B have already read the workspace and planned the queries by this point, and
discovering here that the browser is missing wastes that and strands the user
mid-sweep:

```bash
export PATH="$HOME/.local/bin:$PATH"
ego-browser nodejs -e 'console.log("READY")'
```

Anything other than `READY` means stop and work through
`SKILL.md`'s [Setting up ego lite](../SKILL.md#setting-up-ego-lite), which covers
the skill being absent, the binary not being on the PATH, and what each failure
actually means. Install is a one-time setup with a GUI step only the user can
do, so it is a conversation, not a retry.

**Read the `ego-browser` skill before the first browser call.** It is the
browser manual: task spaces, snapshots, refs, actions, waiting, and its own
escalation ladder for a stuck page. This skill does not restate any of it. What
follows is only what is specific to sweeping job boards.

Open one task space for the whole sweep, named for the run:

```bash
ego-browser nodejs -e '
const task = await taskSpace("job search sweep 2026-09-21-1");
const page = task.page("p1");
await page.goto("https://jobs.ashbyhq.com/example");
console.log({ spaceId: task.spaceId });
console.log(await page.snapshot());
'
```

Print the `spaceId` and reuse it for every later round. One space for the whole
sweep, not one per source: a sweep is a single user goal, and a fresh space per
board loses the accumulated session state and costs a startup each time.

Navigate the same page between sources with `goto()` rather than opening a page
per board. A sweep visits dozens of URLs, and a page each would exhaust the page
budget long before the run finished.

The user's logged-in sessions are what make gated boards readable. They come
from the Chrome import during ego lite onboarding. **Probe rather than assume**:
if LinkedIn or Y Combinator shows a login wall, that source is blocked for this
run. Report it, do not try to work around it.

**Do not run a sweep while an application is in progress.** `job-apply` drives
its own task space, and a sweep is a long sequence of navigations. Finish or
abandon one before starting the other, or the two compete for the same browser.

## Phase D: sweep each source

`references/sources.md` has the URL patterns, extraction selectors, and failure
modes for each. The loop is the same everywhere:

1. Build the URL from the plan.
2. `goto`, then extract the result list.
3. Normalize each result into a harvest row.
4. Paginate up to `max_pages_per_query`.
5. Append to the in-memory harvest.

**Checkpoint after each source**, so a run that dies at source four keeps the
first three. Write the whole accumulated harvest each time, overwriting:

```bash
python3 - "$W/search/runs/<run-id>.partial.json" <<'PY'
import json, sys
harvest = [
  {"company": "Hilbert Systems", "role": "Forward Deployed Engineer",
   "url": "https://jobs.ashbyhq.com/hilbert/cccc3333", "platform": "ashby",
   "location": "London, United Kingdom", "work_mode": "hybrid", "source": "ashby"},
  # ...every row gathered so far, from every source completed
]
json.dump(harvest, open(sys.argv[1], "w"), indent=2)
PY
```

The file is the only state that survives between rounds: each `ego-browser`
invocation is a new process, so nothing in JavaScript persists. Re-serialize the
full accumulated list rather than appending one source's rows, because a partial
file that omits earlier sources loses exactly what the checkpoint exists to keep.

**Under a fan-out run, each agent writes its own shard**, named
`<run-id>.<source>.partial.json`. One shared file would mean every agent writing
the whole accumulated list to one path, so the last writer wins and everyone
else's rows vanish silently. The orchestrator concatenates the shards with
`pipeline.py merge` before the single upsert.

**Checkpoint the blocked sources too.** A blocked source contributes no rows, so
it exists only in your head between here and the report. If the run dies in
between, the harvest survives and the blocked list does not, which is the one
fact this skill is most insistent on not losing. Keep them alongside the rows,
in a file the next round can read:

```json
{"rows": [...], "blocked": ["linkedin: challenge at https://..."]}
```

Feed `rows` to `upsert` and `blocked` to `report`.

Extract the fields listed under [Harvest format](#harvest-format). Anything
missing beyond those is fine: `pipeline.py` fills sensible defaults, and a
results page genuinely does not carry a full posting body. Do not open every
posting to enrich a row. That multiplies the request count by twenty for detail
that `job-apply` will read properly at application time anyway.

**Do not filter while sweeping.** Collect everything with title similarity and
let `upsert` apply the blockers. One place deciding what gets dropped is what
makes the run report's counts true.

**A track restriction is a planning decision, not a filter.** When the user asks
for one track, that narrows the query terms in Phase B: you run
`query_terms_fde` and not `query_terms_leadership`. It does not mean discarding
a role a source hands back. Those are different things and conflating them
breaks one rule or the other.

So a leadership title arriving from a board you swept for FDE terms is kept, and
`upsert` tracks it as `leadership`. It is a real opening the user can act on, and
throwing it away because of how the query was phrased would lose a job for a
bookkeeping reason. Say in the report that the run was scoped to one track, so
the counts are read in that light.

## Phase E: upsert

Once every source has been swept or retired, merge the whole run at once:

```bash
scripts/pipeline.py upsert \
  --pipeline "$W/search/pipeline.csv" \
  --log      "$W/applications/log.csv" \
  --criteria "$W/profile/search.md" \
  --run-id   "<run-id>" \
  --max-new  60 \
  < "$W/search/runs/<run-id>.partial.json"
```

It dedups on all three axes, applies the blockers, infers the track, and prints a
JSON summary. Read the summary: `ambiguous_track` lists rows it refused to guess
on, and `over_cap` says how many were left out by `--max-new`.

If `over_cap` is non-zero, say so in the report. A cap that silently discards
findings makes the next sweep look like it found nothing new.

Delete the `.partial.json` once the upsert succeeds.

## Phase F: report and finish

```bash
scripts/pipeline.py report --pipeline "$W/search/pipeline.csv" \
  --run-id "<run-id>" \
  --blocked "linkedin: checkpoint challenge at https://www.linkedin.com/checkpoint/challenge/x" \
  --blocked "ai-boards: YC login wall" \
  --out "$W/search/runs/<run-id>.md"
```

**Finish the task space with `task.finish({ keep: [] })` once the sweep is
genuinely done**, and only then. A sweep visits pages rather than producing
anything in the browser, so there is normally nothing worth keeping open.

Leave it open when something is outstanding: a source part-swept, a login the
user is about to complete, or a board you want them to look at themselves. It
still holds the pages, and closing it to tidy up throws away the state the next
round needs.

Then tell the user, in a few lines: how many new rows, the drop counts by
reason, which sources were blocked, and how to apply to what was found. Point at
`references/handoff.md` for the last part.

Report blocked sources even when the run went well otherwise. That is the piece
the user needs to act on themselves.

## Pacing

These are the user's real accounts. A throttled LinkedIn session costs them
hours of their own browsing, not just this run.

| Source | Budget per run |
|---|---|
| Ashby, Greenhouse | Unbounded via their JSON APIs. These are public endpoints with no anti-bot, and the user's own boards. |
| LinkedIn | 6 queries, 3 pages each, 25 results per page |
| YC, Wellfound | 2 queries and 1 query respectively, best effort |
| Google | 3 queries, and only for discovering board slugs |

- **Delay 3 to 6 seconds between LinkedIn page loads**, randomized. A fixed
  cadence is itself a bot signal, so an exact 5-second gap is worse than a
  varying one.
- **Serial within a domain, never two agents on one.** One request at a time
  against a given site. Concurrent loads against a single session are the
  fastest route to a challenge page, and every budget and delay on this page is
  written per *run*: split a domain across two sweepers and the request budget
  doubles, the randomized delay collapses into a faster aggregate cadence, and
  the strike counter below stops reaching three. Different domains in parallel
  are fine, and the public JSON APIs are not a session at all. See
  `references/orchestration.md` for how a fan-out run keeps this true.
- **Three strikes per source.** An empty extraction or a timeout is a strike.
  Three retires that source for the run. This stops a sweep grinding against a
  board that has already decided to stop answering.

  **A challenge or a login wall is not a strike, it is an immediate stop.**
  Strikes are for a board that might answer next time. A checkpoint page has
  already decided, and hitting it twice more is what turns a soft throttle into
  a long block. See [When a source blocks](#when-a-source-blocks).

## When a source blocks

A login wall, a CAPTCHA, a consent interstitial, or a challenge page.

**Stop that source immediately.** Do not retry in a loop, do not try to solve it,
and do not fall back to fetching the same page unauthenticated. Repeated hits on
a session that has just been challenged is what turns a soft throttle into a
long block.

Then: continue with the remaining sources, record the blocking URL, and put it in
the report's blocked section. The user can open that URL in their own browser,
clear the challenge in five seconds, and the next sweep works.

**Report blocked separately from empty.** "LinkedIn: 0 results" and "LinkedIn:
blocked at a checkpoint" lead to completely different actions, and collapsing
them tells the user a board is dry when it is merely guarded.

If the user takes control of the browser, or the task space becomes inactive or
unassigned, stop. Do not retry or route around it. Keep the partial, say which
sources were completed, and pick the sweep up in the same space afterwards.

**A task space that no longer exists is a different case.** `task space not
found` means there is nothing to resume and nothing to hand back, so the rule
against opening a new space to escape a stuck page does not apply: there is no
stuck page. Open a fresh space, say so, and carry on from the checkpoint. Check
`listTaskSpaces()` first to be sure it is gone rather than merely busy, because
recovering from a space the user is still using would take the browser out from
under them.

## Harvest format

The JSON array fed to `upsert`. One object per posting:

```json
[
  {
    "company": "Cohere",
    "role": "Forward Deployed Engineer, Agentic Platform",
    "url": "https://jobs.ashbyhq.com/cohere/2d256112",
    "platform": "ashby",
    "location": "London, UK",
    "work_mode": "hybrid",
    "source": "ashby",
    "notes": ""
  }
]
```

`company`, `role`, and `url` are required, and `upsert` exits non-zero if any is
missing rather than writing a row that cannot be identified or acted on.
`work_mode` is `remote`, `hybrid`, `onsite`, or `unknown`; `unknown` is honest
and common from a results page. Leave `track` out: it is inferred.

Put anything the listing said about work authorization into `notes`. That is
where the `us-work-auth` blocker looks, and a results page occasionally says
"US-based only" right in the card.

## Messages to an orchestrator

When an orchestrator spawned you to sweep one source, you report to it rather
than to the user. The formats live here, not in `orchestration.md`, so an agent
that never sees that file still knows them.

Send `SendMessage(to="<the address in your brief>")`, never to the sender label
on a message you receive.

**`HARVEST`** when your source is done:

```
HARVEST | <source>
shard:    <path to your .partial.json>
rows:     <count>
space:    <spaceId, or "none" for a plain-fetch source>
requests: <how many you used, against the budget you were given>
notes:    <anything odd: a slug that 404'd, a board that rendered late>
```

**`BLOCKED`** the moment a source challenges you. Send it and wait:

```
BLOCKED | <source>
url:  <the exact URL that blocked>
kind: challenge | login-wall | throttled
```

The `kind` matters to the orchestrator, because a challenge is evidence about
the shared session rather than about you, and it may need to halt other agents.

**`RETIRED`** after three strikes on a source, per the pacing rules above.

**`SLUGS`** for ATS boards you discovered:

```
SLUGS | ashby:hilbert, greenhouse:euler
```

Report them rather than writing them. `profile/search.md` is a read-modify-write
file and concurrent edits clobber each other, so the orchestrator merges once.

**Your scope as a subagent**: sweep the one source you were given, write only
your own shard, and do not filter. Never run `pipeline.py upsert`, never write
`search/pipeline.csv` or the run report, never edit `profile/search.md`. One
place decides what gets dropped, and it is the orchestrator's single upsert.
