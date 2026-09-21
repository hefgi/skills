# Writing rules

Governs all generated prose: cover letters, long-form application answers, CV
summaries, and CV bullets.

A hiring manager reads hundreds of these. Anything that pattern-matches to
generated text gets discounted, and increasingly gets discarded. The goal is
prose that reads as though the user wrote it on a good day.

## Contents

- [Hard rules](#hard-rules)
- [Route through the humanizer skill](#route-through-the-humanizer-skill)
- [Cover letters](#cover-letters)
- [Application answers](#application-answers)
- [Voice](#voice)
- [Patterns to avoid](#patterns-to-avoid)
- [Pre-save checklist](#pre-save-checklist)

## Hard rules

**No em dashes.** Not in cover letters, not in application answers, not in CV
prose. Use a comma, a colon, a period, or restructure the sentence. Em dash
overuse is among the most recognizable tells of generated text, and it is the
one thing most reliably noticed.

```
Bad:  I led the migration — it took four months — and shipped on time.
Good: I led the migration. It took four months and shipped on time.
Good: I led the migration, which took four months, and shipped on time.
```

Check before saving, on prose files only:

```bash
grep -n "—" "$S/cover-letter.md" "$S/answers.md" && echo "FIX: em dashes present"
```

Scope it to the prose. `cv/design.yaml` may legitimately contain `—` as a
RenderCV bullet character, so a repo-wide grep produces a false positive on a
file this rule was never about.

En dashes (–) in numeric ranges such as `2020–2024` are fine. The rule is about
the em dash used as a parenthetical or dramatic break.

**Never claim a fact not in the workspace.** Every number, technology, title,
and responsibility traces back to `cv/cv-base.yaml`, `profile/narrative.md`, or
something the user said in this conversation. A cover letter that overclaims
becomes the user's problem in an interview.

**Use the user's own framing.** `profile/narrative.md` holds prose the user has
approved. Recombine it. Do not invent a new voice for them.

**Pronouns.** Use what `profile/identity.md` records. If it is empty, use
they/them, and never infer from a name.

## Route through the humanizer skill

After writing any cover letter or long-form answer, and before saving it, run it
through the `humanizer` skill if it is available. It catches inflated symbolism,
promotional language, vague attributions, rule-of-three padding, negative
parallelisms, and the vocabulary that marks generated text.

Invoke it on the draft, apply what it flags, then save. Do this once per
document rather than per paragraph.

**When `humanizer` is not installed**, do the pass manually against the
[Patterns to avoid](#patterns-to-avoid) list below, which covers the same
ground. Read the draft once looking only for those patterns. This is a real
substitute, not a formality: the list exists because these are the specific
tells that get an application discounted.

Short factual answers, such as a notice period or a salary figure, do not need
it. It is for prose.

## Cover letters

Four short paragraphs, roughly 250 to 350 words total. Shorter is better than
longer. Nobody has ever been rejected for a cover letter that was too brief.

**Paragraph 1: why this company and this role, specifically.** Something drawn
from the actual posting or the company, not a generic statement of enthusiasm.
If nothing specific can be said, the letter is not worth sending, and that is
worth telling the user.

**Paragraph 2: the single most relevant proof point, with a number.** One, not
three. Pick what the posting most cares about and give the concrete outcome.

**Paragraph 3: the closest thing to their hardest stated requirement.** If the
user meets it, show it. If they do not, use the honest framing from the
`Known gaps` section of `profile/narrative.md` rather than dodging. A reader who
spots an evaded requirement stops trusting the rest.

**Paragraph 4: a plain close.** Available to talk, what is attached. No
flourish.

Do not restate the CV. The CV is attached. The letter says the one thing the CV
cannot: why this specific role, and why now.

Address a named person only if the posting names one. Otherwise open without a
salutation, or use the team name. "Dear Hiring Manager" is acceptable but flat.
Never guess a name.

Render to PDF matching the CV's visual identity, so the two documents look like
a set.

## Application answers

**Match the length to the box.** A single-line input wants one sentence. A
textarea with a 200-word limit wants 150 to 200 words. Respect stated limits
exactly, since some forms truncate silently.

**Answer the question asked.** Forms often ask something oddly specific. Answer
that, not the question it resembles.

**For `reuse: adapt` answers**, re-point the base framing at this company using
the posting. Never submit an `adapt` answer verbatim: it will read as a template
because it is one.

**For factual questions**, give the fact. No preamble, no framing, no
elaboration. "One month from signing." is a complete answer to a notice period
question.

## Voice

First person. Direct. Concrete.

- Past tense for past work, present for current.
- Specifics over adjectives. "Cut deploy time from 40 minutes to 6" beats
  "dramatically improved deployment efficiency".
- Say "I" for individual work and "we" for team work, accurately. Claiming a
  team's work as solo is the fastest way to fail a reference check.
- Vary sentence length. Uniform sentence rhythm is itself a tell.
- Plain words. "Use", not "utilize". "Help", not "facilitate".

## Patterns to avoid

These are the recurring markers of generated application text:

- Em dashes as parentheticals. The hard rule above.
- "I am passionate about", "I am excited to", "I thrive in"
- "Leveraging", "utilizing", "spearheaded", "orchestrated", "pioneered"
- "Deeply", "truly", "incredibly", "uniquely positioned"
- Rule-of-three lists where two items would do, or three where the third is
  padding
- Negative parallelism: "not just X, but Y"
- "-ing" clauses tacked on to imply significance: "...shipping the feature,
  demonstrating my commitment to quality"
- Restating the job description back at the reader
- "As you can see from my resume"
- Superlatives about oneself: "world-class", "exceptional", "unparalleled"
- Concluding paragraphs that summarize what was just said

## Pre-save checklist

Before writing any prose file to disk:

1. Zero em dashes. Grep for it.
2. Every claim traceable to the workspace or this conversation.
3. Ran through the `humanizer` skill.
4. Within any stated length limit.
5. Company and role names spelled as the posting spells them.
6. No placeholder text left behind. Grep for `[`, `<`, `TODO`, `XXX`.
7. Reads like one person wrote it, not like a merge of templates.

Item 5 is worth its own check. Misspelling the company name on an application
undoes everything else in the document.
