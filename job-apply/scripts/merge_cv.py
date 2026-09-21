#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Compose a RenderCV input from cv-base.yaml plus a track plus an overlay.

The base holds every fact. The track and overlay may only select, reorder, and
rephrase what is already there. Introducing a company or a highlight that is not
in the base is a fabrication the user would have to defend in an interview, so
this script refuses to do it and says which key was at fault.

Usage:
  merge_cv.py --base cv/cv-base.yaml --track cv/tracks/fde.yaml \
              --overlay applications/<slug>/cv-overlay.yaml \
              --out applications/<slug>/cv-merged.yaml

--track and --overlay are both optional. With neither, this validates the base
and copies it through. Pass --explain to print what each layer did.
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

import yaml


class MergeError(Exception):
    """A merge that would fabricate, drop, or misname something."""


def load(path: Path | None) -> dict:
    if path is None:
        return {}
    if not path.is_file():
        raise MergeError(f"not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise MergeError(f"{path}: expected a mapping at the top level")
    return data


def company_of(entry: dict) -> str | None:
    for field in ("company", "institution", "name", "label"):
        if isinstance(entry, dict) and entry.get(field):
            return str(entry[field])
    return None


def highlight_id(text: str) -> str:
    """Derive a stable slug from highlight text, for named ordering.

    Tracks refer to highlights by name (`hands-on`, `budget`) rather than index,
    because an index silently retargets when the base gains a bullet, and a
    retargeted rewrite is how a CV ends up saying something the user did not do.
    A base highlight may declare its own id with a leading `[id]` marker;
    otherwise the id is derived from the first few words.
    """
    marker = re.match(r"^\s*\[([a-z0-9][a-z0-9-]*)\]\s*(.*)$", text, re.IGNORECASE)
    if marker:
        return marker.group(1).lower()
    stripped = re.sub(r"[*_`]", "", text).strip().lower()
    words = re.findall(r"[a-z0-9]+", stripped)[:3]
    return "-".join(words) if words else "untitled"


def highlight_text(text: str) -> str:
    """Strip a leading [id] marker, which is metadata rather than content."""
    marker = re.match(r"^\s*\[[a-z0-9][a-z0-9-]*\]\s*(.*)$", text, re.IGNORECASE)
    return marker.group(1) if marker else text


def resolve_ids(highlights: list[str], where: str) -> tuple[list[str], dict[str, int]]:
    """Return (text with markers intact, id -> index).

    The marker is deliberately NOT stripped here. Stripping per layer would mean
    the track layer consumes the explicit ids and the overlay layer only ever
    sees derived first-three-words ids, so an overlay could not reference the
    documented id. Markers are stripped once, at write time, by strip_markers().
    Ambiguous ids are an error, not a guess.
    """
    clean, index_of, collisions = [], {}, set()
    for i, raw in enumerate(highlights):
        clean.append(raw)
        hid = highlight_id(raw)
        if hid in index_of:
            collisions.add(hid)
        index_of[hid] = i
    if collisions:
        raise MergeError(
            f"{where}: highlight ids {', '.join(sorted(collisions))} are ambiguous. "
            f"Disambiguate by prefixing a highlight in cv-base.yaml with a marker, "
            f"e.g. '[budget] Owned a $4M engineering budget'."
        )
    return clean, index_of


def pick(name: str, index_of: dict[str, int], where: str, kind: str) -> int:
    """Resolve a named or numeric highlight reference to an index."""
    if isinstance(name, int):
        if not 0 <= name < len(index_of):
            raise MergeError(f"{where}: {kind} index {name} is out of range")
        return name
    key = str(name).lower()
    if key in index_of:
        return index_of[key]
    matches = [hid for hid in index_of if hid.startswith(key) or key in hid]
    if len(matches) == 1:
        return index_of[matches[0]]
    if len(matches) > 1:
        raise MergeError(
            f"{where}: {kind} '{name}' matches several highlights "
            f"({', '.join(sorted(matches))}). Use a more specific id."
        )
    raise MergeError(
        f"{where}: {kind} '{name}' does not match any highlight. "
        f"Available: {', '.join(sorted(index_of))}. "
        f"Tracks select from cv-base.yaml; they cannot introduce a new bullet."
    )


def shape_entry(entry: dict, spec: dict, where: str, log: list[str]) -> dict:
    """Apply per-entry shaping: rewrites, ordering, drops, caps, title override."""
    entry = copy.deepcopy(entry)
    raw = entry.get("highlights") or []
    highlights, index_of = resolve_ids(raw, where)

    # Carry each highlight's id alongside its text. Re-deriving ids after a
    # reorder would read them off already-stripped text, losing every explicit
    # [id] marker, so the ids travel with the bullets instead.
    ids = [""] * len(highlights)
    for hid, i in index_of.items():
        ids[i] = hid

    def remap() -> dict[str, int]:
        return {hid: i for i, hid in enumerate(ids) if hid}

    for ref, new_text in (spec.get("rewrite") or {}).items():
        i = pick(ref, remap(), where, "rewrite")
        # Re-attach the id so a later layer can still address this bullet by the
        # name the base gave it, even though the prose has changed.
        highlights[i] = f"[{ids[i]}] {new_text}" if ids[i] else new_text

    order = spec.get("highlight_order")
    if order is not None:
        if not isinstance(order, list):
            raise MergeError(f"{where}: highlight_order must be a list")
        seen, picked, picked_ids = set(), [], []
        for ref in order:
            i = pick(ref, remap(), where, "highlight_order")
            if i in seen:
                raise MergeError(f"{where}: highlight_order repeats '{ref}'")
            seen.add(i)
            picked.append(highlights[i])
            picked_ids.append(ids[i])
        # Anything not named is appended, so a partial order promotes the listed
        # bullets without silently discarding the rest. drop_highlights is the
        # explicit way to remove one.
        for i, h in enumerate(highlights):
            if i not in seen:
                picked.append(h)
                picked_ids.append(ids[i])
        highlights, ids = picked, picked_ids

    dropped = spec.get("drop_highlights") or []
    if dropped:
        drop_idx = {pick(ref, remap(), where, "drop_highlights") for ref in dropped}
        highlights = [h for i, h in enumerate(highlights) if i not in drop_idx]
        ids = [d for i, d in enumerate(ids) if i not in drop_idx]
        log.append(f"{where}: dropped {len(drop_idx)} highlight(s)")

    cap = spec.get("max_highlights")
    if cap is not None:
        if not isinstance(cap, int) or cap < 0:
            raise MergeError(f"{where}: max_highlights must be a non-negative integer")
        if len(highlights) > cap:
            log.append(f"{where}: capped {len(highlights)} highlights to {cap}")
            highlights = highlights[:cap]

    override = spec.get("position_override")
    if override:
        # Retitling for accuracy is allowed; the dates and company are not.
        entry["position"] = override
        log.append(f"{where}: position -> {override}")

    if highlights:
        entry["highlights"] = highlights
    else:
        entry.pop("highlights", None)
    return entry


def apply_experience(section: list, layer: dict, where: str, log: list[str]) -> list:
    rules = layer.get("experience") or {}
    merged_specs = layer.get("merged_entries") or {}
    if not rules:
        return section

    known = {company_of(e) for e in section if company_of(e)}
    for company in rules:
        if company not in known:
            raise MergeError(
                f"{where}: '{company}' is not in cv-base.yaml. "
                f"Known: {', '.join(sorted(known)) or 'none'}. "
                f"Add the role to the base first, and confirm it is true."
            )

    promoted: list = []
    nested: dict[str, list[str]] = {}
    merged: dict[str, list[dict]] = {}

    for entry in section:
        company = company_of(entry)
        spec = rules.get(company) or {}
        treatment = spec.get("treatment", "promote")

        if treatment == "omit":
            log.append(f"{where}: omitted {company}")
            continue

        if treatment == "nest":
            parent = spec.get("nest_under")
            if not parent:
                raise MergeError(f"{where} -> {company}: 'nest' needs nest_under")
            if parent not in known:
                raise MergeError(
                    f"{where} -> {company}: nest_under '{parent}' is not in cv-base.yaml"
                )
            # nest_as is user-approved prose summarising the role in one line.
            text = spec.get("nest_as")
            if not text:
                label = entry.get("position") or company
                summary = entry.get("summary") or ""
                text = f"**{label}** ({company}){f': {summary}' if summary else ''}"
            nested.setdefault(parent, []).append(text)
            log.append(f"{where}: nested {company} under {parent}")
            continue

        if treatment == "merge":
            target = spec.get("merge_into")
            if not target:
                raise MergeError(f"{where} -> {company}: 'merge' needs merge_into")
            if target not in merged_specs:
                raise MergeError(
                    f"{where} -> {company}: merge_into '{target}' has no entry under "
                    f"merged_entries. Define its position, location, and dates there."
                )
            merged.setdefault(target, []).append(entry)
            continue

        if treatment != "promote":
            raise MergeError(
                f"{where} -> {company}: unknown treatment {treatment!r} "
                f"(expected promote, nest, merge, or omit)"
            )
        promoted.append(shape_entry(entry, spec, f"{where} -> {company}", log))

    for entry in promoted:
        extra = nested.pop(company_of(entry), None)
        if extra:
            entry.setdefault("highlights", []).extend(extra)

    if nested:
        raise MergeError(
            f"{where}: nested under {', '.join(sorted(nested))}, "
            f"but that entry was omitted or absent"
        )

    for target, entries in merged.items():
        spec = merged_specs[target]
        for field in ("position", "start_date", "end_date"):
            if not spec.get(field):
                raise MergeError(
                    f"{where}: merged_entries['{target}'] needs '{field}'. "
                    f"A collapsed entry still states real dates and a real title."
                )
        bullets = []
        for entry in entries:
            company = company_of(entry)
            role = entry.get("position") or ""
            bullets.append(f"**{role}**, {company}" if role else f"**{company}**")
        combined = {
            "company": target,
            "position": spec["position"],
            "start_date": spec["start_date"],
            "end_date": spec["end_date"],
            "highlights": bullets,
        }
        if spec.get("location"):
            combined["location"] = spec["location"]
        if spec.get("summary"):
            combined["summary"] = spec["summary"]
        cap = spec.get("max_highlights")
        if isinstance(cap, int) and len(combined["highlights"]) > cap:
            combined["highlights"] = combined["highlights"][:cap]
        promoted.append(combined)
        log.append(f"{where}: merged {len(entries)} role(s) into '{target}'")

    for target in merged_specs:
        if target not in merged:
            log.append(f"{where}: warning, merged_entries['{target}'] matched no role")

    return promoted


def strip_markers(cv: dict) -> None:
    """Remove [id] markers from every highlight, in place, just before writing.

    Ids are structural metadata for composing the CV, not content. They stay on
    the text through every layer so each one can address bullets by name, and
    come off once here so they never reach the PDF.
    """
    for entries in (cv.get("sections") or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("highlights"):
                entry["highlights"] = [highlight_text(str(h)) for h in entry["highlights"]]


def merge(base: dict, track: dict, overlay: dict) -> tuple[dict, list[str]]:
    if "cv" not in base:
        raise MergeError("cv-base.yaml has no top-level 'cv:' key")

    result = copy.deepcopy(base)
    cv = result["cv"]
    sections = cv.get("sections") or {}
    log: list[str] = []

    for name, layer in (("track", track), ("overlay", overlay)):
        if not layer:
            continue

        if layer.get("headline"):
            cv["headline"] = layer["headline"]

        summary = layer.get("summary")
        if summary is not None:
            sections["summary"] = summary if isinstance(summary, list) else [summary]

        if layer.get("experience"):
            if "experience" not in sections:
                raise MergeError(f"{name}: no 'experience' section in cv-base.yaml")
            sections["experience"] = apply_experience(
                sections["experience"], layer, name, log
            )

        groups = layer.get("skills_groups")
        if groups:
            available = {
                s.get("label") for s in (sections.get("skills") or []) if isinstance(s, dict)
            }
            missing = [g for g in groups if g not in available]
            if missing:
                raise MergeError(
                    f"{name}: skills_groups names {', '.join(missing)}, not in "
                    f"cv-base.yaml. Known: {', '.join(sorted(filter(None, available)))}"
                )
            order = {g: i for i, g in enumerate(groups)}
            sections["skills"] = sorted(
                (s for s in sections["skills"] if s.get("label") in order),
                key=lambda s: order[s["label"]],
            )

        # A layer may define the literal content of a section that the base does
        # not carry, such as a one-line references note. Anything longer than a
        # short list belongs in the base, where the user reviews it as fact.
        for key, value in layer.items():
            if key in sections or not isinstance(value, list):
                continue
            if key in {"section_order", "skills_groups", "titles", "highlight_order"}:
                continue
            sections[key] = value
            log.append(f"{name}: defined section '{key}'")

    order = overlay.get("section_order") or track.get("section_order")
    if order:
        missing = [s for s in order if s not in sections]
        if missing:
            raise MergeError(
                f"section_order names {', '.join(missing)}, not in cv-base.yaml or the "
                f"track. Known: {', '.join(sections)}. Either add the section to "
                f"cv-base.yaml, or define its content in the track."
            )
        dropped = [s for s in sections if s not in order]
        if dropped:
            log.append(f"section_order dropped: {', '.join(dropped)}")
        sections = {key: sections[key] for key in order}

    cv["sections"] = sections
    strip_markers(cv)
    return result, log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--track", type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--explain", action="store_true", help="print what each layer did")
    args = parser.parse_args()

    try:
        merged, log = merge(load(args.base), load(args.track), load(args.overlay))
    except MergeError as exc:
        print(f"merge_cv: {exc}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        fh.write(
            "# yaml-language-server: $schema=https://raw.githubusercontent.com/"
            "rendercv/rendercv/refs/tags/v2.8/schema.json\n"
        )
        fh.write("# Generated by merge_cv.py. Edit cv-base.yaml or the overlay instead.\n")
        yaml.safe_dump(merged, fh, sort_keys=False, allow_unicode=True, width=100)

    if args.explain:
        for line in log:
            print(f"  {line}")

    experience = merged["cv"].get("sections", {}).get("experience") or []
    print(f"wrote {args.out} ({len(experience)} experience entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
