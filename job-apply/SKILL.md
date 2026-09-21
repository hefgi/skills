---
name: job-apply
description: >-
  Tailor a CV and cover letter to a specific job posting and apply to it
  automatically in the browser. Use this skill whenever the user shares a job
  posting URL, asks to apply for a job, wants a CV or resume tailored to a
  specific role or company, wants a cover letter written for an application,
  asks to review or optimize their CV, or wants to track which jobs they have
  applied to. Also use it when the user mentions job hunting, job applications,
  LinkedIn job posts, Greenhouse, Lever, Ashby, Workday, or Easy Apply, even if
  they do not name this skill. Handles a batch of postings in parallel when the
  user has several. Maintains a reusable profile so application answers, contact
  details, and target roles never need re-entering.
---

# Job Apply

Turn a job posting URL into a tailored CV, a cover letter, and a submitted
application, using a durable profile so the same facts are never re-entered.

## The workflows

| The user wants | Workflow | Read |
|---|---|---|
| First-time use, or no workspace exists | Setup | `references/setup.md` |
| Review, critique, or improve a CV | CV review | `references/cv-review.md` |
| Apply to one job posting | Apply | `references/apply.md` |
| Apply to several postings at once | Orchestrate | `references/orchestration.md` |

Every workflow depends on the workspace. Resolve it first.

Load these when the moment comes, not up front:

| Read when | File |
|---|---|
| About to drive the browser | the `ego-browser` skill |
| Writing any prose the user will send | `references/writing-rules.md` |
| Reading or writing a workspace file | `references/data-schema.md` |
| Reading or writing a file in `applications/<slug>/` | `references/application-schema.md` |

`references/orchestration.md` is for the orchestrating agent only. Do not hand it
to a subagent that is applying to a single job.

## Step 0: resolve the workspace (always do this first)

The workspace is a directory holding the user's profile, CV sources, Q&A bank,
and application log. It belongs to the user, not to this skill. Nothing personal
is ever written inside the skill directory.

Resolution order:

1. `$JOB_APPLY_HOME`, if set.
2. Walk **up** from the current directory looking for `.job-apply/config.yaml`.
   The directory containing `.job-apply/` is the workspace.
3. Look **down** one or two levels, for a subdirectory holding
   `.job-apply/config.yaml`. This matters because the workspace is usually a
   `job-apply/` folder inside a project, and a user sitting in the project root
   is below nothing and above the workspace.
4. If none is found, the workspace does not exist yet. Run **Setup**.

```bash
# Search up, then down. Prints the workspace path, or "none".
find_workspace() {
  [ -n "$JOB_APPLY_HOME" ] && { echo "$JOB_APPLY_HOME"; return; }
  d="$PWD"
  while :; do
    [ -f "$d/.job-apply/config.yaml" ] && { echo "$d"; return; }
    [ "$d" = "/" ] && break
    d=$(dirname "$d")
  done
  hit=$(find "$PWD" -maxdepth 3 -type f -path '*/.job-apply/config.yaml' 2>/dev/null | head -1)
  [ -n "$hit" ] && { dirname "$(dirname "$hit")"; return; }
  echo "none"
}
find_workspace
```

Finding more than one workspace means the user has two. Ask which to use rather
than picking, since applying from the wrong one sends the wrong CV.

If the user asks to apply to a job and no workspace exists, say so plainly and
run Setup first. Applying without a profile would mean inventing facts about
someone's career, which is the one thing this skill must never do.

Read `references/data-schema.md` for the format of any workspace-level file, and
`references/application-schema.md` for the files inside an application folder.
They are the canonical spec, so prefer them over inferring structure from
whatever files happen to exist.

## Ground rules

These hold across every workflow, and across every agent in an orchestrated run.

**Never invent a fact about the user.** Employment dates, job titles, team
sizes, metrics, and qualifications come from the workspace or from the user.
Tailoring means choosing what to emphasize and how to phrase it. It never means
adding an achievement that is not already on record. A fabricated CV is worse
than no CV, because the user has to defend it in an interview.

**Ask rather than guess.** When a form asks something the workspace cannot
answer, ask the user. Use `AskUserQuestion` and batch related questions so the
user answers once rather than five times.

**Verify inferred facts.** When you derive something rather than read it, such
as a location implied by a company name or a date range reconstructed from a
PDF, confirm it before writing it to the workspace. Silent wrong inferences are
the most common way this kind of data goes bad.

**No em dashes in generated prose.** Cover letters and application answers use a
comma, a period, or a restructured sentence instead. Read
`references/writing-rules.md` before writing any prose, and route it through the
`humanizer` skill.

**The user's browser is not yours.** Never clear cookies, cache, or storage at
the profile level. Those operations reach every site the user is signed into,
they cannot be undone, and under orchestration they break every other agent
sharing the profile. A problem with one site is solved at that site's scope or
not at all.

## Prerequisites

Check these before a workflow needs them, and offer to fix them rather than
failing mid-flow.

