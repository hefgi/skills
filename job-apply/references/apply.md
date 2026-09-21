# Workflow 3: Apply to a job

Takes a job posting URL. Produces a tailored CV, a cover letter, a submitted
application, and a log entry.

The phases run in order. Loading the profile before touching the browser is what
stops the skill asking for data it already holds, and verifying before
submitting is what stops a misread form reaching a real employer.

Applying to several jobs at once is a different workflow. Read
`orchestration.md` instead, and come back here for the per-application steps.

**If an orchestrator spawned you to apply to one posting, you are a subagent.**
Two rules override everything below, and they override `auto_submit`:

1. **Never submit until the orchestrator approves.** Fill and verify the form,
   then stop and send a `SUBMIT-REQUEST` (Phase E). Wait for `APPROVED`.
2. **Never write to `applications/log.csv`.** The orchestrator owns it. You send
   it a row; it appends.

Everything else here applies to you unchanged.

## Contents

- [Phase A: load the source of truth](#phase-a-load-the-source-of-truth)
- [Phase B: extract the posting](#phase-b-extract-the-posting)
- [Phase C: analyze and tailor](#phase-c-analyze-and-tailor)
- [Phase D: fill the form](#phase-d-fill-the-form)
- [Phase E: verify, then submit](#phase-e-verify-then-submit)
- [Phase F: record](#phase-f-record)
- [When it truly cannot proceed](#when-it-truly-cannot-proceed)

## Phase A: load the source of truth

Before opening a browser, read:

- Every file in `profile/`
- `qa/answers.md` and `qa/stories.md`
- `cv/cv-base.yaml`, `cv/design.yaml`, and every `cv/tracks/*.yaml`
- `.job-apply/config.yaml`, for `auto_submit` and naming
- `applications/log.csv`

This phase is not optional and not reorderable. The point of the workspace is
that the user answers a question once, and skipping the load defeats it.

**A `#` comment above a key is a standing decision, not a note.** When
`identity.md` carries a location rule or `logistics.md` carries a salary-band
computation, follow it without re-deriving it and without asking. These exist
because the same judgement recurs on every form. See `data-schema.md`.

**Check the log for a duplicate.** If the URL appears, or the same company and
role, tell the user before doing anything else. Applying twice to the same
posting is worse than not applying. As a subagent, raise it with the orchestrator
instead: it already deduplicated the batch, so a hit here means something it
could not see, and it is your only route to the user.

If there is no workspace, stop and run Setup. Do not improvise a profile.

**Read the `ego-browser` skill before the first browser call.** It is the
browser manual: task spaces, snapshots, refs, actions, uploads, and its own
escalation ladder for a stuck page. This skill does not restate any of it. What
you will find below is only what is specific to job applications.

## Phase B: extract the posting

Open the posting with ego-browser in a task space named for the job.

**First, before anything else, confirm the posting is still open.** Postings
close, and building a CV and a cover letter for a dead listing wastes the entire
run. Stop now and report it, without creating the application folder or
rendering anything, when either of these holds:

- The page says so. "No longer accepting applications", a closed or expired
  notice, a filled banner.
- There is no route to a form: no Apply control on the page, no link out to an
  applicant tracking system, and the user did not supply a form URL.

A missing Apply button is not by itself a closed posting. Plenty of postings are
description-only pages whose form lives elsewhere, and if the user handed you the
form URL directly then the route exists and the check is satisfied. What kills a
run is a page that states it is closed, or one with no way through at all.

**A form you discovered is not a route the posting offered.** Guessing an apply
URL, or finding one by browsing a directory listing or a sitemap the posting
never links to, is not the same as the employer pointing you there. An unlinked
form is as likely to be a draft, a stale artifact, or a different role's form as
it is the one intended for you. Say what you found and ask before using it.

Then read the description. The page's own text is the fastest route; scope the
extraction to the description container when the page is heavy with navigation,
"people also viewed" panels, and footers.

**Check whether the user already applied.** Many boards say so on the page
itself, and LinkedIn shows an "Application submitted" status with a date. This
is more reliable than the local log, since it catches applications made outside
this skill. Check both, and stop to ask before applying again.

Capture the poster's screening requirements specifically. LinkedIn surfaces them
under "Requirements added by the job poster", and they are the hard filters:
work authorization, years with a named technology, a required certification.
These decide whether applying is worthwhile at all, so if the user clearly fails
a hard filter, say so before spending effort on a tailored CV.

Common obstacles:

- **"Show more" truncation.** The description is collapsed behind a control and
  the text ends with "… more". Find the control, click it, re-extract.
- **Login wall.** Ask the user to log in, then retry. ego lite may be a fresh
  profile, so a session you expect to exist may not.
- **Expired posting.** Report it and stop.
- **The URL is a search result, not a posting.** Ask which posting is meant.

Create the application folder and write `job.md` per `application-schema.md`,
which is the spec for every file in an application folder:

```bash
mkdir -p "$W/applications/<YYYY-MM-DD>-<company>-<role-slug>/screenshots"
```

Extract into `job.md`: title, company, URL, platform, location, salary if
stated, the full description, and the requirements as a list.

Add a `## Signals` section: what the posting reveals about what they actually
want. Requirements listed first usually matter most. Phrases repeated across
sections are what the hiring manager cares about. Seniority language indicates
which track fits.

## Phase C: analyze and tailor

### Choose the track

Match the posting against each track in `profile/targets.md`, using title,
seniority language, and the balance of hands-on versus organizational
responsibilities.

State which track was chosen and why in one line. When two tracks fit roughly
equally, ask the user: it changes the whole document, and they know their
priorities.

If the posting matches something under `## Avoid`, say so before proceeding.

### Write analysis.md

Requirement by requirement, from the posting:

```markdown
# Analysis

track: fde
reason: Hands-on delivery role, customer-facing, no team ownership mentioned.

## Requirement match
| Requirement | Evidence | Strength |
|---|---|---|
| 5+ years Python | 12 years, Acme and Example Corp | strong |
| Customer-facing delivery | Client engagement at Example Corp | strong |
| Kubernetes in production | Listed in skills, no bullet-level evidence | weak |
| Finance domain | None | gap |

## Gaps
Finance domain: no direct experience. Honest framing from narrative.md is
regulated-fintech adjacency via the MLRO work.

## Emphasis for this application
Lead with the customer-facing engagement. Promote the pipeline bullet, since
they mention data volume twice. Deprioritize org-scaling bullets.

## Keywords to surface
Python, production ownership, customer engagement
```

The gaps section matters most. It drives paragraph 3 of the cover letter and
prevents overclaiming.

### Build the CV

Compose base plus track plus a per-application overlay. Use the bundled script,
which does the merge deterministically:

```bash
S="$W/applications/<slug>"

scripts/merge_cv.py --base "$W/cv/cv-base.yaml" \
  --track "$W/cv/tracks/<track>.yaml" \
  --overlay "$S/cv-overlay.yaml" \
  --out "$S/cv-merged.yaml"
```

It applies section order, entry treatment (`promote` / `nest` / `omit`),
highlight reordering and rewrites, and refuses to introduce a company or a
highlight that is not in the base. Read `scripts/README.md` for the exact
semantics. Doing this by hand per application is where inconsistency creeps in.

Layers compose, so a track that drops a highlight means an overlay cannot bring
it back. If you need a bullet the track drops, skip `--track` and declare the
role selection in the overlay instead.

Then render. **Use absolute paths for every path argument**, for the reason
explained in `cv-review.md`'s [RenderCV mechanics](cv-review.md#rendercv-mechanics)
section:

```bash
rendercv render "$S/cv-merged.yaml" --design "$W/cv/design.yaml" \
  -o "$S" \
  --pdf-path "$S/<Lastname>_<Company>_<Role>.pdf" \
  --dont-generate-markdown --dont-generate-html --dont-generate-png
```

Name the PDF per `naming.cv` in the config, typically
`<Lastname>_<Company>_<Role>.pdf`. A file called `cv.pdf` in a recruiter's
downloads folder is anonymous, and the filename is visible to them.

RenderCV leaves an `Ada_Lovelace_CV.typ` alongside the PDF. Harmless, and it
records exactly what was typeset.

**Every fact comes from `cv-base.yaml`.** Reorder, reweight, rephrase, retitle
for accuracy. Never add a technology, a number, or a responsibility that is not
already on record. Matching the posting is not worth a fabrication the user has
to defend in an interview.

Confirm the page count did not change unexpectedly. Read `cv-review.md` if the
rendered CV needs trimming.

### Write the cover letter

Read `writing-rules.md` first. Four paragraphs, 250 to 350 words, no em dashes,
routed through the `humanizer` skill before saving.

Write `cover-letter.md`, then render it to a PDF that matches the CV's visual
identity, using the bundled script:

```bash
# RenderCV bundles the typst package the script needs, so run it under
# RenderCV's interpreter rather than a bare python3. Resolve the path:
PY=$(dirname "$(readlink -f "$(command -v rendercv)")")/python

"$PY" scripts/render_letter.py "$S/cover-letter.md" \
  "$S/<Lastname>_<Company>_CoverLetter.pdf" \
  --name "Ada Lovelace" --location "London, United Kingdom" \
  --email "ada@example.com" --phone "+44 7700 900000"
```

If that resolution fails, run the script under plain `python3`: it detects the
missing `typst` import and prints the exact interpreter to re-run it with. Read
`scripts/README.md`.

Verify no em dashes survived before moving on:

```bash
python3 -c "t=open('$S/cover-letter.md').read(); print(t.count(chr(8212)))"
```

Skip the cover letter when the form does not ask for one and the posting does
not mention one. An unrequested cover letter is rarely read. Mention that it was
skipped.

## Phase D: fill the form

The posting may have an Apply button, or link out to a separate applicant
tracking system. Follow it, and check whether it opened a new tab.

Drive the form with ego-browser, per its skill. Work field by field: identify
the label and input type, resolve the value from the source of truth, fill it,
move on.

### Resolving values

| Field asks for | Source |
|---|---|
| Name, email, phone, address, links | `profile/identity.md` |
| Work authorization, sponsorship, notice, salary, start date | `profile/logistics.md` |
| Gender, ethnicity, veteran, disability | `profile/demographics.md` |
| A known question | `qa/answers.md` |
| A behavioural question | `qa/stories.md` |
| Why this company, why this role | Write it, using `job.md` and `narrative.md` |
| CV, cover letter, portfolio | The files just produced |

### Stop and ask when

- **No confident match.** The question is not in the bank and is not derivable.
- **Low-confidence match.** A stored answer is related but not equivalent.

Fill everything resolvable first, then ask, so the user answers once rather than
per field. Working alone, batch the questions with `AskUserQuestion`. As a
subagent you have no route to the user and must not call it: carry the questions
in the `unanswered` field of your `SUBMIT-REQUEST`, or send `BLOCKED` if one of
them stops you filling the rest.

When genuinely torn between high and low confidence, treat it as low. Asking is
cheap. A wrong answer submitted to an employer cannot be corrected.

Be careful with authorization questions that look like inversions but are not.
"Are you authorized to work in X?" and "Will you require sponsorship?" both come
from `profile/logistics.md`, not from paraphrasing one into the other.

**When the posting states a salary band and the top of it is below the figure
the profile would quote, stop and ask.** Naming a number well above the
advertised maximum screens the application out on a field that was never the
real constraint. This is a per-job judgement, not a formula.

### What goes wrong on application forms specifically

The `ego-browser` skill covers stale refs, pointer interception, and the rest of
the generic failure modes. These are the ones peculiar to applying for jobs, and
each has cost a real application:

- **A failed submit can silently drop your uploads.** Seen on Greenhouse and
  Teamtailor: a validation error on one field clears the attached files without
  saying so. After *any* validation error, re-verify every field **and every
  upload** before resubmitting.
- **Verify an upload by the filename the page displays.** A plain file input
  renders the name next to it and that is the thing to read. Custom upload
  widgets replace the underlying input after a successful upload, so the input's
  `files` property reads empty on a form that is perfectly filled: trust what the
  page shows over what the property says. Never treat an empty `files` as proof
  the upload failed.
- **ATS boards pre-fill stale data from earlier applications.** An old CV from a
  previous application on the same board, junk education rows, a first-name
  field showing a doubled value from autofill overlap. Never assume a pre-filled
  field is correct. Read it, and clear it explicitly when it is wrong.
- **Constrained dropdowns may not contain the user's real answer.** A university
  list without their institution, an ethnicity list without a "prefer not to
  say". Do not pick the nearest wrong option. Leave it and ask.
- **Suggestion lists need keyboard selection.** Clicking a typeahead's list can
  silently select a different entry than the one intended, and a wrong city
  submits just as cleanly as a right one. Select with the keyboard and confirm
  the committed value.
- **Account creation.** Workday and similar often demand a new account. Ask the
  user rather than creating one, since it means credentials to manage.
- **Multi-step forms.** Complete each page, verify it, then advance. Going back
  often loses entered data.

**LinkedIn Easy Apply is the expensive case.** Its overlays intercept clicks and
its modal is resistant in ways ordinary ATS forms are not. Budget more turns for
it, and prefer handling it yourself rather than delegating it (see
`orchestration.md`).

## Phase E: verify, then submit

**This phase always runs, regardless of `auto_submit`.**

Re-read the completed form and check every field holds the intended value, then
screenshot to `screenshots/pre-submit.png`.

Verify:

- Every required field is populated.
- Each value matches what was intended. Watch for truncation at a maxlength, an
  autocomplete overwriting a selection, and a dropdown that silently reset.
- Uploaded filenames appear, as the page displays them.
- Long text was not cut off.
- No validation errors are showing.

Checked state is worth verifying directly rather than by eye: a radio or
checkbox that looks unset in a page snapshot is often set. Read the control's
actual state before concluding a click failed and clicking again.

A field that will not verify after retries **becomes a question for the user**,
even under auto-submit. This is the one place autonomy stops, because a
submitted application cannot be recalled. Report the specific field and what it
contains versus what it should contain.

Then, **if an orchestrator spawned you**, stop here regardless of `auto_submit`
and send it a submit request:

```
SUBMIT-REQUEST | <company> | <role>
space: <spaceId>   folder: applications/<slug>/
track: <track>, because <one line>
fields:
  <label> = <value as submitted>
  ...every field, including uploads by the filename the page displays
unanswered: <none | the question, and what you would propose>
odd: <anything about the posting or form that looked wrong>
screenshot: applications/<slug>/screenshots/pre-submit.png
```

Then wait. The reply is one of `APPROVED` (submit now), `CORRECT: <field> =
<value>` (fix, re-verify, re-request), or `ABORT: <reason>` (do not submit; see
below). Write `answers.md` before requesting approval, not after, so the
orchestrator can check your answers against the workspace.

**Otherwise, working alone:**

- **`auto_submit: true`** and everything verified: submit.
- **`auto_submit: false`**: present a summary of every field and answer, and wait
  for explicit confirmation. If the user is not there to confirm, log the row
  with `status: awaiting_review` and stop. The work is finished and correct;
  only the click is outstanding. Do not log it as `incomplete`, which means
  something could not be filled.

**Confirm the submission actually landed.** Affirmative confirmation text, a
reference number, or a redirect to a success URL. Never infer success from the
absence of an error: a form that silently failed validation looks much like one
that succeeded. Screenshot to `screenshots/confirmation.png`.

A subagent then reports the result and the row for the orchestrator to log:

```
SUBMITTED | <company> | <role>
confirmation: <the exact affirmative text, or the URL it landed on>
screenshot: applications/<slug>/screenshots/confirmation.png
log-row: <the twelve values in the order of the log.csv header, comma-joined,
          quoting any field that contains a comma>
```

**Finish the task space with `task.finish({ keep: [] })` once the application is
genuinely done**, and only then. Leave it open when anything is outstanding,
including after an `ABORT` or a hand-back: it still holds the filled form, and
the orchestrator or the user may need to pick it up. Do not close it to tidy up.

## Phase F: record

**If an orchestrator spawned you, skip the append.** You already sent it the row
in `SUBMITTED`; it owns the file. Write `answers.md` and stop. Several processes
appending to one CSV corrupt it.

Otherwise, append one row to `applications/log.csv`. Quote any field containing a
comma.

Every value below is a placeholder, including the date. Substitute all twelve
columns from this application, in the header's order, and use today's actual
date rather than copying the one shown:

```bash
printf '%s\n' '2026-09-02,Acme Corp,Forward Deployed Engineer,https://...,greenhouse,fde,applied,applications/2026-09-02-acme-corp-forward-deployed-engineer/Lovelace_Acme_ForwardDeployedEngineer.pdf,applications/2026-09-02-acme-corp-forward-deployed-engineer/Lovelace_Acme_CoverLetter.pdf,<session-id>,2,' >> "$W/applications/log.csv"
```

Confirm the row landed and the column count matches the header, since a
malformed row corrupts the duplicate check that every future application depends
on:

```bash
python3 -c "
import csv
rows = list(csv.reader(open('$W/applications/log.csv')))
print(len(rows[-1]), 'fields, header has', len(rows[0]))"
```

Use a real CSV parser, not `awk -F,`. Splitting on commas miscounts any row with
a quoted comma in it, which is exactly the row worth checking.

Include the Claude Code session id when available, so an application can be
traced back to the conversation that produced it.

**As a subagent, you are done.** You wrote `answers.md` before requesting
approval and the orchestrator has your row. Report any answer worth reusing and
let it harvest them once across the whole run, rather than saving them yourself.

Otherwise, write `answers.md` in the application folder: every question and the
answer submitted, with its `source`.

Then offer to save genuinely reusable answers to `qa/answers.md`. A question that
will recur is worth storing; one specific to this company is not.

## When it truly cannot proceed

After exhausting the `ego-browser` skill's escalation ladder, hand over rather
than guessing. Leave the browser on the page with everything filled, and:

- Tell the user exactly which fields remain and what to put in them
- Confirm the CV and cover letter are saved and where
- Log `status: incomplete` with the remaining work in `notes`

A partially filled form the user finishes in two minutes is a good outcome. A
form submitted with fabricated answers is not.

**As a subagent, hand over to the orchestrator rather than the user**, and do it
as soon as you are genuinely blocked rather than after a long silence:

```
BLOCKED | <company> | <role>
space: <spaceId>   folder: applications/<slug>/
problem: <what is blocking, in one or two lines>
tried: <what you attempted>
need: <the answer, decision, or action that would unblock you>
state: <what is already filled, and what is not>
```

Send this whenever a question is unanswerable from the workspace, a required
dropdown has no correct option, the posting turns out to be closed or is not the
job it claimed to be, the form demands a new account, the posting's stated salary
band sits below the profile's figure, or three attempts on the same element have
failed. Then wait. Do not guess, and do not open a second task space to escape a
stuck page.

When an orchestrator replies `ABORT`, report what state you are leaving behind:

```
ABORTED | <company> | <role>
space: <spaceId>   folder: applications/<slug>/
reason: <why>
log-row: <the twelve values, with status incomplete or failed, and the reason in notes>
```

Leave the task space open so the work is recoverable.
