# Resume an interrupted job-apply setup

## Problem/Feature Description

A user started setting up a `job-apply` workspace a few days ago and the session
was cut short partway through. The workspace directory exists and some files in
it are already correct, but most of the profile was never written and the CV
sources were never built.

They come back and ask to finish it, supplying the facts that were missing.

The fixture workspace is at `fixtures/partial-workspace/`. Copy it somewhere
writable and run against the copy. It contains a valid `.job-apply/config.yaml`,
a partially filled `profile/identity.md`, and a `applications/log.csv` holding
only its header row. Everything else is absent.

## The user's message

> I started setting up job-apply here a few days ago but I think it got cut off
> partway. Can you pick it up and finish it? My address is 12 Example Street,
> London N1 1AA, I'm a UK citizen so no sponsorship, one month notice, and I'm
> after about 110k. Targeting forward deployed engineer type roles mainly.

Their CV facts, for the parts of the workspace that need them:

> Seven employers over twelve years. Most recently Lovelace Consulting
> (2025-09 to present, independent), before that Northwind Data (2026-02 to
> 2026-08, via Lovelace Consulting), Halcyon Systems, Bramble Health, Meridian
> Logistics, Acme Corp, and Example Corp.

## Output Specification

A completed workspace that a subsequent apply run could use, with the gaps
filled and nothing that already existed destroyed.
