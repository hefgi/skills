# Data schema

Canonical spec for the two things this skill writes. Prefer it over inferring
structure from whatever files happen to exist, because a sweep that guesses the
pipeline's shape will write a column nothing reads.

Everything else in the workspace belongs to `job-apply` and is read-only here.
Its `references/data-schema.md` is authoritative for those files.

## Contents

- [Layout](#layout)
- [profile/search.md](#profilesearchmd)
- [search/pipeline.csv](#searchpipelinecsv)
- [Status lifecycle](#status-lifecycle)
- [search/runs/<run-id>.md](#searchrunsrun-idmd)
- [The search block in .job-apply/config.yaml](#the-search-block-in-job-applyconfigyaml)
- [Conventions](#conventions)

## Layout

```
<workspace>/
├── profile/search.md        # written by Setup, edited by hand afterwards
└── search/
    ├── pipeline.csv         # every job found, one row each
    └── runs/
        ├── 2026-09-21-1.md                  # the run report
        ├── 2026-09-21-1.partial.json        # serial sweep scratch
        ├── 2026-09-21-1.ashby.json          # fan-out: one shard per agent
        ├── 2026-09-21-1.linkedin.json
        └── 2026-09-21-1.merged.json         # what the orchestrator upserts
```

Scratch files are deleted after a clean upsert. Under a fan-out run each agent
owns exactly one shard and writes nothing else, because a single shared file
means the last writer wins and every other agent's rows vanish. A shard holds
either a bare array of harvest rows, or an object carrying what the agent could
not sweep alongside them:

```json
{"rows": [...], "blocked": ["linkedin: challenge at https://..."], "slugs": ["ashby:hilbert"]}
```

`pipeline.py merge` accepts both shapes and concatenates them.

## profile/search.md

Markdown with `key: value` lines, the same shape as `profile/targets.md` so one
tolerant parser reads both. Match on the key name, ignore surrounding
formatting, and treat a missing or empty value as unknown rather than as an
empty string. Values may wrap onto indented continuation lines.

This file says **where and how** to look. `profile/targets.md` says **what** to
look for. When the two disagree, `targets.md` wins: `job-apply` reads it to pick
a CV track, and a second copy of the target roles would drift out of step
without anyone noticing.

```markdown
# Search criteria

Sourcing criteria for the job-search skill. Read on every sweep.
Roles and titles live in profile/targets.md. This file says WHERE and HOW to
look, not WHAT to look for. When the two disagree, targets.md wins.

## Scope

geography: London UK, United Kingdom, France, European Union
remote_scope: remote, hybrid, onsite
# Onsite is included because logistics.md accepts fully onsite in London.
# Onsite outside London is a blocker, not a preference: relocation is off.
onsite_requires_city: London
exclude_locations: United States, Canada, India, Singapore, Australia
# Excluded because they imply relocation or local work authorization.

## Companies

company_stage: seed, series-a, series-b, series-c, growth, public
company_size:
industries_prefer: AI infrastructure, developer tools, agents, fintech
industries_avoid: gambling, adtech
# industries_avoid drops a row. industries_prefer only affects report grouping,
# because a preference is not a reason to hide a job from someone applying wide.

## Sources

sources: ashby, greenhouse, linkedin, ai-boards, career-pages
# Sweep order, most productive first, so a run cut short by a challenge page has
# already harvested the best sources. Derived from the application log.
sources_disabled:
known_company_boards: ashby:cohere, ashby:openai, ashby:langchain,
  greenhouse:physicsx
# Mined from applications/log.csv URLs, and appended to whenever a sweep finds a
# new slug. Revisiting a board the user already applied through is the cheapest
# source of new roles there is.

## Query terms

# Seeded from profile/targets.md titles, plus titles found in the application
# log that targets.md does not list.
query_terms_fde: Forward Deployed Engineer, Deployed Engineer, Solutions
  Engineer, Applied AI Engineer, Solutions Architect, Customer Engineer
query_terms_leadership: VP of Engineering, CTO, Head of Engineering,
  Director of Engineering
query_terms_exclude: intern, graduate, apprentice, placement

## Exclusions

company_cooldown: Google until 2026-10-07, ElevenLabs
# Companies that cap applications per candidate or per window. Applying again
# wastes a slot. A bare name is indefinite; "until <ISO date>" expires.
companies_never:

## Pacing

max_new_rows_per_run: 60
max_pages_per_query: 3
```

Every list is comma-separated. A trailing empty value means "considered, not
set", so keep the key rather than deleting it.

`query_terms_fde` and `query_terms_leadership` are keyed to the track names in
`targets.md`. A workspace with different tracks uses `query_terms_<track>` for
each, and `pipeline.py` reads whichever exist.

## search/pipeline.csv

One row per job found, ever. Sixteen columns, in this order:

```csv
job_key,first_seen,last_seen,company,role,url,platform,location,work_mode,track,source,status,applied_date,run_id,drop_reason,notes
```

| Column | Content |
|---|---|
| `job_key` | Normalized identity, `company__role`. The primary key. Computed only by `pipeline.py`, never by hand. |
| `first_seen` | ISO date the row was created. Never changes. |
| `last_seen` | ISO date the job was last observed live. Updated on every sweep that sees it. |
| `company` | As advertised |
| `role` | As advertised, with the original punctuation. Quoted by the CSV writer when it contains a comma. |
| `url` | The posting URL, query string stripped |
| `platform` | `ashby`, `greenhouse`, `linkedin`, `lever`, `workable`, `teamtailor`, `rippling`, `icims`, `workday`, `direct`, `other`. The same vocabulary `applications/log.csv` uses, so a row crossing to `job-apply` needs no translation. |
| `location` | As advertised |
| `work_mode` | `remote`, `hybrid`, `onsite`, `unknown` |
| `track` | `fde`, `leadership`, or `both`. `both` is a real answer, not a failure: "Head of Forward Deployed Engineering" genuinely fits either, and `job-apply` resolves it against the posting text. |
| `source` | Which sweep found it first: `ashby`, `greenhouse`, `linkedin`, `ai-boards`, `career-pages` |
| `status` | See the lifecycle below |
| `applied_date` | Filled when the status becomes `applied`, from the log. Empty otherwise. |
| `run_id` | The sweep that created the row, matching a file in `search/runs/` |
| `drop_reason` | Empty unless `status` is `dropped`. One of `junior-ic`, `us-work-auth`, `location`, `onsite-elsewhere`, `cooldown`, `company-excluded`, `industry`. |
| `notes` | Free text. A cross-posted duplicate's other URL goes here as `also: <url>`. |

There is deliberately **no score, rank, fit, or match column**. The policy is to
apply to anything with title similarity, so a score would be a number nobody
acts on, and it would quietly become a reason not to apply.

Rows are stored sorted by `(track, source, first_seen descending, company)`.
That is a reading order, not a ranking: track first because the user works one
CV track at a time, then source so a board reviews as a block, then newest first.

## Status lifecycle

| Status | Meaning | Set by |
|---|---|---|
| `new` | Found, passed the blockers, not yet triaged | sweep |
| `queued` | Picked for application | user, or the handoff |
| `applied` | `job-apply` submitted it | `reconcile`, from the log |
| `dropped` | Failed a blocker. `drop_reason` says which. | sweep |
| `skipped` | The user looked and declined | user |
| `expired` | The posting was gone on a later sweep | sweep |
| `rejected` | The employer said no | user |

Permitted transitions:

```
new      -> queued | skipped | dropped | expired | applied
queued   -> applied | skipped | expired | new
applied  -> rejected
dropped  -> new          (a blocker was wrong, or the criteria changed)
skipped  -> new | queued (the user changed their mind)
expired  -> new          (reposted)
rejected -> (terminal)
```

`pipeline.py set-status` refuses anything else rather than writing it. An
out-of-band status means two writers disagree about what happened, and the CSV
cannot say which is right.

A row that reappears after being `expired` goes back to `new` with a note. A
reposted requisition is a real opportunity, and leaving it expired buries it.

## search/runs/<run-id>.md

Written at the end of every sweep. The run id is `<ISO date>-<n>`, so a second
sweep on the same day is `2026-09-21-2`.

It must say three things, and the third is the one that gets forgotten:

1. What was found, by status and by source.
2. What was dropped, and for which reason.
3. **What could not be swept, and why.** A source that was blocked is not a
   source with no jobs. Collapsing the two tells the user a board is dry when it
   is merely challenging their session, and they stop checking it by hand.

`pipeline.py report --blocked "linkedin: checkpoint challenge at <url>"` renders
the blocked section.

## The search block in .job-apply/config.yaml

Optional. The workspace marker is shared, so this skill adds a `search:` block
rather than a second config file. Absent keys take the defaults shown.

```yaml
search:
  max_new_rows_per_run: 60   # 0 disables the cap
  default_track:             # empty sweeps every track

  # Fan-out caps, used only by references/orchestration.md.
  max_concurrent_sweeps: 6   # tier 1: public JSON APIs, no browser, no session
  max_concurrent_browser: 3  # tier 2: one task space each, never 2 on a domain
```

The two caps are separate because the sources they govern carry different risk,
not different speed. Tier 1 agents open no browser at all and hit public
endpoints that are nobody's account, so the only limit is politeness. Tier 2
agents share the user's logged-in session, where the binding rule is one agent
per domain rather than any particular total. Setting `max_concurrent_browser`
above 1 never permits two agents on the same domain.

`0` or `1` in either means do not fan out that tier; sweep it yourself in
sequence.

**`profile/search.md` wins when the two disagree.** `max_new_rows_per_run`
appears in both files, because pacing belongs with the other sourcing criteria
and the config block predates it. The user edits `search.md` by hand far more
often, so that is the one whose value to trust, and the one to change. Say which
you used when they differ, rather than picking silently.

A sweep opens its own ego lite task space, named for the run, and does not share
one with an application in progress. Nothing about the browser belongs in this
config: the `ego-browser` skill owns that, and duplicating a setting here would
give two files an opinion about it.

## Conventions

These match `job-apply`'s, because a user reading both workspaces should not
have to learn two sets of rules.

**Dates** are ISO `YYYY-MM-DD`.

**Missing values** stay as present-but-empty keys rather than being deleted, so
it is clear the field was considered rather than forgotten.

**Appending, not rewriting.** `pipeline.csv` grows. `upsert` only ever adds rows
and bumps `last_seen`; it never rewrites a status, a note, or a `first_seen`,
because those are the user's triage and cannot be regenerated by sweeping again.

**Never split these files on commas.** Both `pipeline.csv` and
`applications/log.csv` contain quoted fields with embedded commas, such as the
role `"Product Engineer, Ona"`. `awk -F,` and `cut -d,` shift every column after
one, and the corruption is silent. Use `pipeline.py`, or a real CSV parser.

**Editability.** The user will open `search.md` by hand more than any other file
in the workspace. Keep the comments that explain why a default was chosen, and
do not reformat the file because one value changed.
