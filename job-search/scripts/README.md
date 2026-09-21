# Scripts

## pipeline.py

Owns every read and write of `search/pipeline.csv`. Run it rather than editing
the CSV or computing a key by hand: the identity key must be byte-identical
across every run forever, and a key derived a second way breaks dedup silently,
which shows up weeks later as duplicate applications.

It is a `uv run` script with an inline dependency header and no third-party
dependencies, so it needs no environment setup.

```bash
scripts/pipeline.py <command> [options]
```

`scripts/` in every example below is **relative to this skill's directory, not
to the workspace**. A sweep runs with the workspace as its working directory, so
resolve the script's real path once and use it throughout. Locate it from the
skill rather than hard-coding one, since where skills live differs between
setups:

```bash
# You know where you read SKILL.md from. Set this once from that path.
PIPELINE="<path to this skill>/scripts/pipeline.py"
"$PIPELINE" list --pipeline "$W/search/pipeline.csv"
```

### mine

Summarise `applications/log.csv` so Setup can seed from evidence rather than an
interview. Read-only.

```bash
scripts/pipeline.py mine --log "$W/applications/log.csv" \
                         --targets "$W/profile/targets.md"
```

| Option | Effect |
|---|---|
| `--log` | Required. The application log to mine. |
| `--targets` | Optional. Adds `titles_not_in_targets`, the delta between titles applied to and titles declared. |

Emits JSON: `applications`, `companies`, `platforms` (ranked, which becomes the
sweep order), `tracks`, `known_company_boards` (ATS slugs pulled from the URLs),
`titles`, `company_names`, `cooldown_candidates`, and `retryable` (applications
logged as failed, incomplete, or draft).

Each cooldown candidate carries `stated_cap`, `applications_logged`,
`cap_reached`, and `rejected_on_cap`. `cap_reached` is `null` when the note
stated a limit with no number, which is unknown rather than no.

### init

Create an empty `pipeline.csv` with the header. Does nothing if one already
exists with content.

```bash
scripts/pipeline.py init --pipeline "$W/search/pipeline.csv"
```

### key

Compute the identity key for one company and role. Useful for checking by hand
whether two postings will dedup.

```bash
scripts/pipeline.py key --company "Ash by Slingshot AI" --role "Technical Ex-Founder"
```

Returns `job_key`, `company_key`, `role_key`, and the captured `seniority`.

### upsert

The main call. Merges one sweep's whole harvest, deduping on all three axes,
applying blockers, and inferring tracks. Reads a JSON array on stdin.

```bash
scripts/pipeline.py upsert \
  --pipeline "$W/search/pipeline.csv" \
  --log      "$W/applications/log.csv" \
  --criteria "$W/profile/search.md" \
  --run-id   2026-09-21-1 \
  --max-new  60 \
  < harvest.json
```

| Option | Effect |
|---|---|
| `--pipeline` | Required. Written atomically. |
| `--log` | Enables axis-1 dedup against applications already made. Omitting it means a sweep can surface jobs already applied to. |
| `--criteria` | `profile/search.md`. Without it no blockers apply and every row is kept. |
| `--run-id` | Stamped on new rows, and matches the report filename. |
| `--max-new` | Cap on new rows this run. `0` disables. Anything beyond the cap is counted as `over_cap` rather than dropped silently. |
| `--today` | Override the date. For tests and fixtures. |
| `--dry-run` | Compute and report, write nothing. |

The summary reports `added`, `seen_again`, `reappeared`, `already_applied`,
`retryable`, `cross_post_merged`, `over_cap`, `dropped` by reason, and
`ambiguous_track`.

Taking the whole run as one payload is deliberate. Deduping within a run is
impossible if the first source's rows are written before the last source has been
swept, so a partially swept run cannot half-write.

### list

Read rows in the deterministic order `(track, source, first_seen descending,
company)`. That is a reading order, not a ranking: there is no fit score.

```bash
scripts/pipeline.py list --pipeline "$W/search/pipeline.csv" \
  --status new --track fde --limit 20 --format tsv
```

`--format` is `tsv` (default), `json`, or `url`. TSV exists so downstream shell
never has to parse quoted CSV.

### set-status

Move one row through the lifecycle. The only sanctioned way to change a status
by hand.

```bash
scripts/pipeline.py set-status --pipeline "$W/search/pipeline.csv" \
  --job-key cohere__forward-deployed-engineer --status queued --note "batch 3"
```

### reconcile

Pull applied state from the log into the pipeline. Run at the start of every
sweep.

```bash
scripts/pipeline.py reconcile --pipeline "$W/search/pipeline.csv" \
                              --log "$W/applications/log.csv"
```

### report

Render a run report to markdown.

```bash
scripts/pipeline.py report --pipeline "$W/search/pipeline.csv" \
  --run-id 2026-09-21-1 \
  --blocked "linkedin: checkpoint challenge at https://..." \
  --blocked "ai-boards: YC login wall" \
  --out "$W/search/runs/2026-09-21-1.md"
```

`--blocked` is repeatable, once per blocked source, and renders a "Sources
blocked" section. It is repeatable rather than comma-separated because a useful
blocked message names a URL and usually contains a comma, and splitting one
message into three fragments is worse than typing the flag twice. Use it
whenever a source could not be swept, because blocked and empty lead to
completely different actions by the user.

## What it refuses to do

The pipeline holds the user's triage, and triage cannot be regenerated by
sweeping again. The script exits non-zero rather than producing a file that
looks right and is not:

- **Write a row missing `company`, `role`, or `url`.** A row without those
  cannot be identified, deduped, or acted on.
- **Overwrite an existing row's `status`, `notes`, `first_seen`, or
  `applied_date`.** `upsert` only ever adds rows and bumps `last_seen`. The one
  exception is an `expired` row that reappears, which returns to `new` with a
  note saying so.
- **Invent a track.** A title matching neither or both track vocabularies is
  recorded as `both` and reported as ambiguous. A wrong track sends the wrong CV.
- **Accept a status transition outside the lifecycle** in
  `references/data-schema.md`. The error names what is allowed from the current
  status.
- **Split any CSV on commas.** Both `pipeline.csv` and `applications/log.csv`
  hold quoted fields containing commas, such as the role
  `"Product Engineer, Ona"`. Every read goes through `csv.DictReader` and every
  write through `csv.DictWriter`.
- **Write `pipeline.csv` non-atomically.** It writes a temp file in the same
  directory and renames it, so an interrupted run leaves the previous pipeline
  intact rather than a truncated one.
- **Touch anything outside the paths given on the command line.**

When a blocker rule is wrong, the fix is editing `profile/search.md` and moving
the row back to `new`. That ordering is the point: the criteria are the user's
to change, and the script should not quietly reinterpret them.
