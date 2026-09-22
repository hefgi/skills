# Discover a job board the workspace has never seen

## Problem/Feature Description

A sweep that only knows the boards it shipped with gets no better with use. The
directory in `profile/boards.md` is the one asset a sweep builds that makes the
next sweep cheaper, because the per-company ATSs have no cross-company search:
the only way to sweep them is to know which boards exist.

So a posting URL is two things at once. It is a job, and it is evidence about
where jobs live. This scenario tests the second.

Three cases have to come out differently, and conflating any two of them is the
failure:

- A URL on a **board type already known** yields a company slug to save.
- A URL on an **unfamiliar ATS host** is probed for a public endpoint, and if
  one answers with real rows, saved as a reusable board type.
- A URL that is **an ordinary company careers page**, or a system with no public
  listing endpoint at all, is not a board type and must not be saved as one.

The rule that matters most: a recipe that has not actually returned a row is not
saved as working. An unverified recipe reports an empty board on every later
sweep, and nothing distinguishes that from a company with nothing open.

## Setup

Serve the board fixtures on port 8899 from the `fixtures/` directory:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy `fixtures/workspace/` somewhere writable and run against the copy. Its
`profile/boards.md` holds the seeded sources.

## The user's message

> Do a sweep. And keep track of any job boards you come across, I don't want to
> be stuck with just LinkedIn forever.

## Output Specification

An updated `search/pipeline.csv` as usual, plus a `profile/boards.md` that has
grown: new company slugs under board types already known, and any genuinely new
board type recorded with its endpoint, its field mapping, and an honest
`verified` state. Whatever was guessed rather than observed is flagged.
