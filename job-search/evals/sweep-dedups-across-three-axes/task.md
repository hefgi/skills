# Sweep the boards and deduplicate across three axes

## Problem/Feature Description

The user has a configured search and wants their pipeline filled. The work is a
sweep of several boards followed by reconciliation, and the reconciliation is
where it goes wrong.

Three kinds of duplicate have to be collapsed, and they are different problems:

- **Already applied.** A role sitting in `applications/log.csv` must not be
  offered again as new.
- **Cross-posted.** The same job listed on two boards is one role, not two, and
  the second URL is worth keeping.
- **Seen before.** A row already in `pipeline.csv` from an earlier run keeps its
  history rather than being reset by re-seeing it.

Two postings must be dropped rather than surfaced: one requires US work
authorization the profile does not have, and one is junior. Dropped rows stay in
the CSV with a reason, because a pipeline that silently deletes rows cannot
explain itself on the next run.

There is no ranking. The user's stated position is that anything with a genuine
similarity is worth applying to, so no score, fit, or match column exists.

## Setup

Serve the board fixtures on port 8899 from the `fixtures/` directory:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy `fixtures/workspace/` somewhere writable and run against the copy. It has a
configured `profile/search.md`, a populated `applications/log.csv`, and a
`search/pipeline.csv` with rows from an earlier run.

## The user's message

> Do a sweep and fill up my pipeline. Just the FDE stuff for now.

## Output Specification

An updated `search/pipeline.csv` and a run report under `search/runs/`, with
every duplicate collapsed, every drop explained, and nothing written to
`applications/`.
