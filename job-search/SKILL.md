---
name: job-search
description: >-
  Sweep job boards in the browser and build a deduplicated pipeline of roles
  worth applying to. Use this skill whenever the user asks to find jobs, search
  for roles, look for openings, sweep LinkedIn or a job board, refresh or top up
  their job pipeline, asks what roles are out there right now, or wants to set
  up their job search criteria. Also use it when the user mentions job hunting,
  sourcing roles, job boards, LinkedIn job search, Ashby, Greenhouse, Lever,
  Wellfound, or Y Combinator jobs and they are looking rather than applying.
  Reads the same workspace as job-apply, so a role already applied to is never
  surfaced twice, and hands each new role to job-apply for the application
  itself.
---

# Job Search

Turn a description of the roles someone wants into a deduplicated CSV of live
postings to apply to, swept from the boards in their own browser.

This skill finds jobs. It does not apply to them: a posting in the pipeline is
handed to `job-apply`, which owns CVs, cover letters, and forms.

## The workflows

| The user wants | Workflow | Read |
|---|---|---|
| First-time use, or no search criteria exist | Setup | `references/setup.md` |
| Find jobs now, refresh or top up the pipeline | Sweep | `references/search.md` |
| Sweep several sources at once | Orchestrate | `references/orchestration.md` |
| Add a job board the workspace does not know | Discover | `references/discovery.md` |

Every workflow depends on the workspace. Resolve it first.

`references/orchestration.md` is for the orchestrating agent only. Do not hand it
to a subagent that is sweeping a single source, or it will fan out again.

Applying to a posting, rather than finding one, is the `job-apply` skill's work.
The signal is whether there is a posting URL: one URL means apply, no URL and a
request to look for roles means search. This skill writes a pipeline of postings
into the same workspace and hands them to `job-apply` one at a time.

Load these when the moment comes, not up front:

| Read when | File |
|---|---|
| About to drive the browser | the `ego-browser` skill |
| Reading or writing `search.md` or `pipeline.csv` | `references/data-schema.md` |
| Deciding whether two postings are the same job | `references/filters.md` |
| Handing a found job to `job-apply` | `references/handoff.md` |
| Sweeping several sources in parallel | `references/orchestration.md` |
| Meeting a job board the workspace does not know | `references/discovery.md` |

## Step 0: resolve the workspace (always do this first)

The workspace holds the user's profile, CV sources, application log, and now the
search pipeline. It belongs to the user, not to this skill, and it is the *same*
workspace `job-apply` uses. Sharing it is the point: the application log is what
stops this skill offering a job the user already applied to, and the profile is
what stops it asking for facts already on record.

Resolution order, identical to `job-apply` because the marker is the same file:

1. `$JOB_APPLY_HOME`, if set.
2. Walk **up** from the current directory looking for `.job-apply/config.yaml`.
   The directory containing `.job-apply/` is the workspace.
3. Look **down** one or two levels for a subdirectory holding
   `.job-apply/config.yaml`, because the workspace is usually a `job-apply/`
   folder inside a project and the user is sitting in the project root.
4. If none is found, the workspace does not exist yet.

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

**When there is no workspace, do not create one.** Say so and run `job-apply`'s
Setup instead. A search needs `profile/targets.md` to know what to look for and
`applications/log.csv` to know what to skip, and a pipeline row is only useful if
`job-apply` can act on it. Building half a workspace here would produce a search
that cannot hand anything off.

Finding more than one workspace means the user has two. Ask which, rather than
picking: sweeping against the wrong log surfaces jobs they have already applied
to.

`references/data-schema.md` is the canonical spec for `profile/search.md`,
`profile/boards.md`, and `search/pipeline.csv`. Prefer it over inferring structure from whatever files
happen to exist. For every other workspace file, `job-apply`'s own
`references/data-schema.md` is authoritative and this skill only reads them.

## Ground rules

**This skill writes exactly three paths.** `profile/search.md`,
`profile/boards.md`, and everything under `search/`. It never writes
`applications/`, `cv/`, `qa/`, or the rest of `profile/`. The workspace is shared, so a stray write here would corrupt data
`job-apply` depends on, and the user would find out at the worst moment, mid
application.

**Never apply to anything.** No forms, no submits, no CV rendering. If the user
asks to apply while a sweep is running, finish or abandon the sweep cleanly and
hand the URL to `job-apply`. Two skills driving one browser session is how a
half-filled form gets submitted.

**Volume is the goal, so filter only on true blockers.** The user wants to apply
widely. A role is dropped only when it is one they cannot take or have ruled out
permanently: US work authorization, junior or mid-level IC, an excluded location,
a company on cooldown. Anything with title similarity is kept, even when it looks
like a stretch. There is no fit score, and adding one would be inventing a
judgement the user asked not to have.

