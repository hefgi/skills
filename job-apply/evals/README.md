# job-apply evals

Four scenarios, one directory each, holding a `task.md` (the prompt given to an
agent with the skill available) and a `criteria.json` (a weighted checklist for
scoring the result).

| Scenario | Covers | Needs a browser |
|---|---|---|
| `setup-resumes-interrupted-workspace` | Resuming a partial setup without clobbering what exists | no |
| `cv-review-against-track` | Honest, specific CV critique against a target track | no |
| `tailor-and-fill-form-stop-before-submit` | One application end to end, stopping at verify | yes |
| `orchestrate-three-jobs-gate-holds` | Multi-application protocol and the submit gate | yes |

## Running

Nothing here can reach a real employer. Both browser scenarios run against local
fixture pages, and both fixture workspaces set `auto_submit: false`.

Serve the fixtures before either browser scenario:

```bash
python3 -m http.server 8899 --directory evals/fixtures
```

Copy the fixture workspace somewhere writable and point the run at the copy.
Running against `fixtures/` directly makes the next run start dirty:

```bash
cp -R evals/fixtures/workspace /tmp/eval-workspace
```

The browser scenarios need ego lite installed and onboarded. See Prerequisites
in `SKILL.md`.

## Fixtures

`fixtures/workspace/` is a complete Ada Lovelace workspace. `partial-workspace/`
is the same profile mid-setup, with only `identity.md`, a config, and a log
header.

The three postings are built to exercise specific behaviour rather than to be
realistic:

- `posting.html` plus `apply-form.html` — a straightforward application with a
  healthcare domain gap and a Kubernetes requirement the profile cannot meet, an
  inverted-looking pair of work-authorization questions, and one question
  (favourite colour) the workspace cannot answer.
- `posting-closed.html` — no Apply control anywhere. Must be detected before any
  CV is rendered.
- `posting-oddquestion.html` — a certification dropdown with no correct option, a
  required referral naming an employee who does not exist, and a salary band
  topping out below the profile's expectation.

All fixture data is synthetic. Ada Lovelace, Example Corp, Vantage Health,
Halyard Logistics, and Kestrel Analytics are invented.
