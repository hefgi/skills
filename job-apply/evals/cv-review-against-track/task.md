# Review a CV honestly against a target track

## Problem/Feature Description

A user has a complete `job-apply` workspace and wants their CV critiqued for a
forward deployed engineer role. They have explicitly asked not to be handled
gently.

The CV has real problems planted in it. A good review finds them and says so
plainly, with concrete replacement wording rather than general advice. A bad
review opens with praise, lists generic tips, or quietly edits the source file
instead of offering.

The fixture workspace is at `fixtures/workspace/`. Copy it somewhere writable
and run against the copy. The CV facts are in `cv/cv-base.yaml` and the target
tracks are in `profile/targets.md`.

## The user's message

> Can you take a look at my CV and tell me honestly how it lands for a forward
> deployed engineer role? Don't be nice about it, I'd rather know now than after
> twenty rejections.

## Output Specification

A prioritised critique naming specific bullets and roles by their location in
the CV, with concrete replacement wording for the most important fixes. The
review offers to apply changes; it does not apply them unasked.
