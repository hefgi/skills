# Keep unreachable and off-profession roles out of the pipeline

## Problem/Feature Description

A real sweep of 339 rows put 31 roles the user cannot legally take, and 17 roles
in a different profession, in front of them as actionable. Both classes looked
correct to the sweep that harvested them, which is what makes them worth an
eval: nothing errored, and the counts all added up.

Two failures, and each has a tempting wrong fix.

**Qualified remote is not remote.** `Remote - Texas` is a location requirement
wearing the word remote: you must be in Texas, there is simply no office. Every
qualified-remote string contains the bare word, so a geography test that looks
for `remote` first can never reach the qualified case. One large employer writes
its whole board this way, so getting it wrong fills the pipeline with a single
company's US postings.

**A job in another profession is not a stretch application.** The user applies
widely on purpose, so a preference never drops a row. But `Head of Sales EMEA`
and `PR Director` are not stretch engineering roles, they are other jobs. The
tempting fix, excluding anything containing `sales`, also removes
`Solutions Engineer, Pre-Sales` and `Pre-sales Engineering Manager`, which are
real engineering roles the user wants. That fix is worse than the bug.

A posting listing several locations is reachable if **any** of them is, and a
fragment that is a hiring policy rather than a place is not a location at all.

## Setup

Serve the board fixtures on port 8899 from the `fixtures/` directory:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy `fixtures/workspace/` somewhere writable and run against the copy. Its
`profile/search.md` carries both `exclude_locations` and `query_terms_exclude`.

`fixtures/blocker-cases.json` holds the same postings as a unit-level
regression, runnable with `scripts/test_blockers.py`. This scenario is the
agent-level counterpart: does a sweep put the right rows in front of the user.

## The user's message

> Sweep and fill the pipeline. I only want things I can actually take, and I
> only want engineering roles.

## Output Specification

A `search/pipeline.csv` where unreachable and off-profession rows are present
with a `drop_reason` rather than deleted, the reachable engineering roles are
`new`, and the run report names the profession drops individually rather than
only counting them.
