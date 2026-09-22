# Workflow 1: Setup

Bootstrap the workspace and gather enough real career context that the other two
workflows never have to invent anything.

Setup is a conversation, not a form. The user is handing over their career
history and personal details, so explain what is being created and why before
creating it.

## Contents

- [Step 1: check for an existing workspace](#step-1-check-for-an-existing-workspace)
- [Step 2: check tooling](#step-2-check-tooling)
- [Step 3: explain, then create the structure](#step-3-explain-then-create-the-structure)
- [Step 4: seed from real context (required)](#step-4-seed-from-real-context-required)
- [Step 5: interview for what seeds cannot supply](#step-5-interview-for-what-seeds-cannot-supply)
- [Step 6: define target tracks (required)](#step-6-define-target-tracks-required)
- [Step 7: build the CV files](#step-7-build-the-cv-files)
- [Step 8: confirm inferred facts](#step-8-confirm-inferred-facts)
- [Step 9: render and verify](#step-9-render-and-verify)
- [Step 10: seed the Q&A bank](#step-10-seed-the-qa-bank)
- [Step 11: report](#step-11-report)
- [Re-running setup](#re-running-setup)

## Step 1: check for an existing workspace

Use `find_workspace` from `SKILL.md` (searches up, then down, then honours
`$JOB_APPLY_HOME`).

A workspace existing is not the same as setup having finished. Setup is a long
conversation and gets interrupted, so **check completeness before deciding what
to do**:

```bash
W=<workspace>
for f in profile/identity.md profile/logistics.md profile/targets.md \
         profile/narrative.md profile/demographics.md \
         cv/cv-base.yaml cv/design.yaml \
         qa/answers.md qa/stories.md applications/log.csv; do
  [ -s "$W/$f" ] || echo "MISSING: $f"
done
[ -n "$(ls -A "$W"/cv/tracks 2>/dev/null)" ] || echo "MISSING: cv/tracks/ (no track defined)"
```

Three cases, and they lead to different places:

- **Nothing found.** Fresh setup. Continue to step 2.
- **Found and complete.** Setup has already run. Report where it is and what it
  contains, then ask which part to update. Never overwrite wholesale: it holds
  data the user cannot easily reconstruct. See
  [Re-running setup](#re-running-setup).
- **Found and incomplete.** Setup was interrupted. Say so plainly, list what is
  missing, and **resume from the first missing piece** rather than restarting.
  Skip the steps whose outputs already exist and are non-empty. Re-asking a user
  for their phone number because the conversation dropped is exactly the failure
  this workspace exists to prevent.

A file that exists but is empty counts as missing, which is why the check uses
`-s`. Step 3 writes skeletons, so an empty-valued file is normal mid-setup and
means that step still needs doing.

If `$JOB_APPLY_HOME` is set, that is the workspace, regardless of the search.

## Step 2: check tooling

```bash
rendercv --version || echo "MISSING: uv tool install \"rendercv[full]\""
export PATH="$HOME/.local/bin:$PATH"
command -v ego-browser || echo "MISSING: see Prerequisites in SKILL.md"
```

Also check that the `ego-browser` skill is available, since it is the browser
manual this skill defers to.

RenderCV is needed from step 9. The browser is needed only if seeding from a
LinkedIn URL, or later when applying. Missing either is not a reason to stop
setup, so note it and continue. Setting up ego lite needs the user at the
keyboard for a GUI onboarding step, so it is better done when they are ready
rather than in the middle of an interview.

## Step 3: explain, then create the structure

Tell the user what is about to exist and where. Keep it short, and be concrete
about the personal data:

> This creates a `job-apply/` directory holding your profile, CV sources, a
> reusable answer bank, and an application log. `profile/` will contain your
> phone number and address, so if this directory is inside a git repository you
> may want to gitignore it.

Default location is `./job-apply/` in the current directory. Confirm it, since
the user may want it elsewhere.

```bash
W="./job-apply"   # or the confirmed location
mkdir -p "$W"/.job-apply "$W"/profile "$W"/cv/tracks "$W"/qa "$W"/applications
```

Write `.job-apply/config.yaml` and the `log.csv` header now, so the workspace is
valid even if the conversation is interrupted:

```bash
printf 'date,company,role,url,platform,track,status,cv_file,cover_letter_file,session_id,questions_asked,notes\n' > "$W"/applications/log.csv
```

**Then create every profile and qa file as a skeleton, before the interview
starts.** Use the templates in `data-schema.md`, with the keys present and the
values empty. Fill them as the interview proceeds.

```bash
for f in profile/identity.md profile/logistics.md profile/targets.md \
         profile/narrative.md profile/demographics.md \
         qa/answers.md qa/stories.md; do
  [ -e "$W/$f" ] || : > "$W/$f"     # then write the template into it
done
```

Creating them up front is what makes step 1's completeness check meaningful and
what makes an interrupted setup resumable. A skeleton with empty keys says "this
was considered and not yet answered". A file that does not exist says nothing,
and the next run cannot tell how far it got.

Do not skip this because the interview will fill them anyway. Interruption is
the normal case, not the exceptional one: setup asks for a lot, and users step
away.

## Step 4: seed from real context (required)

Ask for at least one of:

1. **LinkedIn profile URL**
2. **An existing CV or resume** (PDF, DOCX, or RenderCV YAML)

Both is better. Do not proceed without one. Everything downstream depends on
real employment history, and the alternative is interviewing the user through
fifteen years of career detail one question at a time, or worse, inventing it.

If the user has neither, the honest answer is that they should write a rough CV
first, even a bad one, and come back. A one-page draft is enough to seed from.

### Seeding from a CV file

Read it. PDFs and DOCX can be read directly. Extract into `cv-base.yaml`
structure: name, contact, every role with company, title, location, dates,
bullets, education, certifications, skills.

Preserve the user's own phrasing at this stage. Setup captures facts; the CV
review workflow improves phrasing. Rewriting during extraction makes it hard for
the user to confirm the extraction was faithful.

### Seeding from LinkedIn

LinkedIn requires a logged-in session. Read the `ego-browser` skill, open the
profile URL in a task space, and read the page text.

Experience entries may be collapsed behind a "show all" link. Look for it, click
through, and re-extract. Close the task space when finished.

If LinkedIn is not signed in, ask the user to log in rather than working around
it. Ego lite may be a fresh profile even when the user is signed in elsewhere.

LinkedIn dates are month-and-year granular and often show only durations, so
reconstructed dates are inferences. They go in the step 8 confirmation list.

## Step 5: interview for what seeds cannot supply

Batch these with `AskUserQuestion`. Grouping them means the user answers once
rather than being interrupted repeatedly.

**Identity gaps** (whatever the seed did not give): preferred name, pronouns,
phone, full postal address, personal website, GitHub, other links.

A CV rarely carries a street address, so seeding from one almost always leaves
`address_line_1`, `city`, and `postcode` empty. Application forms ask for them
constantly. Ask for the address explicitly here rather than discovering it is
missing halfway through a form, where the user is waiting and the browser is
open. The same goes for `pronouns`, which some forms ask directly.

**Logistics**, none of which appear on a CV and all of which get asked on forms:

- Work authorization: which countries, and does any require sponsorship?
- Notice period and earliest start date
- Salary expectation, with currency, and how flexible
- Remote, hybrid, or onsite preference
- Willing to relocate?
- Travel willingness
- Security clearance, if relevant to their field

Ask work authorization directly rather than inferring it from location. A phone
number or an address does not establish right to work, and getting it wrong on a
form is a serious error.

**Demographics** (voluntary): mention that `profile/demographics.md` exists,
defaults to "prefer not to say" for everything, and can be edited by hand at any
time. Do not walk the user through each field. Declining is a complete answer,
and this skill should not apply pressure on it.

**When the user answers with a rule rather than a value, record the rule.**
"Always say London unless they want a postcode" and "quote the higher band if
it is more than two days onsite" are decisions, not data, and writing them down
as a `#` comment above the relevant key is what stops the question being asked
again on the next form. See the standing decisions section of `data-schema.md`.

## Step 6: define target tracks (required)

Ask what roles the user is targeting. This is a required field, not a nicety:
the apply workflow uses tracks to decide how to shape a CV for a given posting.

Most people have one or two. Two very different targets, such as a hands-on
engineering role and an executive role, need separate tracks because the two
audiences look for opposite signals in the same career. Read `cv-review.md` for
why, and explain it to the user if they are unsure whether they need one track
or two.

For each track, capture: a key (`fde`), a display name, a positioning sentence,
target titles, seniority level, and the `emphasize` / `deemphasize` lists.

The `emphasize` and `deemphasize` lists do the actual work. A track without them
is a label that changes nothing. Push for specifics: not "leadership" but "org
scaling, hiring, delivery outcomes".

Also ask what to rule out, and record it under `## Avoid`. It prevents wasted
effort later.

Write `profile/targets.md`.

## Step 7: build the CV files

**`cv/cv-base.yaml`** from the seed. Every fact, including ones that will not
appear on any single CV. Keep the schema comment on line 1. Phone in E.164.

**`cv/design.yaml`** from the `data-schema.md` template, theme
`engineeringresumes`. Ask whether the user wants a different theme, and mention
that `engineeringresumes` is chosen for parsing cleanly in applicant tracking
systems. Available: `engineeringresumes`, `classic`, `sb2nov`, `moderncv`,
`engineeringclassic`, `bronzor`.

**`cv/tracks/<track>.yaml`** per track from step 6, with headline, section
order, and per-company treatment.

Then apply the structural checks from `cv-review.md`, specifically the timeline
integrity pass. Overlapping full-time roles, unexplained gaps, and facts that
contradict between tracks are all much cheaper to fix now than after they have
been sent to twenty employers. Report what you find and offer to fix it, but do
not silently alter the user's history.

## Step 8: confirm inferred facts

List everything derived rather than read, and confirm it in one batch. Typical
inferences: a company's location, a date reconstructed from a duration, a job
title normalized to a standard form, a seniority level, an employment type.

Silent wrong inferences are the main way this data goes bad, and they are
expensive later because the user has to defend a CV they did not write. Confirm
before writing.

Present them compactly, as a list the user can correct in one message rather
than a question each.

## Step 9: render and verify

Render each track to confirm the toolchain works end to end. Use absolute paths,
for the reason explained in `cv-review.md`'s
[RenderCV mechanics](cv-review.md#rendercv-mechanics) section:

```bash
rendercv render "$W/cv/cv-base.yaml" --design "$W/cv/design.yaml" \
  -o /tmp/job-apply-check \
  --pdf-path /tmp/job-apply-check/<track>.pdf \
  --dont-generate-markdown --dont-generate-html
```

Keep PNG output on for this first render, so page count and layout can be
eyeballed. Report the page count per track. Two pages is fine for senior
profiles. Three or more usually means the CV needs the trimming pass from
`cv-review.md`.

A RenderCV validation error here is useful: it means `cv-base.yaml` has a
structural problem worth fixing now. Read the `rendercv` skill for field
requirements.

## Step 10: seed the Q&A bank

Create `qa/answers.md` and `qa/stories.md`. Pre-populate `answers.md` from data
already collected, since these questions are asked on nearly every form:

- Notice period, from logistics
- Earliest start date, from logistics
- Salary expectation, from logistics
- Work authorization and sponsorship, from logistics
- Address and phone, from identity

Then ask for one or two stories, using the STAR structure in `data-schema.md`.
The highest-value ones, because they are asked constantly in different wordings:

- A significant project the user built, with their specific role in it
- A hard problem they solved, with the outcome

Two good stories are worth more than eight thin ones. The bank grows naturally
as applications surface new questions, so do not try to be exhaustive now. Say
that, so the user does not feel they need to answer everything up front.

## Step 11: report

Show the user what exists, in a short tree. Then state plainly:

- Where the workspace is
- Which tracks are defined
- Page count per track
- What is still empty and will be asked on first use, typically the Q&A bank
- That `profile/` holds personal data, and whether it is inside a git repository
- How to apply: share a job posting URL

Run the step 1 completeness check again here and report anything still missing.
Call out empty fields in `identity.md` and `logistics.md` specifically, since
those are the ones that stall a live application:

```bash
grep -nE '^[a-z_]+:[[:space:]]*$' "$W"/profile/identity.md "$W"/profile/logistics.md
```

An empty `address_line_1` or `requires_sponsorship` is worth one more question
now. Mid-form is the worst time to find out, because the user is waiting and a
half-filled application is sitting in a browser.

If anything from step 7's structural check went unresolved, restate it here. It
matters more than the rest of the report, because it affects every CV sent from
this workspace.

## Re-running setup

Setup is safe to re-run and must never clobber. When a workspace exists:

- Ask what to update: profile, tracks, CV base, or design
- Update only that
- Leave `applications/` and `qa/` untouched unless explicitly asked
- Re-run the timeline integrity check after any `cv-base.yaml` change, and
  re-check that tracks still agree with the base on every fact
