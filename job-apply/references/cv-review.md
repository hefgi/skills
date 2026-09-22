# Workflow 2: Review and optimize a CV

A critical review, then concrete edits. The default mode is honest rather than
flattering. A user asking for a CV review is asking to be told what a hiring
manager would think and not say.

Be specific. "Bullet 3 in the Acme role lists four tools and no outcome" is
useful. "Consider strengthening your bullets" is not.

## Contents

- [Why RenderCV](#why-rendercv)
- [The review order](#the-review-order)
- [Structural checks](#structural-checks)
- [Line-level checks](#line-level-checks)
- [Quantification](#quantification)
- [Presentation](#presentation)
- [RenderCV mechanics](#rendercv-mechanics)
- [Output format](#output-format)

## Why RenderCV

Recommend RenderCV, and say why rather than just asserting it:

- **Content and design are separate files.** Facts live in `cv-base.yaml`,
  appearance in `design.yaml`. Tailoring per job touches content only, and every
  CV the user sends looks consistent.
- **Text output parses in applicant tracking systems.** PDFs exported from
  design tools frequently lose reading order, so a parser sees scrambled text.
  A CV that a parser mangles is often never read by a person.
- **Reproducible.** The CV is a text file under version control. Diffs are
  reviewable, and a change three months ago is recoverable.
- **Tailoring is mechanical.** Reordering sections and rewriting bullets per
  application is editing YAML, not fighting a layout.

A user committed to Word or a design tool can still use everything else in this
skill. Say what they lose: per-application tailoring becomes manual, and
parsing reliability is unknown.

## The review order

Structure before wording. A perfectly worded bullet in a CV with an unexplained
two-year gap is wasted effort, because the reader is already suspicious.

1. Timeline integrity
2. Audience fit and track separation
3. Cross-variant consistency
4. Ordering and emphasis
5. Bullet quality
6. Quantification
7. Presentation and length
8. Typos

## Structural checks

### Timeline integrity is the top credibility risk

Check every date against every other date.

- **No two full-time roles may silently overlap.** A reader who spots an overlap
  assumes either an error or a misrepresentation, and both are fatal. Every
  overlap needs an explicit reconciling clause: "concurrent with", "advisory
  while at", "via my consultancy".
- **Unexplained gaps** over a few months invite the question. A brief note
  closes it.
- **Education dates against employment dates.** Working while studying is
  normal, but an unexplained overlap still reads as sloppiness.
- **A short recent role that just ended** raises "what happened". Address it
  structurally, not cosmetically. See below.

When an overlap is real, the fix is a clause, not a date change. Suggest wording
and let the user pick, since only they know the truth. Never silently alter
someone's employment history.

### One CV cannot serve two different buyers

The highest-leverage structural insight. When a user targets two materially
different role types, one document actively hurts both.

A hands-on engineering manager hiring an individual contributor wants: ships
code, talks to customers, comfortable in ambiguity. They get nervous seeing "VP
who managed a $4M budget and 40 engineers", because they read too senior, too
expensive, will not do the actual work.

An executive recruiter hiring a VP or CTO wants: org scaling, hiring, P&L,
strategy, business outcomes. They get nervous seeing bullets about specific
libraries and tooling, because they read an individual contributor who has not
learned to delegate.

A CV that signals both gives each audience the disqualifying half. The fix is
two tracks over one set of facts, with different emphasis and ordering. Not two
different truths, and this distinction matters: the same career, framed for who
is reading.

### Variants must never contradict each other

When two tracks describe the same role differently on a **fact**, that is a bug.
"Solo founder, small team" in one and "grew to 18 people" in the other cannot
both be true, and two people at the same company will compare notes.

Emphasis may differ freely. Facts may not. After any change to `cv-base.yaml`,
re-check every track against it.

### Strict reverse-chronological order

Sort by recency, most recent first. Do not reorder by impact, even when an older
role is more impressive.

Deviating makes a reader wonder what is being hidden, and it confuses applicant
tracking systems that assume chronological ordering. A current founder or
consulting role at the top is completely normal.

For roles that overlap, sort by end date, so the most recently ended appears
first.

### The top-third rule

Whatever the strongest proof point is, it belongs in the top third of page one.
That is what gets read in the first pass.

For an executive track, that is usually scale, funding raised, or an exit. For a
hands-on track, it is usually recent shipping and customer-facing work.

### Reframe short or ended engagements structurally

A six-month engagement that just ended looks like a problem. Nested as a client
engagement under the user's own consultancy, it becomes evidence of consulting
work. Same facts, and the second framing is accurate when the user does have an
entity.

Never lead a summary with "fixed-term". It signals impermanence before the
reader has seen any value. Lead with what was delivered.

Named clients are usually an asset, since an unfamiliar company plus a short
stint invites suspicion. Confirm the client can be named before naming them, and
fall back to "confidential client (via <consultancy>)".

### Do not volunteer negatives

"Company ceased operations due to lack of product-market fit" is honest and a
self-inflicted wound. Reframe to what was built, or cut it. The failure does not
need stating: a past-tense founder role with an end date says enough.

Also ask whether a short failed role belongs on an executive CV at all. Not
every true thing earns its space.

### Title hygiene

"Founder & CEO / CTO" reads as a company small enough that titles were
self-assigned. Suggest picking the one that supports the target track and
letting the other come up in conversation.

## Line-level checks

### Bullets state outcomes, not tools

The most common failure. A bullet like:

```
Built the ingestion pipeline (Kafka, Dagster, ClickHouse, dbt, Airflow)
```

reads as keyword stuffing and buries the point. Four tools in a parenthetical
crowd out the outcome. The fix:

```
Built the ingestion pipeline so that analysts queried same-day data instead of
waiting for an overnight batch, using Kafka and ClickHouse
```

The formula: **cut one tool from every parenthetical, add "so that" or
"resulting in".** Applied across a CV it changes the document's character.

Keep enough technology to be credible and searchable. Two named tools per bullet
is usually right. The CV needs keywords for parsers, but not at the cost of
every bullet reading identically.

### Avoid over-precise specifics that date badly

Exact model version numbers, minor library versions, and current-quarter product
names go stale within months and then read as a CV that was not updated. Name
the category or the major tool.

### Every bullet earns its line

Cut bullets that describe responsibilities rather than results. "Responsible for
the frontend team" says nothing that the job title did not already say.

Six strong bullets on a recent role beats twelve mixed ones. Older roles need
two or three, and roles over ten years old often need one line or just the title
and dates.

## Quantification

Numbers are the strongest thing on a CV, and the wrong numbers do damage.

### Keep numbers that survive scrutiny

Concrete, defensible, and impressive at the target seniority: team grown from 15
to 40, 100TB processed, funding raised, lead time improved 2.5x, an exit.

### Small numbers actively hurt

A number that sounds like an achievement to the person who earned it can read as
evidence of failure to a reader at scale. Revenue of 5K monthly, or assets of
300K for a fund, invites "so it did not work?".

Options: contextualize with the timeframe ("in the first six months"), or drop
the figure and lead with what is genuinely strong, such as the raise, the
investors, or the exit. Say this plainly to the user. It is uncomfortable and it
is the single most common quantification error.

### Do not volunteer deflating precision

"Managed 40% of company engineering spend" invites the reader to compute total
company spend, and the answer may undercut the framing. State the budget or
state the scope. Not the ratio that lets them do arithmetic against you.

### Executive tracks need organizational metrics

A CV for a VP or CTO role that quantifies only technology is missing the
evidence that audience wants: attrition and retention, engineer satisfaction,
on-time delivery rate, promotion rate, hiring throughput, time to first commit
for new hires.

These are harder to remember than tool names, so ask for them directly.

### Phrase the arithmetic correctly

"Cut lead time by 2.5x" is mathematically confused. "Improved lead time to
change by 2.5x", or better, "cut lead time from five days to two". Use a proper
multiplication sign or the word, consistently.

## Presentation

### Seniority is inversely proportional to logo count

Ten skill categories with proficiency bars reads junior. An executive reader
sees a list of thirty technologies and concludes the candidate cannot
distinguish what matters.

- No skill bars, no percentages, no star ratings. They are self-assessed and
  therefore meaningless.
- Group into roughly four labelled lines.
- Cut anything niche, joke-named, or obsolete from a headline skills section.
- The more senior the target, the fewer items.

### Length

Two pages is fine for senior and executive profiles. One page for early career.
Three pages needs a strong reason, and academic CVs are the usual one.

Check by rendering PNG and looking at the page count:

```bash
rendercv render "$W/cv/cv-base.yaml" --design "$W/cv/design.yaml" -o /tmp/cv-check
```

A CV that is 2.1 pages, with three lines dangling onto page three, looks
careless. Either cut to fit two or expand to fill three.

### References

"Available on request" as a one-line section, or omit entirely. Named
referees with contact details eat prime space and are unusual now.

### Typos are not negotiable

At senior level a typo undercuts the entire document, because attention to
detail is part of what is being assessed. Check technology names specifically,
since they are where errors cluster and where a reader will notice: Kubernetes
not Kubernetees, Terraform not TerraForm, PostgreSQL, TypeScript, GitHub.

Read every bullet for grammar that survived editing, like "Scaled the org by
from 15 to 40".

## RenderCV mechanics

### Rendering

**Use absolute paths for every path argument.** RenderCV resolves `-o` and
`--pdf-path` relative to the directory containing the input YAML, not the
current working directory. Relative paths therefore land somewhere surprising,
such as `cv/applications/...` instead of `applications/...`.

```bash
W=/abs/path/to/workspace
S="$W/applications/<slug>"

rendercv render "$W/cv/cv-base.yaml" --design "$W/cv/design.yaml" \
  -o "$S" \
  --pdf-path "$S/<Lastname>_<Company>_<Role>.pdf" \
  --dont-generate-markdown --dont-generate-html --dont-generate-png
```

**`--pdf-path` is required whenever more than one variant exists.** RenderCV
names output from the `cv.name` field, so two tracks rendered without it
overwrite each other silently and the user ends up sending the wrong CV.

`-o` controls where the intermediate `.typ` and any PNGs land. Without it they
go to `<yaml-dir>/rendercv_output/`, which clutters `cv/`.

Keep PNG generation on while iterating, to check page count and layout. Add
`--dont-generate-png` for the final render.

`--watch` re-renders on save, which is useful during a heavy editing pass.

### Overriding without editing files

```bash
rendercv render cv/cv-base.yaml --design cv/design.yaml \
  --cv.sections.summary.0 "A summary written for this application"
```

Useful for a one-field change. Multi-field tailoring belongs in an overlay file,
so the application folder records what was actually sent.

### Applying track and overlay files

`cv/tracks/<track>.yaml` and `applications/<slug>/cv-overlay.yaml` are this
skill's own structures, not RenderCV inputs. Compose them by reading base plus
track plus overlay, producing a merged CV YAML in the application folder, and
rendering that. Keep the merged file, since it is the record of what was sent.

Overlays reorder, reweight, and rewrite. They never add a fact absent from
`cv-base.yaml`.

### Common validation failures

- Phone must be E.164: `+441234567890`, quoted in YAML.
- Bullet characters limited to `● • ◦ - ◆ ★ ■ — ○`.
- Dates as `YYYY-MM` or `YYYY`, or `present` for current.
- Colons inside unquoted YAML strings break parsing. Quote any string containing
  a colon.
- Markdown works in text fields: `**bold**`, `[text](url)`.

Read the `rendercv` skill for full field documentation.

## Output format

Deliver a review as:

1. **The honest summary.** Two or three sentences on how this CV lands with the
   target audience. Lead with the real problem, not with praise.
2. **A prioritized fix list**, highest impact first, each with the specific
   location, what is wrong, and the concrete replacement. Five to eight items,
   because a list of twenty gets ignored.
3. **What is already working**, briefly, so the user does not undo it.
4. **Open questions**, where a fix depends on facts only the user has.

Then offer to apply the fixes. Do not apply them unasked: this is the user's
career history, and some fixes involve judgment calls about how to frame their
own experience.

Track which recommendations the user accepts and which they decline. A declined
recommendation should not resurface at every subsequent review.
