#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run the blocker regression cases.

These are real postings from a real sweep. Every DROP case reached the user
before the geography and function blockers existed; every KEEP case is one a
careless fix breaks. The pre-sales rows are the sharpest: a `sales` substring
exclusion removes all of them and is therefore wrong.

    scripts/test_blockers.py

Exits non-zero on the first regression, so it can gate a change to
`blocker_for()` or to any of the geography helpers.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent / "evals" / "fixtures" / "blocker-cases.json"


def load_pipeline():
    spec = importlib.util.spec_from_file_location("pipeline", HERE / "pipeline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if not CASES.exists():
        print(f"error: no cases at {CASES}", file=sys.stderr)
        return 2

    pipeline = load_pipeline()
    data = json.loads(CASES.read_text(encoding="utf-8"))
    criteria = data["criteria"]

    failures = []
    for case in data["cases"]:
        got = pipeline.blocker_for(case, criteria)
        want = case["expect"]
        if got != want:
            failures.append((case, want, got))

    total = len(data["cases"])
    for case, want, got in failures:
        print(f"FAIL want={want!s:18} got={got!s:18} "
              f"{case['role'][:44]:46} {case['location'][:34]}")

    print(f"{total - len(failures)}/{total} blocker regression cases pass")
    if failures:
        print("\nThese are real postings. A failure here means a row the user "
              "cannot act on reaches their pipeline, or one they want is "
              "hidden from them.", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
