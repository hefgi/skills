# Source recipes

URL patterns, extraction, and failure modes per source. Read the one you are
about to sweep rather than the whole file.

Sweep order comes from `sources:` in `search.md`, which Setup orders by how
often the user actually applied through each. The order below matches the
typical result, and the reasoning generalizes: boards with a public JSON API
first, because they are fast, reliable, and unguarded; search engines last,
because they are slow and challenge readily.

## Contents

- [Shared rules](#shared-rules)
- [Ashby](#ashby)
- [Greenhouse](#greenhouse)
- [LinkedIn](#linkedin)
- [AI and startup boards](#ai-and-startup-boards)
- [Career pages and Google](#career-pages-and-google)
- [Growing known_company_boards](#growing-known_company_boards)

## Shared rules

The `ego-browser` skill is the browser manual: task spaces, snapshots, refs,
waiting, and the escalation ladder for a stuck page. Read it before the first
browser call. Opening the space and finishing it are in `references/search.md`
Phase C and Phase F. What follows is only what is specific to job boards.

**Extract in bulk with `page.evaluate()`, not by clicking through results.** A
board page holds twenty to fifty postings, and the sweep wants a list, not an
interaction. One `evaluate` returning an array of objects is a single round;
walking the same list through refs is fifty. The per-source recipes below are
written that way for this reason.

**Scope the extraction to the results container.** Reading whole-page text pulls
in navigation, cookie notices, "people also viewed" panels, and footers, and the
postings arrive fragmented in the middle of it.

**A board that renders client-side returns nothing if read too early.** Wait for
the list to exist with `waitForSelector()` rather than a fixed delay, then
extract. Treat a board as genuinely empty only after that wait has succeeded and
still found no rows.

**Paginate by navigation where the board allows it.** A URL carrying the page
offset is cheaper and more reliable than clicking a Next control and hoping the
list re-rendered.

## Ashby

The highest-yield source for most users, and the one to get right.

**Ashby has no global job search.** There is no cross-company query. Every sweep
is per-company, against a board you already know about. That single constraint
shapes the whole recipe: Ashby pays off through `known_company_boards` growing
over time, not through search.

### Board sweep, per slug

Try the posting API first. It is undocumented but widely available, and it
returns clean JSON with no DOM parsing. `page.fetch()` runs it in the page, so
several slugs can be collected in one round:

```bash
ego-browser nodejs -e '
const task = await taskSpace(7);
const page = task.page("p1");
const slugs = ["cohere", "langchain", "elevenlabs"];
const out = [];
for (const slug of slugs) {
  const res = await page.fetch(
    `https://api.ashbyhq.com/posting-api/job-board/${slug}`,
    { timeout: 15000 },
  );
  if (!res.ok) { out.push({ slug, error: res.status }); continue; }
  const jobs = JSON.parse(res.body).jobs ?? [];
  out.push({ slug, jobs: jobs.map((j) => ({
    role: j.title, location: j.location,
    work_mode: j.isRemote ? "remote" : "unknown", url: j.jobUrl,
  })) });
}
console.log(JSON.stringify(out, null, 2));
'
```

Each entry carries `title`, `location`, `employmentType`, `isRemote`, and
`jobUrl`. Map `isRemote` to `work_mode`.

When a slug 404s, fall back to the board page. It renders client-side, so wait
for the list before extracting. Posting links match `/<slug>/<uuid>`:

```js
await page.goto("https://jobs.ashbyhq.com/<slug>");
await page.waitForSelector('loc=css:a[href*="/"]', { state: "visible" });
const jobs = await page.evaluate(() =>
  [...document.querySelectorAll("a[href]")]
    .filter((a) => /^\/[^/]+\/[0-9a-f-]{36}/.test(a.getAttribute("href") || ""))
    .map((a) => ({ role: a.innerText.trim(), url: a.href })),
);
```

### Failure modes

- **404 on a slug.** The slug drifted, not the company vanishing. One real log
  had `bjakcareer` rather than `bjak`. Report it, keep the entry, do not delete.
- **Empty board.** Either no open roles or pre-hydration extraction. Retry once
  before believing it.
- **Company name prefixed by the ATS.** Boards sometimes render the employer as
  `Ash by <Company>`. `normalize_company` strips it; do not record it verbatim.

## Greenhouse

The most reliable source in this skill, because the API is documented and stable.

```js
const res = await page.fetch(
  `https://boards-api.greenhouse.io/v1/boards/${slug}/jobs?content=true`,
  { timeout: 15000 },
);
const jobs = JSON.parse(res.body).jobs.map((j) => ({
  role: j.title,
  location: j.location?.name ?? "",
  url: j.absolute_url,
  platform: "greenhouse",
}));
```

Returns `title`, `location.name`, `absolute_url`, and `updated_at` for every open
role. That is everything a harvest row needs, with no DOM parsing and no
anti-bot. Use it in preference to the HTML board every time.

Neither API needs a logged-in session, so a plain Node `fetch()` outside the
browser works too. Prefer `page.fetch()` anyway while a space is already open: it
keeps one transport for the whole sweep, and some tenants serve different content
to a browser origin.

Three host variants all appear in real application logs, and a sweep must handle
each:

| Host | Note |
|---|---|
| `job-boards.greenhouse.io/<slug>` | Current |
| `job-boards.eu.greenhouse.io/<slug>` | EU-hosted tenants |
| `boards.greenhouse.io/<slug>` | Legacy, redirects |
| `app.greenhouse.io/embed/job_app?token=<n>` | A single embedded posting, not a board. Cannot be swept; only reachable from a company career page. |

### Failure modes

- **Guessed slugs 404.** Never guess. Use slugs mined from the log or harvested
  from a link. One real log has `scaleai`, not `scale`.
- **Departments paginate** on some HTML boards. The API does not, which is
  another reason to prefer it.

## LinkedIn

The broadest source and the most fragile. Pace it (see `search.md`).

```
https://www.linkedin.com/jobs/search/?keywords=<term>&location=<loc>&f_TPR=r604800&sortBy=DD&start=<n>
```

| Parameter | Meaning |
|---|---|
| `f_TPR=r604800` | Posted in the last 7 days, in seconds. `r86400` for a daily sweep. Bound this, or every weekly sweep re-reads the same postings. |
| `sortBy=DD` | Date descending, which makes the recency cut predictable |
| `f_WT=1,2,3` | Onsite, remote, hybrid. Omit for all. |
| `f_E=4,5,6` | Mid-senior, director, executive. Worth setting for a leadership track: LinkedIn's own seniority filter is more reliable than parsing titles afterwards. |
| `start=0,25,50` | Pagination, 25 per page |

Extract from the card container, not the body. One `evaluate` per results page
returns the whole list:

```js
await page.goto(url);
await page.waitForSelector("loc=css:[data-job-id]", { state: "visible" });
const cards = await page.evaluate(() =>
  [...document.querySelectorAll(
    "div.job-card-container, li.jobs-search-results__list-item, [data-job-id]",
  )].map((c) => ({
    id: c.getAttribute("data-job-id"),
    text: c.innerText,
  })).filter((c) => c.id),
);
```

The card text carries the company and location on separate lines; parse them out
in Node rather than in the page, so a layout change shows up as a parse you can
see rather than an empty array.

**Build the URL from `data-job-id`**, as
`https://www.linkedin.com/jobs/view/<id>/`, rather than reading the anchor. The
rendered href carries tracking parameters that differ on every load, so a
scraped href defeats URL-based dedup.

### Failure modes

- **The list does not populate.** The results pane lazy-mounts. Move the pointer
  over the pane and `page.mouse.wheel(0, 800)`, wait for the count to grow, then
  re-extract. If two scrolls add nothing, the list is done regardless of the
  count LinkedIn claims.
- **Login wall or "Join now".** The session expired. Stop LinkedIn for this run
  and tell the user to log in in their own browser. Do not retry.
- **`/checkpoint/challenge` or a CAPTCHA.** Hard stop on LinkedIn. Record the URL
  and move on. Never attempt to solve it.
- **Results empty after previously working.** Throttling. Back off and retire
  the source.
- **Promoted and repeated cards.** LinkedIn shows the same requisition across
  pages. In-run dedup absorbs this; do not try to detect it in the DOM.
- **Easy Apply cards with no external URL.** Keep them with
  `platform: linkedin`. They are applicable, just through LinkedIn's own form.

## AI and startup boards

Both are best effort. Say so in the report when they fail, rather than recording
zero results.

### Y Combinator Work at a Startup

```
https://www.workatastartup.com/jobs?role=eng&remote=yes&query=<term>
```

Full listings need a logged-in YC account. Check for the login wall first and
skip the source with a clear message rather than harvesting a truncated
anonymous list, which looks like a complete result and is not.

Companies are `/companies/<slug>`, jobs `/jobs/<id>`. Infinite scroll, so bound
it by scroll count rather than page count.

### Wellfound

```
https://wellfound.com/jobs?keywords=<term>&locationSlugs=<city>
https://wellfound.com/role/r/<role-slug>
```

Aggressive Cloudflare. One query per track, and abandon the source on the first
challenge page. Wellfound failing is expected rather than a bug to retry around.

## Career pages and Google

The intent here is finding companies that the board sweeps do not already cover.
Career pages carry the load; Google is a last resort for discovering new slugs.

### Career pages, deterministic

For each company in `known_company_boards`, and each company mined from the log:

1. Try the Ashby or Greenhouse API for its slug.
2. Otherwise `https://<domain>/careers`, `/jobs`, `/careers/jobs`.
3. Detect the embedded ATS from the page. An `ashbyhq.com` iframe or a
   `greenhouse.io` script tag means switching to that recipe, which is both more
   reliable and already written.

Some companies run bespoke career pages that need direct extraction. Real
examples include `helsing.ai/jobs/<id>` and `faculty.ai/en-gb/job-listing/...`.
Extract the posting list from the page and record `platform: direct`.

### Google, capped at 3 queries

```
https://www.google.com/search?q=site:jobs.ashbyhq.com+"forward+deployed+engineer"+London
```

Restrict with `site:` to `jobs.ashbyhq.com`, `job-boards.greenhouse.io`, or
`jobs.lever.co`. An unrestricted title query returns aggregator spam that costs
requests and yields nothing.

**The purpose is discovering board slugs, not harvesting postings.** Pull the
company slug out of each result path, add it to `known_company_boards`, and let
the Ashby or Greenhouse recipe do the actual extraction. That reframing is why
three queries is enough.

**Check for a block before the first real query.** `goto` a search URL and look
for `consent.google.com` or `/sorry/index`. If either appears, skip Google for
this run and report it. Do not click through consent, and do not attempt a
CAPTCHA.

Google is the weakest link in a browser-only sweep, which is why it is last,
capped, and scoped to slug discovery. If it becomes reliably blocked, the right
fix is enabling a search API for slug discovery alone, not fighting the browser.

## Growing known_company_boards

The compounding loop that makes Ashby and Greenhouse productive despite having
no cross-company search.

Every sweep, whenever a posting URL matches a known ATS pattern, extract the
slug and add it to `known_company_boards` in `search.md` if it is new:

| Pattern | Slug |
|---|---|
| `jobs.ashbyhq.com/<slug>/<uuid>` | `ashby:<slug>` |
| `job-boards(.eu).greenhouse.io/<slug>/...` | `greenhouse:<slug>` |
| `jobs.lever.co/<slug>/...` | `lever:<slug>` |

LinkedIn is the main feeder here: its postings link out to company ATS boards, so
a LinkedIn sweep discovers Ashby slugs that the next Ashby sweep harvests
directly and far more cheaply.

Tell the user when slugs were added and how many. It explains why later sweeps
find more while doing less, and it is the clearest signal the skill is improving
with use.
