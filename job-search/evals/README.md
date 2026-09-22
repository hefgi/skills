# job-search evals

Six scenarios, one directory each, holding a `task.md` (the prompt given to an
agent with the skill available) and a `criteria.json` (a weighted checklist for
scoring the result). Same layout as the other skills in this repo.

| Scenario | Covers | Needs a browser |
|---|---|---|
| `setup-mines-past-applications` | Deriving search criteria from an existing workspace instead of interviewing | no |
| `sweep-dedups-across-three-axes` | The core sweep: dedup, drops, CSV integrity | yes |
| `sweep-degrades-on-blocked-source` | Carrying on when a board blocks the sweep | yes |
| `sweep-orchestrated-fan-out` | Parallel sweep: shards, one agent per domain, a single upsert | yes |
| `discover-a-new-board` | Turning a posting URL into a reusable board in the directory | yes |
| `sweep-filters-unreachable-and-offtrack` | Dropping roles the user cannot take or does not want, without taking the pre-sales engineering roles with them | yes |

## Running

No real job board is ever contacted. The two browser scenarios run against
static fixture pages, and the skill never submits anything anywhere, so there is
no destructive step to neuter.

Serve the board fixtures before either browser scenario:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy the fixture workspace somewhere writable and point the run at the copy.
Running against `fixtures/` directly makes the next run start dirty:

```bash
cp -R evals/fixtures/workspace /tmp/search-eval
```

The browser scenarios need ego lite installed and onboarded. See Prerequisites
in `SKILL.md`.

## Unit-level regression

`fixtures/blocker-cases.json` holds 23 real postings from the 2026-09-21 sweep
with the drop reason each should produce. Run them directly, no browser and no
agent:

```bash
scripts/test_blockers.py
```

Every DROP case reached the user before the geography and function blockers
existed. Every KEEP case is one a careless fix breaks, and the pre-sales rows
are the sharpest: a bare `sales` exclusion removes all three, which is worse
than the original bug. Run this before and after any change to `blocker_for()`.

## Fixtures

`fixtures/seed-workspace/` is a workspace with an application history but no
search configured yet, which is what setup mines. `fixtures/workspace/` is the
same profile with `profile/search.md` and a `search/pipeline.csv` already
populated from an earlier run, which is what the sweeps build on.

`fixtures/boards/` holds the static board pages. Each one carries an HTML or
JSON comment explaining what it is for, so read the file rather than guessing.
They mirror the real markup closely enough that the selectors in `sources.md`
are genuinely exercised rather than matched against a convenient shape:

- `linkedin-results.html` carries most of the test cases, including the roles
  that must be dropped: one US-only posting (`us-work-auth`) and one junior
  posting (`junior-ic`). It also holds a role already present in the application
  log and one already skipped in the pipeline.
- `linkedin-results-page2.html` exercises pagination, and repeats one card from
  page 1 the way LinkedIn repeats promoted requisitions, so the in-run dedup has
  to absorb it without emitting a second row.
- `ashby-board.html` carries the other half of the cross-post: its "Forward
  Deployed Engineer (UK)" is the same job as a LinkedIn card, so the same role
  arrives by two routes.
- `greenhouse-api.json` mirrors the Greenhouse boards API rather than HTML,
  since the API is the preferred path and needs no DOM parsing. The sweep has to
  handle both shapes.
- `yc-jobs.html` is a login wall. A truncated anonymous list looks like a
  complete result, so the sweep must recognise the wall and skip rather than
  harvest a partial page as if it were everything.
- `linkedin-challenge.html` is the blocked source that drives the degradation
  scenario.
- `kepler-board.html` and `kepler-board.json` are an ATS the skill has never
  heard of, at `{slug}.jobvault.io`. Nothing in `ATS_PATTERNS` matches it, so
  `discover-a-new-board` has something real to probe. The JSON deliberately uses
  field names (`headline`, `place`, `arrangement`, `permalink`) that match no
  shipped recipe, so an agent has to record an actual mapping rather than
  assuming a familiar shape.
- `acme-careers.html` is the negative case: one company's own careers page on
  its own domain. Jobs should be harvested from it, but it must not be recorded
  as a reusable board type.

All fixture data is synthetic. Ada Lovelace and the companies in these pages are
invented. Keep the board companies distinct from the employers in the fixture
CV, so an agent never has to wonder whether it is looking at a former employer.
