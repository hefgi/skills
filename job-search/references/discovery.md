# Discovering new job sources

A sweep that only knows the boards it shipped with gets no better with use. This
is how a sweep turns a link it happened to see into a source it can harvest on
every later run.

Two things get discovered, and they are different work:

- **A new company** on a board type already known. Cheap, common, and the main
  way `boards.md` grows.
- **A new board type**, an applicant tracking system the workspace has never
  seen. Rarer, needs a probe, and worth doing because it unlocks every company
  on that ATS from then on.

## Contents

- [Why this compounds](#why-this-compounds)
- [Recognising a board in a URL](#recognising-a-board-in-a-url)
- [The probe ladder](#the-probe-ladder)
- [Verify before saving](#verify-before-saving)
- [What to write](#what-to-write)
- [When not to bother](#when-not-to-bother)

## Why this compounds

Ashby, Greenhouse, Lever and the rest have no cross-company search. Their public
endpoints are per-board by design, so the only way to sweep them is to know
which boards exist. There is no free API that searches across all of them, which
makes the directory the asset: it is the one thing a sweep builds that makes the
next sweep cheaper.

Search sources are what feed it. LinkedIn postings link out to company ATS
boards, and Workable's cross-company search names a company on every result. So
the pattern is: search sources find companies, companies reveal boards, and
boards are harvested directly and far more cheaply from then on.

Tell the user when the directory grew and by how much. It explains why later
sweeps find more while doing less, and it is the clearest sign the skill is
improving with use.

## Recognising a board in a URL

Every posting URL a sweep sees is a candidate. `pipeline.py` already knows the
shapes:

```bash
"$PIPELINE" boards --boards "$W/profile/boards.md" --format json
```

Each `board` entry carries a `posting_pattern`. A URL matching one is a known
board type, and the captured group is the company slug. Add it:

```bash
"$PIPELINE" boards --boards "$W/profile/boards.md" --add-company lever:palantir
```

Under a fan-out run agents **report** slugs rather than writing them, and the
orchestrator merges once. Two agents editing `boards.md` at the same moment
clobber each other.

A URL matching nothing is either a new board type or an ordinary careers page.
The signal that it is an ATS is a host shaped like `{slug}.vendor.com` or
`vendor.com/{slug}`, with the same vendor appearing for different companies. One
company on its own domain is a careers page, not a board type.

## The probe ladder

Only for a host that looks like an ATS and matches no known pattern. Try these
in order and stop at the first that returns parseable rows:

| Probe | Shape |
|---|---|
| `{host}/jobs.json` | JSON Feed. Teamtailor answers here. |
| `{host}/jobs.rss` | RSS, often with a vendor namespace carrying location and remote status. |
| `{host}/api/offers/` | Recruitee. The trailing slash matters. |
| `{host}/xml?language=en` | Personio. |
| `{host}/json` | Breezy. |
| `{host}/api/v1/...` | Generic REST, worth one guess from the visible path. |

**Probing is requests against someone's site.** At most a handful of candidate
paths per host, once, and never in a loop. A host that answers none of them is
not hiding an endpoint from you; it does not have one.

If the page is server-rendered and listable, the board is still usable as
`tier: 2` with the browser. Record it that way rather than discarding it.

## Verify before saving

**A recipe that has not returned at least one row with a role and a URL is not
saved as `tier: 1`.** This is the rule that matters most here.

An unverified recipe saved as working is worse than no recipe: every later sweep
calls it, gets nothing, and reports an empty board. Nothing distinguishes that
from a company with no open roles, so the failure is invisible and permanent.

Two traps found in real endpoints, both worth checking before believing a zero:

- **SmartRecruiters does not 404 on a wrong identifier.** It returns 200 with
  `totalFound: 0`, exactly like a real company with nothing open. An empty
  result is not evidence the slug is wrong, and not evidence it is right.
- **Lever's payload contains raw control characters.** A strict JSON parser
  fails on it; the browser's `JSON.parse` does not. A parse error here is not an
  empty board.

Record what was verified and when, in the `verified` field. A board that
silently stops working is then visible as a stale date rather than as a quiet
zero.

## What to write

Record it through the script, which refuses a board with no `fields` mapping and
will not silently overwrite one that exists:

```bash
"$PIPELINE" boards --boards "$W/profile/boards.md" \
  --add-board jobvault \
  --api 'https://{slug}.jobvault.io/jobs.json' \
  --fields 'headline->role, place->location, arrangement->work_mode, permalink->url' \
  --posting-pattern '([a-z0-9-]+)\.jobvault\.io' \
  --verified '2026-09-22, 2 roles for kepler' \
  --notes 'slug substitution inferred from a single tenant'
```

Omit `--verified` when the recipe has not actually returned a row. The schema is
in `references/data-schema.md`.

`fields` is the mapping that matters, because it is what a later sweep uses
without rediscovering anything: which key holds the role, which the location,
and whether anything maps to `work_mode`. Three sources supply work mode
directly (`workplaceType` on Lever, `workplace` on Workable, `location.remote`
on SmartRecruiters), and most supply none, which is worth recording either way
so a later sweep does not go looking.

**Rows from a newly discovered board carry its name.** Set both `source` and
`platform` to the board's `name`, the same string used in `boards.md`. Neither
column is a closed list, precisely so the directory can grow: filing a jobvault
row as `other` throws away the one fact that would let a later sweep route it
back to the recipe that found it.

**Flag what was guessed.** A field derived rather than observed goes in `notes`,
and in the run report. The next person to read the file cannot tell the
difference otherwise.

## When not to bother

Some systems are places a candidate *arrives at* rather than places to sweep,
and writing a recipe for them wastes the effort twice: once now, once when it
silently returns nothing.

Verified as not worth it: **Indeed** and **Glassdoor** both refuse a plain
request outright. **Eightfold** refuses too. **JazzHR**'s public API is gone.
**iCIMS**, **Oracle HCM**, **Keka** and **RippleHire** are per-tenant enterprise
deployments with no public listing endpoint at all.

These still appear in an application log, because the user reached them through
LinkedIn or a careers page. That is the correct handling: let the search sources
feed them, and do not try to sweep them directly.

The general test: if a system has no way to list a company's open roles without
an account, it is not a board for this purpose, however many times it appears in
the log.