**Dropped is not deleted.** A dropped row stays in the pipeline with its reason.
Deleting it means the next sweep rediscovers and re-evaluates it, and "requires
US work authorization" is a permanent fact about a posting, not a transient one.

**The user's browser is not yours.** Never clear cookies, cache, or storage at
the profile level. Those operations reach every site the user is signed into and
cannot be undone, and a sweep has even less reason to reach for them than an
application does: a board that will not load is a board to report, not a profile
to reset. A problem with one site is solved at that site's scope or not at all.

**A blocked source is not an empty source.** When LinkedIn challenges the
session or a board will not load, say so and name the URL. Reporting "0 results"
for a source that was never swept tells the user a board is dry when it is
merely blocked, and they stop checking it themselves.

**Pace the sweep.** These are the user's real logged-in accounts. Getting
LinkedIn to throttle their session costs them hours of their own browsing, not
just this run. `references/search.md` has the budgets; they are not suggestions.

**Secrets stay out of files.** A sweep reads pages behind the user's own logged
in sessions. Nothing from those sessions belongs in the workspace: no cookies,
no tokens, no account details picked up along the way. The pipeline records what
a job is and where to apply, nothing about who is looking at it.

## Prerequisites

Check these before a workflow needs them, and offer to fix them rather than
failing mid-sweep.

| Tool | Check | Needed for |
|---|---|---|
| ego lite | `export PATH="$HOME/.local/bin:$PATH"; command -v ego-browser` | Every sweep |
| `ego-browser` skill | listed in available skills | Every sweep |
| uv | `uv --version` | Running `scripts/pipeline.py` |
| `job-apply` skill | listed in available skills | Setup, and applying to anything found |

Install uv with `brew install uv`. `scripts/pipeline.py` is a `uv run` script
with an inline dependency header, so it needs nothing else. Run it rather than
editing the CSV by hand: it owns the identity key, and a key computed a second
way silently breaks dedup.

`job-apply` is not needed to sweep, but it owns the workspace this skill reads
and it is where a found job goes next. A pipeline with nothing at the other end
is not much use, so mention it if it is missing.

### Setting up ego lite

This skill drives the browser with ego lite. That is a hard requirement rather
than a preference: job boards gate their listings behind a logged-in session,
and ego lite is the browser tested here that carries the user's real sessions.
It is macOS-only today, and it needs a one-time setup the user performs in a GUI.

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
   import from Chrome, which is how the user's logged-in board sessions carry
   across. That import is what makes a sweep worth running: without it, LinkedIn
   and Y Combinator show a login wall instead of results.
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
   board may not be signed in. A sweep that reports zero results because it was
   quietly logged out is worse than one that stops and says so, so check before
   relying on a gated source and ask the user to log in if it is missing.

Not on macOS: point the user at https://lite.ego.app/ and say the install script
is macOS-only.

## Workspace shape

This skill adds two things to the `job-apply` workspace. Everything else it
reads and never writes.

```
<workspace>/
├── .job-apply/config.yaml      # shared marker; may carry a search: block
├── profile/
│   ├── targets.md              # READ: titles, seniority, the Avoid list
│   ├── logistics.md            # READ: work authorization, location, salary
│   ├── search.md               # WRITTEN: where and how to look
│   └── boards.md               # WRITTEN: the source directory, grows each sweep
├── applications/log.csv        # READ: the dedup source of truth
└── search/                     # WRITTEN
    ├── pipeline.csv            # every job found, with its status
    └── runs/<run-id>.md        # what one sweep did, including what it could not do
```

`targets.md` says *what* roles to look for. `search.md` says *where* and *how*.
When they disagree, `targets.md` wins, because `job-apply` uses it to pick a CV
track and two sources of truth about target roles would drift apart silently.

## A sweep: the shape of it

Detail is in `references/search.md`. The order matters.

1. **Load** `profile/`, `search.md`, and `applications/log.csv`, then
   **reconcile** the pipeline against the log so anything applied to since the
   last sweep is already marked.
2. **Plan** the queries: terms per track, sources in yield order. Read the
   `ego-browser` skill before the first browser call.
3. **Sweep** each source in one task space, buffering results and checkpointing
   after each source.
4. **Upsert** the whole run through `scripts/pipeline.py`, which dedups on all
   three axes at once.
5. **Report** into `search/runs/`, naming what was found, what was dropped, and
   what was blocked.
6. **Finish** the task space once the sweep is genuinely done.

Results are buffered until step 5 rather than written as they are found, because
the same job cross-posted to LinkedIn and Ashby can only be collapsed once both
sources have been swept.

## What this skill does not do

A specific job posting URL, a CV, a cover letter, or a form is `job-apply`'s
work. If the user pastes a single posting URL, that is a strong signal they want
to apply, not to search. `references/handoff.md` covers how a pipeline row
becomes an application and how the status finds its way back.