| Tool | Check | Needed for |
|---|---|---|
| RenderCV | `rendercv --version` | Rendering any CV |
| ego lite | `export PATH="$HOME/.local/bin:$PATH"; command -v ego-browser` | Apply, orchestrate, LinkedIn seeding |
| `ego-browser` skill | listed in available skills | Apply, orchestrate |
| `humanizer` skill | listed in available skills | Polishing generated prose (optional) |

Install RenderCV with `uv tool install "rendercv[full]"`.

`humanizer` is optional. When it is not installed, apply the "Patterns to avoid"
section of `references/writing-rules.md` by hand instead. That list is what the
humanizer would catch, so the prose still gets checked. Say which route was
taken rather than silently skipping the step.

RenderCV is the recommended CV toolchain and the one this skill is built around.
`references/cv-review.md` explains why and how. A user who insists on another
tool can still use Setup and the Q&A bank, but the tailoring workflow assumes
RenderCV's YAML input.

### Setting up ego lite

This skill drives the browser with ego lite. That is a hard requirement rather
than a preference: an application means uploading a CV to a form on a site the
user is signed into, and ego lite is the only browser tested here that does both
at once. It is macOS-only today, and it needs a one-time setup the user performs
in a GUI.

**When the `ego-browser` skill is not installed**, it has to be added before
anything else, since it carries both the browser manual and the installer. Ask
the user to add it from `citrolabs/ego-lite` by whatever mechanism their setup
uses for skills. The request they can hand to an agent verbatim:

> Set up ego lite for me: https://github.com/citrolabs/ego-lite
>
> Read `skills/ego-browser/references/install.md` and follow the steps to
> install ego lite.

Once the skill is present, its `references/install.md` is readable and the steps
below apply.

**When the skill is present but `ego-browser` is not on the PATH**, read that
skill's `references/install.md` and follow it. In outline:

1. Run the install script that ships inside the `ego-browser` skill, at
   `scripts/install.sh` relative to that skill's own directory. Locate it from
   the skill rather than assuming a path, since where skills live differs
   between setups. It downloads and installs the app, then opens it.
2. **Stop. The user completes first-run onboarding in the GUI.** You cannot do
   this step. Onboarding is what puts `ego-browser` on the PATH, and it offers to
   import from Chrome, which is how the user's logged-in sessions carry across.
3. Poll rather than asking twice:

   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ego-browser nodejs -e 'console.log("READY")'
   ```

   Re-run it once after the user says they are done. `READY` means go.

   Anything else is a diagnosis, not a reason to ask again. `command not found`
   usually means `~/.local/bin` is not on the PATH rather than that onboarding
   failed. A Gatekeeper block, a failed download, and an app that was never
   reopened all look different and are all covered in that skill's
   `references/install.md` troubleshooting section. Read it, report what you
   actually saw, and act on it. Do not re-run the probe in a loop: after two
   attempts, hand the specific error back to the user.
4. **Probe the session rather than assuming it.** Even after an import, a given
   site may not be signed in. Check before relying on it, and ask the user to log
   in if it is missing.

Not on macOS: point the user at https://lite.ego.app/ and say the install script
is macOS-only.

## Workspace shape

Created by Setup, read by everything else. Full spec in
`references/data-schema.md`.

```
<workspace>/
├── .job-apply/config.yaml      # workspace marker and settings
├── profile/                    # who the user is: identity, logistics, targets, narrative
├── cv/                         # cv-base.yaml (facts), design.yaml, tracks/<track>.yaml
├── qa/                         # answers.md (reusable Q&A bank), stories.md
└── applications/               # log.csv plus one folder per application
```

Setup creates every one of these as a skeleton before interviewing, so an
interrupted setup can resume rather than restart. A workspace existing does not
mean setup finished: `references/setup.md` step 1 has the completeness check.

`profile/` contains personal data including phone number and address. Mention
this if the user is working inside a git repository, so they can decide whether
to commit it.

## Applying: the shape of it

Detail is in `references/apply.md`. The order matters, so do not reorder these.

1. **Load** every file in `profile/`, `qa/`, and `cv/` before touching the
   browser. This is what stops the skill asking for data it already has. Read the
   `ego-browser` skill before the first browser call.
2. **Extract** the posting into `job.md`, after confirming it is still open.
3. **Tailor** the CV with `scripts/merge_cv.py` and write the cover letter.
4. **Fill** the form, stopping only for unknown or low-confidence answers.
5. **Verify** every field reads back correctly, then submit.
6. **Record** a row in `applications/log.csv`.

Auto-submit is the default. `auto_submit: false` in the config turns it into a
confirmation gate. Either way, step 5 runs: a field that will not verify becomes
a question for the user rather than a garbled submission, because a submitted
application cannot be taken back.

## Applying to many jobs

When the user has several postings, one subagent per posting applies to them in
parallel. Each fills and verifies its form, then stops and asks before
submitting. `references/orchestration.md` is the full protocol, including the
concurrency cap and who owns the log. Read it before spawning anything.
