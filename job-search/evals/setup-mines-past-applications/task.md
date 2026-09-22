# Set up the search from an existing application history

## Problem/Feature Description

The user already has a `job-apply` workspace with a populated application log.
They want to start searching for roles rather than stumbling across them, and
they have explicitly asked not to be interviewed at length.

Almost everything the search needs is already derivable from what is on disk.
The log records which ATS platforms they actually apply through, the title
vocabulary they use, and, in its notes, the companies that cap applications.
`profile/targets.md` records target roles and `profile/logistics.md` records
geography and work authorization.

A good run mines those and asks about the few things it genuinely cannot infer.
A bad run treats this as a fresh interview, or writes inferred values silently
without showing its working.

The fixture workspace is at `fixtures/seed-workspace/`. Copy it somewhere
writable and run against the copy. It has a valid `.job-apply/config.yaml`,
`profile/targets.md`, `profile/logistics.md`, and a populated
`applications/log.csv`. There is no `profile/search.md` and no `search/`
directory yet.

## The user's message

> I want to start actually searching for jobs instead of just applying to
> whatever I stumble across on LinkedIn. Can you set that up? Please don't make
> me sit through twenty questions, you've got a whole log of stuff I've already
> applied to in there.

## Output Specification

A `profile/search.md` and an empty `search/pipeline.csv` with the documented
header, with the search criteria mined from what already exists rather than
re-asked, and any inference shown to the user for confirmation.
