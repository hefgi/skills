# Scripts

## merge_cv.py

Composes a RenderCV input from `cv-base.yaml` plus a track plus a per-application
overlay. Run it rather than merging by hand: the composition is deterministic,
and doing it in prose every application is where inconsistency creeps in.

```bash
scripts/merge_cv.py --base "$W/cv/cv-base.yaml" \
  --track "$W/cv/tracks/fde.yaml" \
  --overlay "$S/cv-overlay.yaml" \
  --out "$S/cv-merged.yaml" --explain
```

`--track` and `--overlay` are optional. With neither, it validates the base and
copies it through. `--explain` prints what each layer did, which is worth reading
before sending a CV. It is a `uv run` script with an inline dependency header, so
it needs no environment setup.

### Layering

Base, then track, then overlay. Later layers win. The overlay is the
per-application layer, so it overrides the track.

| Key | Effect |
|---|---|
| `headline` | Sets `cv.headline` |
| `summary` | Replaces the summary section |
| `section_order` | Orders sections. **Sections not named are dropped**, which is how a track shortens a CV. |
| `skills_groups` | Selects and orders skill groups by label. Unlisted groups are dropped. |
| `merged_entries` | Defines collapsed entries that `treatment: merge` targets. |
| any other list key | Defines a section the base does not carry, such as a one-line `references`. |

Per-company, under `experience:`:

| Key | Effect |
|---|---|
| `treatment` | `promote` (own entry), `nest` (a line under `nest_under`), `merge` (folded into a `merged_entries` target), `omit` (hidden) |
| `nest_under` / `nest_as` | Parent entry, and optional user-approved prose for the nested line |
| `merge_into` | Which `merged_entries` key absorbs this role |
| `highlight_order` | Highlight ids, most important first. Unlisted highlights keep their order and follow. |
| `drop_highlights` | Highlight ids to remove |
| `max_highlights` | Cap, applied after ordering and drops |
| `position_override` | Retitle for accuracy. Dates and company are never overridden. |
| `rewrite` | Map of highlight id to replacement text |

### Highlight ids

Tracks refer to highlights by name rather than index, because an index silently
retargets when the base gains a bullet, and a retargeted rewrite is how a CV ends
up claiming something the user did not do.

An id is either declared explicitly with a leading marker in `cv-base.yaml`:

```yaml
highlights:
- "[budget] Owned a **$4M engineering budget** and put in ROI controls."
```

or derived from the first three words when no marker is present
(`Owned a **$4M...**` becomes `owned-a-4m`). Explicit markers are strongly
preferred: they survive rewording, which derived ids do not. The marker is
stripped from the rendered output, so it never reaches the PDF.

Ordering, dropping, and rewriting all resolve ids against the base, and ids
travel with their bullets through a reorder. A prefix match resolves when
unambiguous; an ambiguous one is an error rather than a guess.

Ids survive every layer, so an overlay can address a bullet by the same name the
track used, including one the track has already rewritten. The marker is stripped
once at write time rather than per layer, which is what makes that work.

### What it refuses to do

The base holds every fact, and every downstream layer may only select, reorder,
and rephrase. The script exits non-zero rather than fabricating:

- A company in `experience` that is not in the base
- A highlight id that matches nothing, or matches several things ambiguously
- A `skills_groups` label that is not in the base
- A `section_order` naming a section that neither the base nor the track defines
- `nest_under` pointing at an entry that was omitted or does not exist
- `merge_into` pointing at an undefined `merged_entries` key, or one missing its
  position and dates

Each error names the offending key and lists what was available, so the fix is
obvious. When a track genuinely needs a fact the base lacks, add it to
`cv-base.yaml` first and confirm with the user that it is true. That ordering is
the point: a CV the user cannot defend in an interview is worse than one that
matches the posting less closely.

### Testing a change

```bash
scripts/merge_cv.py --base <base> --track <track> --out /tmp/check.yaml --explain
rendercv render /tmp/check.yaml --design "$W/cv/design.yaml" -o /tmp/check-out
```

Keep PNG output on and check the page count, since a track that drops too little
silently spills onto a third page.
