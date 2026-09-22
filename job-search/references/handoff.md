# Handoff to job-apply

How a row in the pipeline becomes a submitted application, and how that fact
finds its way back.

The contract is deliberately narrow: **job-search hands over a URL, and reads
the application log afterwards.** Nothing else crosses. A richer interface would
mean `job-apply` had to learn `pipeline.csv`, and then two skills would be
writing one file with no way to tell which write was right.

## Contents

- [Forward: a row becomes an application](#forward-a-row-becomes-an-application)
- [Backward: the log updates the pipeline](#backward-the-log-updates-the-pipeline)
- [Why a job is never offered twice](#why-a-job-is-never-offered-twice)
- [The boundary](#the-boundary)

## Forward: a row becomes an application

The user asks for something like "apply to the next three FDE roles".

```bash
scripts/pipeline.py list --pipeline "$W/search/pipeline.csv" \
  --status new --track fde --limit 3 --format url
```

Mark each as queued before handing it over, so an interrupted batch does not
lose track of what was already in flight:

```bash
scripts/pipeline.py set-status --pipeline "$W/search/pipeline.csv" \
  --job-key <key> --status queued
```

Then hand `job-apply` the URL, one at a time. That is the whole interface.
`job-apply`'s Apply workflow already takes a posting URL and reads everything
else it needs from the shared workspace, so there is nothing to pass along.

`platform` in `pipeline.csv` uses the same vocabulary as
`applications/log.csv` specifically so that no translation happens at this
boundary.

A `both` track is not a blocker on the handoff. `job-apply` picks the CV track
from the full posting text, which it fetches anyway and a sweep never had.

## Backward: the log updates the pipeline

`job-apply` writes `applications/log.csv` and knows nothing about `search/`.
So reconciliation is a **pull, not a push**:

```bash
scripts/pipeline.py reconcile --pipeline "$W/search/pipeline.csv" \
                              --log "$W/applications/log.csv"
```

It matches log rows to pipeline rows by canonical URL, then by identity key, and
flips matches to `applied` with the log's date.

Run it at the start of every sweep, and offer it after any batch of
applications.

This design means **no changes to `job-apply` are required**, which is the
point. A contract that needs both sides edited in step breaks the moment one is
updated alone, and these two skills will not always be updated together.

Log status decides what counts as finished. `applied`, `submitted_manually`, and
`awaiting_review` are done. `failed`, `incomplete`, and `draft` are not: those
rows stay actionable, because a posting that closed mid-application or an
application that hit a per-company cap is worth another attempt.

## Why a job is never offered twice

Three things stack up, in this order:

1. **Reconcile runs first**, so everything applied to since the last sweep is
   already `applied` before new rows are evaluated.
2. **Axis 1 dedup** checks every harvested job against the log directly, by URL
   and by identity key, so a role applied to through Ashby is recognized when
   LinkedIn shows it a week later.
3. **Axis 2 dedup** means a job already in the pipeline keeps its existing
   status rather than reverting to `new`.

A job can still legitimately reappear as actionable: a posting that expired and
was reposted, or an application that failed. Both carry a note saying so, which
is the difference between a useful second chance and a duplicate.

## The boundary

`job-search` does not, under any circumstance:

- Write `applications/`, `cv/`, `qa/`, or any of `profile/` except `search.md`
- Render a CV or write a cover letter
- Open, fill, or submit an application form
- Drive the `job-apply` browser session

If the user asks for any of that mid-sweep, finish or cleanly abandon the sweep
first, then hand off. Two skills driving one browser session is how a half-filled
form gets submitted, and a submitted application cannot be recalled.

The reverse also holds: `job-apply` does not write `search/`. If a pipeline row
needs its status changed, it happens through `pipeline.py set-status` or through
`reconcile` reading the log.
