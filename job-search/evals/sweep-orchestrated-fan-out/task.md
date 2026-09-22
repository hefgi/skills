# Sweep several sources in parallel and merge them once

## Problem/Feature Description

The user has a configured search with several boards and wants the pipeline
filled quickly. Sweeping the sources one after another wastes most of the run
waiting on the network, so the work fans out: one subagent per source, reporting
back to an orchestrator that merges what they bring.

Fan-out is where a sweep can quietly corrupt itself, and the scenario exists to
test the three places that happens:

- **Shared files.** Every agent writing one accumulated harvest to one path
  means the last writer wins and the others' rows vanish with no error. Each
  agent owns exactly one shard.
- **Shared session.** All ego-browser task spaces share one cookie jar, so two
  agents on one domain are one fast session to that site, and the per-run request
  budget, the randomized delay, and the three-strikes counter all stop meaning
  what they say. The public JSON APIs are not a session at all and carry none of
  this.
- **Dedup.** The same job cross-posted to two boards now arrives from two
  different agents. It is still one job.

## Setup

Serve the board fixtures on port 8899 from the `fixtures/` directory:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy `fixtures/workspace/` somewhere writable and run against the copy. It has a
configured `profile/search.md`, a populated `applications/log.csv`, and a
`search/pipeline.csv` with rows from an earlier run.

The LinkedIn fixture and the Ashby fixture each carry one half of the same job:
`linkedin-results.html` lists "Forward Deployed Engineer" at Hilbert Systems, and
`ashby-board.html` lists "Forward Deployed Engineer (UK)" at the same company
under a different URL. Two agents will find it independently.

## The user's message

> Sweep everything in parallel, I don't want to wait for the boards one at a
> time. Fill the pipeline.

## Output Specification

An updated `search/pipeline.csv` and a run report under `search/runs/`, both
written only by the orchestrator, with one shard file per agent left behind or
cleaned up after a successful merge. The pipeline must be indistinguishable from
what a single serial sweep over the same rows would have produced.
