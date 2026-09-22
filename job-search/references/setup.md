# Workflow 1: Setup

Create `profile/search.md` and the `search/` tree, so a sweep knows where to
look and what to skip.

The defining choice here: **mine the application log instead of interviewing.**
A user who has applied to thirty jobs has already demonstrated what they want,
which boards they use, and which titles they answer to. Asking them to describe
it from scratch produces a worse answer than reading what they did, and it costs
them twenty minutes. Setup asks only for what the log cannot show.

## Contents

- [Step 1: resolve the workspace, and refuse to create one](#step-1-resolve-the-workspace-and-refuse-to-create-one)
- [Step 2: check completeness](#step-2-check-completeness)
- [Step 2b: check tooling](#step-2b-check-tooling)
- [Step 3: create the skeleton first](#step-3-create-the-skeleton-first)
- [Step 4: mine the application log](#step-4-mine-the-application-log)
- [Step 5: read targets.md and logistics.md](#step-5-read-targetsmd-and-logisticsmd)
- [Step 6: ask only what mining cannot answer](#step-6-ask-only-what-mining-cannot-answer)
- [Step 7: write search.md](#step-7-write-searchmd)
- [Step 8: report](#step-8-report)
- [Re-running setup](#re-running-setup)

## Step 1: resolve the workspace, and refuse to create one

Use `find_workspace` from `SKILL.md`.

If it returns `none`, **stop and route to `job-apply`'s Setup.** Say plainly why:
a search needs `profile/targets.md` to know which titles to query and
`applications/log.csv` to know what to skip, and a job found here is only useful
if `job-apply` can act on it. Creating a partial workspace would produce a
pipeline with nothing at the other end.

## Step 2: check completeness

A workspace existing is not the same as it being usable for search.

```bash
W=<workspace>
for f in profile/targets.md profile/logistics.md applications/log.csv; do
  [ -s "$W/$f" ] || echo "MISSING (run job-apply setup first): $f"
done
[ -s "$W/profile/search.md" ]   && echo "search.md exists"   || echo "TO CREATE: profile/search.md"
[ -s "$W/search/pipeline.csv" ] && echo "pipeline exists"    || echo "TO CREATE: search/pipeline.csv"
```

`targets.md` missing is the blocking case, because it holds the target titles and
the Avoid list. Send the user to `job-apply`'s Setup step 6 rather than inventing
tracks here; tracks drive CV selection and belong to that skill.

An empty `log.csv` with only a header is fine. Mining yields nothing, so setup
falls back to asking, and step 6 grows accordingly. Say which mode is running so
the user understands why they are being asked more.

## Step 2b: check tooling

```bash
uv --version || echo "MISSING: brew install uv"
export PATH="$HOME/.local/bin:$PATH"
command -v ego-browser || echo "MISSING: see Prerequisites in SKILL.md"
```

Also check that the `ego-browser` skill is available, since it carries both the
browser manual and the ego lite installer.

`uv` is needed from step 4, because mining runs `scripts/pipeline.py`. Missing
`uv` blocks setup, so fix it here.

Missing ego lite does **not** block setup: nothing in setup drives a browser.
Note it and continue, then resolve it before the first sweep. Setting it up
needs the user at their keyboard for a GUI onboarding step, and interrupting a
mining conversation to install a browser they will not use for another ten
minutes is the wrong moment. Say plainly that a sweep will need it.

## Step 3: create the skeleton first

```bash
mkdir -p "$W/search/runs"
scripts/pipeline.py init --pipeline "$W/search/pipeline.csv"
```

Then write `profile/search.md` with every key present and empty, from the
template in `references/data-schema.md`. Fill it as the following steps resolve.

**Seed `profile/boards.md`** by copying `assets/boards-seed.md` from the skill.
It ships thirteen verified sources, so a first sweep is already wider than the
five this skill used to hardcode. Mining in step 4 then fills in the companies.

**Add the `search:` block to `.job-apply/config.yaml` if it is missing**, with
the keys and defaults from `data-schema.md`. `references/orchestration.md` reads
`max_concurrent_sweeps` and `max_concurrent_browser` from there, and a key that
is only ever documented is one an operator looks up and does not find.

Creating the skeleton before the questions is what makes step 2's check
meaningful and an interrupted setup resumable. A file with empty keys says "this
was considered and not yet answered". A file that does not exist says nothing,
and the next run cannot tell how far it got.

## Step 4: mine the application log

```bash
scripts/pipeline.py mine \
  --log "$W/applications/log.csv" \
  --targets "$W/profile/targets.md"
```

It prints JSON. What each part is for:

| Field | Seeds | Why it is trustworthy |
|---|---|---|
| `platforms` | The `sources:` order | Ranked by how often the user actually applied there. On a real log this is decisive: one workspace showed Ashby at 38 of 104 applications, so Ashby sweeps first. |
| `known_company_boards` | `companies` in `profile/boards.md` | Slugs pulled straight out of the URLs already applied to, across every ATS in `ATS_PATTERNS`. On a real 104-row log this finds 19 boards across five different ATSs. |
| `titles` | `query_terms_<track>` | Every title applied to, which is broader and more specific than a remembered list. |
| `titles_not_in_targets` | A question in step 6 | The delta between what they applied to and what `targets.md` claims they want. This is the highest-value output of mining. |
| `tracks` | The per-track query budget | The fde-to-leadership ratio in the log is how the user actually splits their effort. |
| `cooldown_candidates` | `company_cooldown`, **only when the cap is reached** | Mined from the notes column, where per-company application caps were recorded at the time. |
| `retryable` | Mentioned in the report | Applications logged as failed, incomplete, or draft. These are jobs to revisit, not history. |

**A mentioned cap is not a reached cap.** Each `cooldown_candidates` entry
carries `stated_cap`, `applications_logged`, `cap_reached`, and
`rejected_on_cap`. Write a company into `company_cooldown` when `cap_reached` is
true, or when `rejected_on_cap` is true, which means an application was actually
turned away on quota and is the strongest signal there is.

`cap_reached: null` means the note stated a limit without a number, which is
common in real wording ("we limit the number of applications"). Unknown is not
the same as no: surface those to the user rather than deciding either way.

When `cap_reached` is false, leave the company out and mention it in the report.
The key means "applying again wastes a slot", and a company that caps at three
where the user has sent one is a board worth sweeping, not skipping. Adding it
anyway silently removes one of their most-used boards from every future run.

The `titles_not_in_targets` delta is worth surfacing explicitly rather than
silently merging. On a real log it found 47 titles absent from `targets.md`,
including `Member of Technical Staff`, `Deployed Engineer`, and `Agent Deployment
Engineer`. Those are exactly the queries a search seeded only from `targets.md`
would never run, so the user would never see those jobs again.

Present the delta as a short list and ask whether to adopt it. Do not adopt it
silently: some entries will be one-off applications the user does not want to
repeat, and only they can tell which.

`mine` reads and never writes, so it is safe to run repeatedly while deciding.

## Step 5: read targets.md and logistics.md

**From `targets.md`**, take the `titles:` of each track as the base
`query_terms_<track>`, and the `## Avoid` list as the blocker policy. Reference
these rather than copying them wholesale: `search.md` should hold the search
*additions*, not a second copy of the targets. Two files claiming to define the
user's target roles will drift, and the one that is stale will still look
authoritative.

**From `logistics.md`**, derive the geography mechanically:

| Logistics field | Derives |
|---|---|
| `countries_authorized` | `geography` |
| `willing_to_relocate` | whether `exclude_locations` covers everywhere else |
| `work_preference` | `remote_scope` and `onsite_requires_city` |

A worked derivation: authorized in the UK, France, and the EU; not willing to
relocate; happy with fully onsite in London. That gives `geography: London UK,
United Kingdom, France, European Union`, `remote_scope: remote, hybrid, onsite`,
`onsite_requires_city: London`, and an `exclude_locations` of the major
non-authorized markets.

**Show the derivation and confirm it**, rather than writing it silently. This is
inference, not something read off a file, and a wrong `exclude_locations` makes
jobs vanish from every future sweep with no visible sign that a filter did it.

## Step 6: ask only what mining cannot answer

One batched `AskUserQuestion`. Four questions at most, which is the point of
mining first.

1. **The title delta.** Adopt the mined titles that `targets.md` lacks, all of
   them, or a subset?
2. **Company stage and size.** Nothing in the log reveals this reliably.
3. **Industries to avoid.** `industries_avoid` drops rows, so it needs saying
   out loud rather than inferring.
4. **Per-run cap.** Default 60 new rows. Worth confirming, because it is the
   main lever on how long a sweep takes.

If the log was empty, this step expands to cover what mining would have given:
which boards they use, which titles they want, and which companies to skip. Say
that the answers will improve on their own once applications accumulate.

## Step 7: write search.md

Use the template from `references/data-schema.md`, keeping its comments. The
user will edit this file by hand more than any other in the workspace, and a
comment explaining why `onsite` is in `remote_scope` is what stops them deleting
it six weeks later.

Order `sources:` by the mined platform counts, and say so in a comment. A sweep
cut short by a challenge page should already have harvested the best source.

## Step 8: report

Show, briefly:

- Where `search.md` and `search/pipeline.csv` now are
- The mined summary as a table: applications, companies, platform counts, and
  how many board slugs were captured
- What was inferred rather than asked, and from which file
- Anything still empty, and that it can be edited by hand at any time
- How to run a sweep

Then run the step 2 check again and report anything still missing.

If `retryable` was non-empty, mention it here: those are applications that
failed or were left incomplete, and they are the fastest jobs to revisit because
the user already decided they wanted them.

## Re-running setup

Safe to re-run, and it must never clobber.

- Ask what to update: scope, sources, query terms, or exclusions
- Update only that
- **Never touch `search/pipeline.csv`.** It holds the user's triage, and
  re-running setup is not a reason to lose it
- Re-mining is always safe and is the right move after a batch of applications,
  because new applications mean new board slugs and new titles
