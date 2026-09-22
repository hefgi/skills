# Source recipes

URL patterns, extraction, and failure modes per source. Read the one you are
about to sweep rather than the whole file.

These are the recipes the skill ships with. They are not the whole list: a
workspace also has `profile/boards.md`, the directory its own sweeps have built,
and `references/discovery.md` covers adding to it. A board in that file with a
`fields` mapping needs no recipe here.

Sweep order comes from `boards.md`, ordered by how often the user actually
applied through each. The reasoning generalizes: sources with a public JSON API
first, because they are fast, reliable, and unguarded; search engines last,
because they are slow and challenge readily.

## Contents

- [Shared rules](#shared-rules)
- [Deciding whether a location is reachable](#deciding-whether-a-location-is-reachable)
- [Ashby](#ashby)
- [Greenhouse](#greenhouse)
- [LinkedIn](#linkedin)
- [AI and startup boards](#ai-and-startup-boards)
- [Career pages and Google](#career-pages-and-google)
- [Growing the directory](#growing-the-directory)

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

## Deciding whether a location is reachable

Every source needs this and every sweep will otherwise reinvent it, so it lives
here once. The obvious naive implementation is the broken one.

A location is reachable when it names a place inside `geography`, **or** it is
*unqualified* remote. `Remote`, `Remote - Global`, `Remote - EMEA`, `Anywhere`
and `Remote - United Kingdom` are reachable. `Remote - Texas`,
`Remote - California`, `Remote U.S.` and `Remote - India` are not: they are
onsite-in-a-country roles that happen not to require an office.

**Test qualified remote before testing for the bare word `remote`**, because
every qualified-remote string contains it. Large US employers write their entire
board this way, so a sweep that gets this wrong fills the pipeline with one
company's US postings. In a real run it was 26 rows from a single employer.

```js
// Qualified first: every qualified string contains the bare word.
const QUALIFIED_REMOTE = /remote[\s\-–—,]*(?:in\s+)?(?!global|anywhere|worldwide|international|emea|europe|eu\b|uk\b|int\b|united\s+kingdom)[a-z]/i;
const UNQUALIFIED_REMOTE = /^\s*(remote|anywhere|global|remote\s*[-–—,]\s*(global|anywhere|worldwide|international|emea|europe|int))\s*$/i;
const REACHABLE = /\b(london|united kingdom|england|scotland|wales|france|paris|ireland|dublin|germany|berlin|munich|netherlands|amsterdam|spain|madrid|portugal|lisbon|poland|warsaw|sweden|stockholm|denmark|copenhagen|italy|milan|belgium|brussels|austria|vienna|finland|helsinki|switzerland|zurich|europe|emea)\b/i;

function reachable(location) {
  const loc = (location || "").trim();
  if (!loc) return true;                      // absent is unknown, not excluded
  // A posting listing several locations is reachable if ANY of them is.
  return loc.split(/[;|]|\s+or\s+/).map(s => s.trim()).some(p =>
    UNQUALIFIED_REMOTE.test(p) || (REACHABLE.test(p) && !QUALIFIED_REMOTE.test(p)));
}
```

**Match on word boundaries, not substrings.** `uk` as a substring matches inside
unrelated words. It is the same class of bug as the bare `remote` token.

**Multi-location postings matter.** `Doha, Qatar; London, UK` and
`London - Hybrid; New York - Hybrid; San Francisco - Hybrid` are both reachable,
because one listed location is London. Split and keep the row if any part is
reachable; testing the whole string as one blob drops both.

**An empty location is not a drop.** A results page often omits it. Keep the row
and let `upsert` decide: a false keep costs one glance, a false drop costs a job.

Harvest the location verbatim anyway. `upsert` applies the real blocker, and one
place deciding what gets dropped is what makes the run report's counts true.

## Ashby

The highest-yield source for most users, and the one to get right.

**Ashby has no global job search.** There is no cross-company query. Every sweep
is per-company, against a board you already know about. That single constraint
shapes the whole recipe: Ashby pays off through the directory in
`profile/boards.md` growing over time, not through search.

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
await page.goto(`https://jobs.ashbyhq.com/${slug}`);
// Wait on the list container, not on the postings. `waitForSelector` resolves a
// single element, so a selector matching every posting link raises
// ElementResolutionError rather than waiting. Count matches instead when there
// is no container to key on.
await page.waitForFunction(
  () => document.querySelectorAll('a[href*="/"]').length > 1,
  undefined,
  { timeout: 15000 },
);
const jobs = await page.evaluate(() =>
  [...document.querySelectorAll("a[href]")]
    .filter((a) => /^\/[^/]+\/[0-9a-f-]{36}/.test(a.getAttribute("href") || ""))
    .map((a) => ({
      // Read the parts separately. `a.innerText` concatenates the role with the
      // location and work mode, and that composite would go straight into
      // job_key and corrupt dedup for that posting forever.
      role: a.querySelector("h3")?.innerText.trim() ?? a.innerText.split("\n")[0].trim(),
      location: a.querySelectorAll("span")[0]?.innerText.trim() ?? "",
      work_mode: (a.querySelectorAll("span")[1]?.innerText.trim() ?? "").toLowerCase(),
      url: a.href,
      // Take the slug from the posting's own href, not from the board queried.
      slug: (a.getAttribute("href").match(/^\/([^/]+)\//) || [])[1] ?? "",
    })),
);
```

**The company name is not on the board page.** Ashby renders the role, the
location, and the work mode, and leaves the employer implicit. `upsert` refuses a
row without a company, so derive it from the slug.

**Take the slug from each posting's href, not from the board you queried.** A
board usually carries one company, but not always: a page can link postings under
other slugs, and stamping the queried slug on all of them files several companies
under one name and breaks dedup against the log. The slug, not the board, is the
unit of company identity.

Resolve the slug to a display name in this order, because `job_key` is derived
from it and an inconsistent name splits one company into two:

1. The name already used for that slug in `applications/log.csv` or
   `pipeline.csv`. Existing rows are the authority.
2. The board's own title or heading, when it names the employer.
3. Title-cased slug as a last resort, and say in the report that you guessed.

**Greenhouse has the same gap**, and the same ladder applies. Its API returns
`title`, `location`, and `absolute_url` but no company name, so resolve the board
slug the same way.

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
await page.waitForFunction(
  () => document.querySelectorAll("[data-job-id]").length > 0,
  undefined,
  { timeout: 15000 },
);
const cards = await page.evaluate(() =>
  [...document.querySelectorAll("[data-job-id]")].map((el) => {
    // The metadata lines carrying location and any work-authorization notice
    // are FOLLOWING SIBLINGS of the card's list item, not descendants of it.
    // Walk forward to the next card, collecting what lies between.
    const parts = [el.innerText];
    let node = (el.closest("li") || el).nextElementSibling;
    while (node && !node.matches?.("[data-job-id]")
                && !node.querySelector?.("[data-job-id]")) {
      parts.push(node.innerText);
      node = node.nextElementSibling;
    }
    return { id: el.getAttribute("data-job-id"), text: parts.join("\n") };
  }).filter((c) => c.id),
);
```

**Walk forward to the siblings; do not climb.** The `[data-job-id]` element holds
the role and the company. The location and any "must be authorized to work in the
United States" line sit *after* the card's list item, as siblings. Climbing with
`closest("li")` reaches an ancestor, and an ancestor cannot contain a sibling, so
that read returns rows that look complete while missing exactly the text the
`us-work-auth` blocker tests. A US-only posting then enters the pipeline as an
ordinary row, and the `location` blocker misses it too because the location was
lost in the same breath.

That failure is silent, which is what makes it dangerous, so it has a visible
signature worth checking every run: **a card with no location means the
extraction missed it, not that the posting has no location.** A batch where
every row lacks a location is a broken selector, not data. Stop and fix the
selector rather than upserting the batch.

Parse the company and location out of the text in Node rather than in the page,
so a layout change surfaces as a parse you can inspect rather than an empty
array.

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

For each company in `profile/boards.md`, and each company mined from the log:

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
company slug out of each result path, add it to `profile/boards.md`, and let
the Ashby or Greenhouse recipe do the actual extraction. That reframing is why
three queries is enough.

**Check for a block before the first real query.** `goto` a search URL and look
for `consent.google.com` or `/sorry/index`. If either appears, skip Google for
this run and report it. Do not click through consent, and do not attempt a
CAPTCHA.

Google is the weakest link in a browser-only sweep, which is why it is last,
capped, and scoped to slug discovery. If it becomes reliably blocked, the right
fix is enabling a search API for slug discovery alone, not fighting the browser.

## Growing the directory

Moved to `references/discovery.md`, which covers both halves of it: adding a
company to a board type already known, and probing an unfamiliar host to work
out whether it is a board type at all.

The short version, because it is what makes the per-company sources viable:
Ashby, Greenhouse, Lever and the rest have no cross-company search, so the only
way to sweep them is to know which boards exist. `profile/boards.md` is that
directory, and it is the one asset a sweep builds that makes the next sweep
cheaper.

Every posting URL a sweep sees is a candidate. The recipes above are the ones
this skill ships with; the directory holds those plus everything the user's own
sweeps have turned up.
