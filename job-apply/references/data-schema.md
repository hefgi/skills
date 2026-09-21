# Workspace data schema

Canonical spec for every file in the workspace. When reading or writing any
workspace file, follow this rather than inferring structure from existing
content. Consistency is the whole point: a profile written by one version of
this skill must be readable by the next.

## Contents

- [Layout](#layout)
- [.job-apply/config.yaml](#job-applyconfigyaml)
- [profile/identity.md](#profileidentitymd)
- [profile/logistics.md](#profilelogisticsmd)
- [profile/targets.md](#profiletargetsmd)
- [profile/narrative.md](#profilenarrativemd)
- [profile/demographics.md](#profiledemographicsmd)
- [cv/cv-base.yaml](#cvcv-baseyaml)
- [cv/design.yaml](#cvdesignyaml)
- [cv/tracks/<track>.yaml](#cvtrackstrackyaml)
- [qa/answers.md](#qaanswersmd)
- [qa/stories.md](#qastoriesmd)
- [applications/log.csv](#applicationslogcsv)
- [applications/<slug>/](#applicationsslug) — full spec in `application-schema.md`
- [Conventions](#conventions)

## Layout

```
<workspace>/
├── .job-apply/
│   └── config.yaml
├── profile/
│   ├── identity.md
│   ├── logistics.md
│   ├── targets.md
│   ├── narrative.md
│   └── demographics.md
├── cv/
│   ├── cv-base.yaml
│   ├── design.yaml
│   └── tracks/
│       └── <track>.yaml
├── qa/
│   ├── answers.md
│   └── stories.md
└── applications/
    ├── log.csv
    └── <YYYY-MM-DD>-<company>-<role-slug>/
```

The `profile/` files are markdown with `key: value` lines rather than YAML, so a
user can open and edit them without worrying about syntax. Parse them
tolerantly: match on the key name, ignore surrounding formatting, and treat a
missing or empty value as unknown rather than as an empty string.

## .job-apply/config.yaml

The workspace marker. Its presence is what makes a directory a workspace.

```yaml
version: 1
created: 2026-09-02

# Behaviour
auto_submit: true          # false turns the final submit into a confirmation gate
default_track: fde         # which cv/tracks/<track>.yaml to use when unsure

# Applying to several postings at once. See orchestration.md.
max_concurrent_applications: 5   # 0 or 1 forces serial

# Output naming. Placeholders: {lastname} {firstname} {company} {role} {track} {date}
naming:
  cv: "{lastname}_{company}_{role}"
  cover_letter: "{lastname}_{company}_CoverLetter"
```

`auto_submit` is the setting with real consequences. Respect it exactly. Under
orchestration it does not disable the subagent submit gate, which is
unconditional; it decides whether the orchestrator approves on the user's behalf
or takes the batch to them. See `orchestration.md`.

## profile/identity.md

Stable personal facts. Used to fill the top of nearly every application form.

```markdown
# Identity

name: Ada Lovelace
preferred_name: Ada
pronouns: she/her
email: ada@example.com
phone: "+441234567890"
location: London, UK
address_line_1: 12 Example Street
address_line_2:
city: London
postcode: N1 1AA
country: United Kingdom
website: https://example.com
linkedin: https://linkedin.com/in/example
github: https://github.com/example
other_links:
  - https://scholar.example.com/example
```

Phone numbers are stored in E.164 format (`+` and digits, no spaces) because
RenderCV requires it and most forms accept it. Quote the value in YAML contexts
so it is not read as a number.

`pronouns` exists so generated prose and form fields never have to guess. If the
user does not supply it, leave it empty and use they/them in any prose.

An empty `address_line_2` is normal. Do not delete the key, since a present-but
-empty key documents that the field was considered.

### Standing decisions

A `#` comment above a key is a **binding rule, not a note**. When a comment says
how to answer a whole class of question, follow it without re-deriving it and
without asking about it again.

```markdown
# LOCATION RULE: answer "London, UK" for any location, city, or
# "where are you based" question. Only a postcode or street-address
# field gets the address below.
location: London, UK
address_line_1: 12 Example Street
```

These exist because the same judgement recurs on every form, and recording it
once is what stops the skill asking a second time. They apply anywhere in
`profile/`. Write one whenever the user answers with a rule rather than a value.

## profile/logistics.md

The answers that gate an application. These are asked constantly and are
tedious to retype, which is exactly why they belong here.

```markdown
# Logistics

work_authorization: UK citizen, no sponsorship required
visa_status: n/a
requires_sponsorship: no
countries_authorized: United Kingdom, France
notice_period: 1 month
earliest_start_date: 2026-10-01
salary_expectation: 120000 GBP base
salary_flexibility: open for the right role and equity
work_preference: remote, or hybrid in London
willing_to_relocate: no
travel_willingness: up to 25%
security_clearance: none
criminal_record_declaration: none
```

`requires_sponsorship` and `work_authorization` are the two most frequently
asked and the two most consequential to get wrong. Confirm them during Setup
rather than inferring from location. A UK phone number does not prove right to
work.

**Salary, when the posting names its own band.** If the top of the posting's
range is below the figure `salary_expectation` would produce, stop and ask rather
than quoting the standing figure blind. Naming a number well above the advertised
maximum screens the application out on a field that was never the real
constraint. This is a per-job judgement for the user to make, not a formula.

`salary_expectation` is often a rule rather than a single number, for instance a
band that depends on how many days onsite the role requires. Write it as a
standing-decision comment, as above, so it is applied rather than re-derived.

## profile/targets.md

The roles the user is actually going after. Required, and read on every apply to
decide which track fits a posting.

```markdown
# Targets

## Track: fde
name: Forward Deployed Engineer
positioning: Hands-on engineer who works directly with customers, from scoping
  the problem to shipping and running it in production.
titles: Forward Deployed Engineer, Solutions Engineer, Applied AI Engineer
seniority: senior, staff
emphasize: customer-facing delivery, shipping speed, production ownership
deemphasize: org size, budget ownership, headcount

## Track: leadership
name: Engineering Leader
positioning: Engineering leader who has scaled teams and owned delivery at the
  org level.
titles: VP of Engineering, CTO, Head of Engineering, Director of Engineering
seniority: executive
emphasize: org scaling, hiring, delivery outcomes, strategy
deemphasize: individual tooling choices, hands-on implementation detail

## Avoid
- Roles requiring full-time onsite outside London
- Pure people-management with no technical scope
```

A track is a named audience, not a job title. Two tracks exist because a
hands-on hiring manager and an executive recruiter look for opposite signals in
the same career, and one document cannot satisfy both. `references/cv-review.md`
explains this at length.

Each track needs `emphasize` and `deemphasize`, because those two lists are what
drive tailoring. Without them a track is just a label.

## profile/narrative.md

Prose the user has approved about themselves. Source material for cover letters
and long-form answers, so the skill is recombining the user's own framing rather
than inventing a voice.

```markdown
# Narrative

## Positioning
One paragraph on what the user does and who they do it for.

## Career story
How the roles connect. Explains any pivot, gap, or overlap in plain terms, so
the same explanation is used consistently everywhere.

## Strongest proof points
- Scaled engineering from 15 to 40+ engineers
- Raised 1M pre-seed and seed, exited via share sale
- Built and ran data pipelines across 20+ chains and 100TB+

## Motivation
Why the user is looking, in a form that is honest and reusable.

## Known gaps
Things the user cannot claim, and the honest framing for each. Recording these
prevents overclaiming under pressure mid-application.
```

`Known gaps` is the most useful section here. When a posting demands something
the user lacks, the honest framing is already written and does not have to be
improvised into a cover letter.

## profile/demographics.md

Optional voluntary-disclosure answers (EEO in the US, similar elsewhere). Always
legitimate to decline, and declining is the default.

```markdown
# Demographics

# Every field here is voluntary. "prefer not to say" is a complete answer and
# is what will be submitted for anything left blank.

gender: prefer not to say
ethnicity: prefer not to say
veteran_status: prefer not to say
disability_status: prefer not to say
lgbtq_status: prefer not to say
```

Fill these from the file without asking again. If the file says prefer not to
say, select that option. Never pick a demographic value the user has not
recorded, and do not push the user to answer during Setup.

## cv/cv-base.yaml

The single source of truth for career facts, and a valid RenderCV input on its
own. Top-level `cv:` key only, with design kept separate.

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/rendercv/rendercv/refs/tags/v2.8/schema.json
cv:
  name: Ada Lovelace
  location: London, UK
  email: ada@example.com
  phone: "+441234567890"
  website: https://example.com
  social_networks:
    - network: LinkedIn
      username: example
    - network: GitHub
      username: example
  sections:
    summary:
      - Base summary, rewritten per application by the overlay.
    experience:
      - company: Example Corp
        position: Principal Engineer
        location: London, UK
        start_date: 2020-03
        end_date: present
        summary: One line of context when the company is not well known.
        highlights:
          - Every claim the user can defend, phrased as an outcome.
    skills:
      - label: AI and Agents
        details: comma, separated, list
    education:
      - institution: Example University
        area: Computer Science
        degree: BSc
        location: United Kingdom
        start_date: 2008
        end_date: 2012
    certifications:
      - bullet: Cert One (2021) · Cert Two (2018)
```

Rules for this file:

- **It holds every fact, including ones no single CV shows.** Tracks and overlays
  select from it. Nothing downstream may add a fact absent here.
- **Give highlights an id when a track needs to reference them.** A leading
  `[id]` marker names a bullet so a track can order, drop, or rewrite it by
  meaning rather than by position:

  ```yaml
  highlights:
  - "[scaling] Scaled engineering from 15 to 40+ across a squad structure."
  - "[budget] Owned a **$4M engineering budget** and put in ROI controls."
  ```

  `scripts/merge_cv.py` strips the marker before rendering, so it never reaches
  the PDF. Ids matter because the alternative is referring to a bullet by index,
  and an index silently retargets the moment a bullet is added above it. A
  retargeted rewrite is how a CV ends up claiming something the user did not do.
  Without a marker an id is derived from the first three words, which works but
  breaks when the bullet is reworded.
- Dates are `YYYY-MM` strings, or bare `YYYY` for education. `present` for a
  current role.
- Highlights are outcomes the user can defend in an interview.
- Keep the schema comment on line 1 so editors validate the file.
- Entry types available: `ExperienceEntry`, `EducationEntry`, `OneLineEntry`,
  `BulletEntry`, `TextEntry`, `NormalEntry`, `PublicationEntry`,
  `NumberedEntry`, `ReversedNumberedEntry`. Read the `rendercv` skill for field
  details.

## cv/design.yaml

Shared RenderCV design, top-level `design:` key only. One file for all tracks,
so every CV the user sends looks like it came from the same person.

```yaml
design:
  theme: engineeringresumes
  page:
    size: a4
    top_margin: 0.5in
    bottom_margin: 0.5in
    left_margin: 0.55in
    right_margin: 0.55in
    show_footer: true
  colors:
    name: rgb(20, 45, 80)
    section_titles: rgb(20, 45, 80)
    links: rgb(20, 45, 80)
    connections: rgb(60, 60, 60)
  typography:
    alignment: left
    font_size:
      body: 9.5pt
      name: 22pt
  header:
    connections:
      separator: "|"
      show_icons: false
      display_urls_instead_of_usernames: true
  section_titles:
    type: with_full_line
    space_above: 0.35cm
    space_below: 0.2cm
  sections:
    space_between_regular_entries: 0.3cm
    space_between_text_based_entries: 0.12cm
  entries:
    highlights:
      bullet: "●"
      space_between_items: 0.06cm
```

This template is verified to render. The nesting is easy to get wrong, so note
that font sizes live under `typography.font_size.{body,name}`, and bullets under
`entries.highlights.bullet`. There is no top-level `text` or `highlights` key,
and no `header.name_font_size`. RenderCV rejects unknown fields outright, so a
guess produces a validation error rather than being ignored.

To see the valid field tree for a theme, generate a fresh sample and inspect it:

```bash
rendercv new "Test User" --theme engineeringresumes
```

`engineeringresumes` is the default because it is restrained and parses cleanly
in applicant tracking systems. Bullet characters are restricted to
`● • ◦ - ◆ ★ ■ — ○`.

## cv/tracks/&lt;track&gt;.yaml

A track overlay. Maps a track in `profile/targets.md` to how the CV should be
shaped for that audience. Named for the track key, so `fde` becomes
`cv/tracks/fde.yaml`.

```yaml
track: fde
headline: Forward Deployed Engineer, AI and Agentic Systems

# Section order for this audience
section_order: [summary, experience, skills, education, certifications]

# Which experience entries appear, and how prominently.
# promote: its own entry. nest: a highlight under the named parent. omit: hidden.
experience:
  Example Corp:
    treatment: promote
    lead_with: hands-on
    highlight_order: [technical, customer, org]
  Small Client Gig:
    treatment: nest
    nest_under: Own Consultancy Ltd

skills_groups: [AI and Agents, Full-Stack, Data and Infra]

summary: Track-level summary, overridden per application by the overlay.
```

An overlay reorders, reweights, renames a title for accuracy, and rewrites
prose. It never introduces a fact. If a track needs a fact that is not in
`cv-base.yaml`, add it to the base first, then confirm with the user that it is
true.

`scripts/README.md` documents every key a track supports, including
`drop_highlights`, `max_highlights`, `position_override`, `nest_as`, and
`merged_entries` for collapsing older roles into one line. Run the script with
`--explain` to see what a track actually did, rather than inferring it from the
rendered PDF.

## qa/answers.md

The reusable Q&A bank. Read before every application. One block per answer,
separated by `---`.

```markdown
# Answers

## What is your notice period?
tags: logistics, availability
reuse: always
---
One month from signing.

## Describe a significant project you have built.
tags: project, technical, behavioural
reuse: always
---
Longer prose answer, reusable as-is across applications.

## Why do you want to work here?
tags: motivation, company-specific
reuse: adapt
---
Base framing to be re-pointed at the specific company. Never submit verbatim:
adapt it using the job posting, then submit the adapted version.
```

`reuse` values:

| Value | Meaning |
|---|---|
| `always` | Submit verbatim. Facts and stable stories. |
| `adapt` | A base framing that must be re-pointed at this company before use. |
| `never` | Not stored here at all. Kept only in the application folder. |

### Deciding whether an answer belongs here

One test: **would this answer still be true and appropriate if the company name
changed?**

- Yes, unchanged: store as `reuse: always`. Notice period, address, a project
  description, work authorization.
- Yes, but needs re-pointing: store as `reuse: adapt`. "Why this role", "why
  this space".
- No: do not store. "Why do you want to work at Acme specifically",
  "which of our products do you use". These go in the application folder only.

The user described this exactly: a phone number or "tell me one big project you
built" is worth keeping. "Why are you applying to company X" is not, because it
cannot be reused.

### Matching a form question to the bank

In order:

1. **Exact or near-exact heading match**, ignoring case, punctuation, and
   trailing whitespace. High confidence.
2. **Semantic match**, using tags and meaning. "How soon could you start?"
   matches "What is your notice period?" High confidence when the question is
   asking for the same underlying fact.
3. **Related but not equivalent.** Low confidence. Stop and ask.
4. **No match.** Stop and ask.

Confidence matters because of what it triggers. High confidence fills
unattended. Low confidence or no match stops and asks the user. When genuinely
uncertain between the two, treat it as low confidence: interrupting the user is
cheap, and submitting a wrong answer to a real employer is not.

Watch for questions that look similar but are not, particularly around
authorization. "Are you authorized to work in the US?" and "Will you require
visa sponsorship?" often have answers that are not simple inversions of each
other. Match these against `profile/logistics.md` rather than paraphrasing one
into the other.

## qa/stories.md

Behavioural answers in STAR form. Separate from `answers.md` because one story
answers many differently-worded questions, and because these get reused in
interviews too.

```markdown
# Stories

## Scaling a team through rapid growth
tags: leadership, hiring, scaling, conflict
situation: Team of 15 needed to reach 40 in 18 months.
task: Own hiring, structure, and delivery through the growth.
action: What the user actually did.
result: Reached 40+ engineers, improved lead time to change 2.5x.
use_for: tell me about scaling, hardest leadership challenge, biggest impact
```

`use_for` lists the question phrasings this story answers. It is the matching
key, so keep it generous.

## applications/log.csv

The audit trail. One row per application. Created with this exact header:

```csv
date,company,role,url,platform,track,status,cv_file,cover_letter_file,session_id,questions_asked,notes
```

| Column | Content |
|---|---|
| `date` | `YYYY-MM-DD` of submission |
| `company` | Company name as advertised |
| `role` | Job title as advertised |
| `url` | The posting URL |
| `platform` | `linkedin`, `greenhouse`, `lever`, `ashby`, `workday`, `direct`, `other` |
| `track` | Which track was used |
| `status` | See below |
| `cv_file` | Path to the submitted CV, relative to the workspace |
| `cover_letter_file` | Path to the cover letter, or empty if none was required |
| `session_id` | Claude Code session id, or empty if unavailable |
| `questions_asked` | Count of questions that needed the user |
| `notes` | Anything a human would want later. Quote if it contains a comma. |

`status` values:

| Status | Meaning |
|---|---|
| `applied` | Submitted, confirmation observed |
| `submitted_manually` | User finished it by hand |
| `awaiting_review` | Form filled and verified, waiting on the user to submit. The normal end state under `auto_submit: false`. |
| `incomplete` | Started, not submitted. `notes` says what remains. |
| `draft` | CV and cover letter produced, form never attempted |
| `failed` | Could not proceed. `notes` says why. |

`awaiting_review` and `incomplete` differ by whose turn it is. `awaiting_review`
means the work is done and correct, and the user only has to click submit.
`incomplete` means something could not be filled and the `notes` column says
what. Recording a verified-but-unsubmitted application as `incomplete` would
misreport finished work as a failure.

Standard CSV quoting: wrap any field containing a comma, quote, or newline in
double quotes and double any internal quote. Append rows, never rewrite the
file, so the log stays a reliable history.

A row is written for every attempt, including failures. A log that only records
successes cannot answer "did I already apply here?", which is the main question
it exists to answer. Check it before applying and warn on a duplicate URL or
company plus role.

**Under orchestration the orchestrator writes every row and subagents never open
this file for write.** Several processes appending at once interleave and corrupt
rows, and a corrupt row breaks the duplicate check. See `orchestration.md`.

## applications/&lt;slug&gt;/

One folder per application, holding `job.md`, `analysis.md`, `cv-overlay.yaml`,
the rendered CV and cover letter, `answers.md`, and screenshots.

Full spec in `references/application-schema.md`. Read that during an apply,
when you need the exact format of one of those files.

## Conventions

**Dates** are ISO `YYYY-MM-DD`, or `YYYY-MM` in CV entries where a day would be
false precision.

**Missing values** stay as present-but-empty keys rather than being deleted, so
it is clear the field was considered rather than forgotten. Treat empty as
unknown, and ask when it matters.

**Money** includes the currency: `120000 GBP`, not `120000`.

**Appending, not rewriting.** `log.csv` and `qa/answers.md` grow. Add to them.
Rewriting risks losing history the user cannot reconstruct.

**Editability.** A user will open these files by hand. Keep them readable, keep
comments that explain non-obvious fields, and do not reformat a file just
because you touched one value in it.
