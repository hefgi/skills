# Boards

Job sources this workspace knows about. Setup seeds it; every sweep adds to it.
Edit it freely, it is yours.

Two kinds, and the difference decides how a sweep uses each:

- `kind: search` takes a query and returns jobs across many companies. These
  need no slug, and they are how the directory grows.
- `kind: board` returns one company's open roles and needs a slug. These are how
  the directory pays off, because a board already discovered is cheap to revisit.

`tier: 1` is a public endpoint with no session, safe to sweep in parallel.
`tier: 2` needs the user's logged-in browser, so one agent per domain.

`verified` records that the recipe actually returned a row, and when. A recipe
that has never returned anything is a guess: leave it unverified rather than
letting a silent zero look like a quiet board.

## Board: workable-search
kind: search
tier: 1
api: https://jobs.workable.com/api/v1/jobs?query={term}&location={city}
fields: title->role, company.title->company, url->url,
  location.city->location, workplace->work_mode
verified: 2026-09-22, 9 forward-deployed roles in London
notes: the only free cross-company job search found. Needs no slug, so it is
  the main feeder for this directory: every result names a company, and its
  external links carry ATS slugs worth adding. workplace is on_site, hybrid or
  remote. Cursor pagination via nextPageToken.

## Board: linkedin
kind: search
tier: 2
board_url: https://www.linkedin.com/jobs/search/
verified: 2026-09-21, fixture and live
notes: recipe in references/sources.md. Needs the logged-in session, challenges
  readily, one agent only. Its postings link out to company ATS boards, which
  makes it the other main feeder for this directory.

## Board: hn-whoishiring
kind: search
tier: 1
api: https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=100
index: https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=hiring
verified: 2026-09-22, thread 49522897 returned 400 comments
notes: one call for roughly 400 postings a month, strong for AI and infra
  startups. Each comment is freeform text in a loose convention of
  "Company | Role | Location | Remote | url", so it needs parsing and the first
  few comments are usually meta rather than jobs. Best effort: a parse failure
  never blocks the sweep.

## Board: ashby
kind: board
tier: 1
api: https://api.ashbyhq.com/posting-api/job-board/{slug}
board_url: https://jobs.ashbyhq.com/{slug}
fields: title->role, location->location, isRemote->work_mode, jobUrl->url
posting_pattern: jobs\.ashbyhq\.com/([^/?#]+)
verified: 2026-09-21
notes: no cross-company search exists, so this board is only as good as the
  slug list. Company name is not in the payload; resolve from the slug.
companies: babbage, lovelace, turinglabs

## Board: greenhouse
kind: board
tier: 1
api: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
board_url: https://job-boards.greenhouse.io/{slug}
fields: title->role, location.name->location, absolute_url->url
posting_pattern: (?:job-boards(?:\.eu)?|boards)\.greenhouse\.io/([^/?#]+)
verified: 2026-09-21, 42 live roles for physicsx
notes: documented and stable. No company name in the payload, and no work_mode
  field at all, so work_mode is unknown unless the location string says remote.
companies: hopper, noether

## Board: lever
kind: board
tier: 1
api: https://api.lever.co/v0/postings/{slug}?mode=json
board_url: https://jobs.lever.co/{slug}
fields: text->role, categories.location->location,
  workplaceType->work_mode, country->country, hostedUrl->url
posting_pattern: jobs\.lever\.co/([^/?#]+)
verified: 2026-09-22, 312 roles for palantir and 73 for spotify
notes: workplaceType is remote, hybrid or onsite, so work_mode comes straight
  from the payload. country is an ISO code, a better filter than matching
  location strings. Server-side filters work but location must be the exact
  full string: "London, United Kingdom" returns 41, "London" returns 0. The
  payload contains raw control characters, so parse with strict=False or fetch
  it through the browser, whose JSON.parse tolerates them. A bad slug 404s; a
  real but empty board returns [] with 200, so the two are distinguishable.
companies: curie

## Board: smartrecruiters
kind: board
tier: 1
api: https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100
board_url: https://jobs.smartrecruiters.com/{slug}
fields: name->role, company.name->company, location.city->location,
  location.remote->work_mode, location.country->country
posting_pattern: (?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)
verified: 2026-09-22, 271 roles for ifs1
notes: the only per-company board here that returns the company name, so no
  slug-to-name resolution is needed. location.remote and location.hybrid are
  booleans. Identifiers are case-insensitive. A wrong identifier does NOT 404:
  it returns 200 with totalFound 0, identical to a company with no open roles,
  so an empty result is not evidence the slug is wrong.
companies: 

## Board: workable
kind: board
tier: 1
api: https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true
board_url: https://apply.workable.com/{slug}
fields: title->role, city->location, country->country,
  application_url->url, employment_type->employment_type
posting_pattern: apply\.workable\.com/([^/?#]+)
verified: 2026-09-22, 93 roles for fuseenergy
notes: prefer workable-search when looking broadly; use this to revisit a
  company already known.
companies: 

## Board: teamtailor
kind: board
tier: 1
api: https://{slug}.teamtailor.com/jobs.json
fallback: https://{slug}.teamtailor.com/jobs.rss
fields: title->role, url->url, remoteStatus->work_mode,
  tt:location.city->location
posting_pattern: ([a-z0-9-]+)\.teamtailor\.com
verified: 2026-09-22, 23 items for spiko
notes: both endpoints return 200. The RSS carries a tt: namespace with city,
  country and remoteStatus, which the JSON feed does not, so prefer RSS when
  location matters. Company name is not in either; resolve from the slug. The
  description field is a full HTML ad, so strip it before anything reaches the
  CSV. Heavily Nordic and EU.
companies: 

## Board: recruitee
kind: board
tier: 1
api: https://{slug}.recruitee.com/api/offers/
fields: title->role, location->location, careers_url->url
posting_pattern: ([a-z0-9-]+)\.recruitee\.com
verified: 2026-09-22
notes: the trailing slash is required. A wrong slug 404s and a real but empty
  board returns 200 with an empty offers array, so the two are distinguishable.
  Now branded Tellent. Harvest only: do not guess slugs into it.
companies: 

## Board: personio
kind: board
tier: 1
api: https://{slug}.jobs.personio.de/xml?language=en
fields: name->role, office->location, id->url
posting_pattern: ([a-z0-9-]+)\.jobs\.personio\.(?:de|com)
verified: 2026-09-22
notes: XML rather than JSON. Build the URL as
  https://{slug}.jobs.personio.de/job/{id}. Some tenants are .com rather than
  .de, so try both. No work_mode field. Strong DACH coverage.
companies: 

## Board: rippling
kind: board
tier: 1
api: https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs
fields: name->role, workLocation.label->location, url->url
posting_pattern: ats\.rippling\.com/([^/?#]+)
verified: 2026-09-22
notes: small but trivially clean. No work_mode field; infer from the location.
companies: 

## Board: workday
kind: board
tier: 2
api: POST https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
fields: title->role, locationsText->location, externalPath->url
posting_pattern: ([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)
verified: 2026-09-22, 350 results for "forward deployed" on nvidia
notes: tier 2 not because it needs a session, but because it is a POST needing
  an exact tenant, pod and site triple. A wrong combination returns 422 with an
  empty body, so all three must be harvested from a real posting URL and never
  guessed. Body is {"appliedFacets":{},"limit":20,"offset":0,"searchText":"..."}
  and searchText is the right way to bound it. locationsText is often a count
  such as "2 Locations" rather than a place, so treat a location that looks like
  a count as unknown. Build the URL from externalPath.
companies: 
