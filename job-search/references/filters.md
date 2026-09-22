# Filters: identity, dedup, and blockers

How a sweep decides that two postings are the same job, and that a job is not
worth surfacing. `scripts/pipeline.py` implements all of this. Read it here to
know what it will do; run it rather than reimplementing any of it, because a key
computed a second way silently breaks every future dedup.

## Contents

- [The identity key](#the-identity-key)
- [Dedup on three axes](#dedup-on-three-axes)
- [Blockers](#blockers)
- [Track inference](#track-inference)
- [What happens to dropped rows](#what-happens-to-dropped-rows)

## The identity key

URLs cannot be the identity. The same requisition appears on LinkedIn, on the
company's Ashby board, and on an aggregator, with three different URLs, and
LinkedIn regenerates its own href with fresh tracking parameters on every
render. So identity comes from the company and the role:

```
job_key = normalize_company(company) + "__" + normalize_role(role)
```

`normalize_company` lowercases, strips a parenthetical so `Bjak (ActAI)` is one
company, drops legal and filler suffixes (`Inc`, `Ltd`, `GmbH`, `Labs`, `AI`),
and removes an `Ash by ` prefix that Ashby boards prepend to the employer name.
Left in, that prefix keys one company two ways depending on which source found
it.

`normalize_role` lowercases, then repeatedly strips:

- **Trailing qualifiers** that say who may apply rather than what the job is:
  `- French Speaking`, `(UK)`, `EMEA`, `(m/f/d)`, `Remote`, `, Ona`.
- **Seniority prefixes**: `senior`, `staff`, `principal`, `lead`, `junior`,
  `associate`. These are captured and returned, not discarded, because seniority
  is what the junior blocker tests. Silently dropping it would make that filter
  unenforceable.
- **Level suffixes**: `II`, `III`, `2`. Also captured.

then expands known abbreviations (`fde`, `mts`, `swe`, `cto`) and folds trailing
plurals, so `Solution Engineer` and `Solutions Engineer` are one job. Boards use
both spellings for the same posting.

Deliberately **not** stripped: `chief`, `head of`, `director of`, `vp of`.
Removing those would collapse `Head of Engineering` into `Engineering`, and an
executive role is not a variant of an IC one.

Worked examples, all from real postings:

| Company | Role | Key |
|---|---|---|
| LangChain | Deployed Engineer (UK) | `langchain__deployed-engineer` |
| LangChain | Deployed Engineer | `langchain__deployed-engineer` |
| ThoughtSpot | Solution Engineer - French Speaking | `thoughtspot__solution-engineer` |
| ThoughtSpot | Solutions Engineer | `thoughtspot__solution-engineer` |
| Acme Inc. | Senior Forward Deployed Engineer | `acme__forward-deployed-engineer` |
| Acme | FDE | `acme__forward-deployed-engineer` |
| ElevenLabs | Forward Deployed Engineer | `elevenlabs__forward-deployed-engineer` |
| ElevenLabs | Forward Deployed Engineer Software Engineer France | `elevenlabs__forward-deployed-engineer-software-engineer` |

The last two are a deliberate non-match. They were two separate requisitions at
one company, and merging them would have hidden a job the user could have
applied to.

**Normalization is lossy, so it is advisory at the boundary.** An exact key
match at the same company dedups. A key match where the hosts differ *and* the
roles differ by more than a stripped qualifier keeps both rows and reports a
possible duplicate in the run report. A spurious extra row costs the user one
glance; a wrongly merged row costs them an application.

## Dedup on three axes

All three run inside one `pipeline.py upsert` call, in this order.

### Axis 1: against applications/log.csv

Has the user already applied to this?

Two passes. **Canonical URL** first, which is cheap and certain: scheme, `www.`,
query string, and trailing slash removed, lowercased. Then **`job_key`**, which
catches the case that matters, where the user applied through Ashby and LinkedIn
is now showing the same role.

A hit does not drop the row. It sets `status: applied` and copies `applied_date`
from the log, so the pipeline honestly reflects what has happened rather than
pretending the job never existed.

**Log status decides whether it is finished.** `applied`, `submitted_manually`,
and `awaiting_review` mean done. `failed`, `incomplete`, and `draft` do **not**:
the row stays actionable with the previous attempt's reason attached to its
notes. This distinction is load-bearing. A posting that closed mid-application,
or an application that hit a per-company quota, is worth another attempt later,
while a submitted one is not. Getting it backwards either hides retryable jobs
or re-offers submitted ones.

### Axis 2: against previous sweeps

`job_key` is the primary key of `pipeline.csv`. A job already there gets
`last_seen` bumped and **nothing else touched**. Status, notes, `first_seen`,
and `applied_date` are the user's triage, and a sweep that overwrote them would
destroy the only data in the file that cannot be regenerated.

The one exception: a row that was `expired` and has reappeared becomes `new`
again with a note. A reposted requisition is a genuine opportunity.

### Axis 3: within one sweep

The same job found on LinkedIn and on Ashby in a single run is one row. The
first source to find it wins the `url` and `source`; the other's URL is appended
to notes as `also: <url>`.

This is why a sweep **buffers every source and upserts once at the end**, rather
than writing rows as it finds them. If the LinkedIn row is already in the CSV
before the Ashby sweep runs, there is nothing left to collapse. `upsert` takes
the whole run as a single JSON payload on stdin precisely so that a partially
swept run cannot half-write.

## Blockers

A blocker drops a row. Only true blockers qualify: things the user cannot take,
or has ruled out permanently. The user is applying wide on purpose, so a mere
preference never drops a job.

| Reason | Test |
|---|---|
| `junior-ic` | Title matches intern, graduate, apprentice, placement, trainee, working student; or seniority is junior or associate; or the level is I or II with no senior, staff, principal, or lead marker alongside it |
| `us-work-auth` | The posting demands US citizenship, a green card, existing US work authorization, or a security clearance |
| `location` | Every location on the posting matches `exclude_locations` or names a subdivision of one, **unless** the role is *unqualified* remote. `Remote - Texas` is dropped; `Remote`, `Remote - EMEA` and `Remote - Global` are kept. |
| `function-excluded` | The role title matches `query_terms_exclude`: a job in a different profession. |
| `onsite-elsewhere` | Work mode is onsite and the location is not `onsite_requires_city` |
| `cooldown` | The company is in `company_cooldown` and any `until` date has not passed |
| `company-excluded` | The company is in `companies_never` |
| `industry` | The posting matches `industries_avoid` |

### Qualified remote is not remote

`Remote - Texas` is a location requirement wearing the word remote. You must be
in Texas; there simply is no office. Only **unqualified** remote is genuinely
location-independent.

This matters more than it sounds, because large US employers write their whole
board that way. A real sweep put 31 unreachable rows in front of the user, 26 of
them one company's US state postings, and every one contained the word remote.

Two consequences for anything testing a location:

- **Test qualified remote before the bare word**, since every qualified string
  contains it. A check that looks for `remote` first can never reach the
  qualified case.
- **`work_mode: remote` does not exempt a row.** "A remote role at a US company"
  and "a role requiring you to be in the US" are different things, and the field
  does not distinguish them. `Remote U.S.` is the second.

`exclude_locations` names countries, but boards name states and provinces, so
the blocker also matches subdivisions. Those live in `pipeline.py` next to the
other domain knowledge rather than in `search.md`: nobody should have to
enumerate fifty states by hand.

A posting listing several locations is kept when **any** of them is reachable,
so `Doha, Qatar; London, UK` stays. Fragments that are a hiring policy rather
than a place, such as `Remote-Friendly (Travel-Required)`, are not counted as a
reachable location, or a posting whose real offices are all excluded would be
rescued by its own policy text.

An absent location is unknown, not excluded. A results page often omits it, and
a false keep costs one glance while a false drop costs a job.

### Excluding a whole profession

`query_terms_exclude` drops roles in a different line of work: account
management, sales leadership, marketing, recruiting, non-software engineering.

Match on word boundaries, never substrings, and prefer multi-word phrases.
`head of sales` rather than `sales`, `pr director` rather than `pr`. A bare
`sales` exclusion also removes `Solutions Engineer, Pre-Sales` and `Pre-sales
Engineering Manager`, which are real engineering jobs the user wants. A bare
`pr` matches inside `product`.

Unlike the other blockers, this one encodes a judgement that can be wrong. An
`Applied AI Architect, Partnerships` is an engineering role serving the
partnerships org, and a `partnerships` exclusion drops it. That trade can be
worth making, but **list `function-excluded` drops individually in the run
report** rather than only counting them, so the user can see a bad call. The
location blocker states a fact; this one states an opinion.

The junior rule is mechanical on purpose. "Junior or mid-level IC" is genuinely
ambiguous, and an inconsistent filter is worse than no filter: the user cannot
tell whether a missing job was rejected or never found. Level III and above is
kept, and `Senior Engineer II` is kept because the senior marker wins.

`us-work-auth` reads the role title, location, and any notes captured from the
listing. A sweep that only skims a results page often has no posting body, so
this test catches what it can and `job-apply` catches the rest at application
time. That is an acceptable split: a false keep costs one discarded row, a false
drop costs a job.

## Track inference

Each row gets `fde`, `leadership`, or `both`, by matching the title against
`query_terms_<track>` in `search.md`.

Matching exactly one track sets it. Matching neither or both sets `both`, and
the run report lists those rows as ambiguous. The script does not guess: a wrong
track sends the wrong CV, and `job-apply` can resolve it properly against the
full posting text, which a sweep never has.

## What happens to dropped rows

They stay in `pipeline.csv` with `status: dropped` and a `drop_reason`.

Deleting them would mean the next sweep rediscovers the same posting, spends the
same effort evaluating it, and drops it again. "Requires US work authorization"
is a permanent fact about a posting, so recording it once is enough.

Keeping them also makes the filter auditable. The user can read what was dropped
and why, and if a rule is wrong, they fix `search.md` and move the row back to
`new`. A filter whose decisions are invisible is one nobody can correct.

The run report counts drops by reason rather than listing every row, because the
useful signal is "eleven dropped for location" and not eleven individual lines.
