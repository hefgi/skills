# Application folder schema

Structure of `applications/<slug>/`, the record of what was actually sent for
one application. Read this during an apply. The workspace-level files are in
`data-schema.md`.

## Contents

- [Layout](#applicationsslug)
- [job.md](#jobmd)
- [cv-overlay.yaml](#cv-overlayyaml)
- [answers.md](#answersmd)

## applications/&lt;slug&gt;/

One folder per application. Slug is `<YYYY-MM-DD>-<company>-<role-slug>`,
lowercased, non-alphanumerics collapsed to hyphens:
`2026-09-02-acme-corp-forward-deployed-engineer`.

```
├── job.md              # the posting: title, company, URL, full description, requirements
├── analysis.md         # chosen track, requirement-by-requirement match, gaps, emphasis
├── cv-overlay.yaml     # per-application overlay over base plus track
├── cv.pdf              # rendered CV, named per config
├── cover-letter.md     # source
├── cover-letter.pdf    # rendered
├── answers.md          # every question and the answer submitted, including one-offs
└── screenshots/        # pre-submit state, confirmation page
```

This folder is the record of what was actually sent. Keep it even on a failed
attempt, because the tailored CV and letter stay useful.

### job.md

```markdown
# <Role> at <Company>

url: https://...
platform: greenhouse
captured: 2026-09-02
location: London, UK (hybrid)
salary: not stated

## Description
Full text of the posting, as captured.

## Requirements
- Extracted, one per line

## Signals
What the posting reveals about what they actually want: repeated phrases,
ordering, seniority language.
```

### cv-overlay.yaml

Thin. Only what changes for this application.

```yaml
extends: fde        # which track this builds on

headline: Forward Deployed Engineer, AI and Agentic Systems

summary:
  - Rewritten for this posting, using only facts from cv-base.yaml.

# Reorder or rewrite specific highlights for emphasis.
experience:
  Example Corp:
    highlight_order: [2, 0, 1, 3]
    rewrite:
      0: Reworded to lead with the outcome this posting cares about.

skills_groups: [AI and Agents, Data and Infra]
```

Rewrites rephrase and reorder. A rewrite that introduces a number, a
technology, or a responsibility not present in `cv-base.yaml` is a fabrication,
regardless of how well it matches the posting.

### answers.md

```markdown
# Submitted answers

## Why do you want to work at Acme?
source: written for this application
reuse: never
---
The answer as submitted.

## What is your notice period?
source: qa/answers.md
reuse: always
---
One month from signing.
```

`source` records where each answer came from: `qa/answers.md`, `qa/stories.md`,
`profile/logistics.md`, `asked user`, or `written for this application`. This is
what makes it possible to see later which answers were improvised.

Under orchestration this file is the subagent's record of its own work, and the
orchestrator may read it when verifying a submit request. Write it before asking
for approval, not after.
