#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Read, dedup, and write the job-search pipeline.

The pipeline is a CSV of jobs found by a sweep. This script owns every write to
it, because the three things it does are all easy to get subtly wrong by hand:

1. Reading a CSV that contains quoted commas. `applications/log.csv` really does
   hold values like "Product Engineer, Ona". Splitting on commas shifts every
   column after it, and the corruption is silent.
2. Deriving the identity key. Dedup only works if the same job produces the same
   key on every run, across runs, forever. That is a job for code, not prose.
3. Upserting without clobbering. Status and notes are the user's triage. An
   upsert that overwrites them destroys work that cannot be reconstructed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

# The pipeline schema. Deliberately has no score, rank, or fit column: the
# policy is to apply to anything with title similarity, so a score would be a
# number nobody acts on.
FIELDS = [
    "job_key",
    "first_seen",
    "last_seen",
    "company",
    "role",
    "url",
    "platform",
    "location",
    "work_mode",
    "track",
    "source",
    "status",
    "applied_date",
    "run_id",
    "drop_reason",
    "notes",
    # Appended, so a reader keyed on position still finds the first sixteen.
    # Never inferred: an empty salary is honest, a guessed one gets quoted into
    # an application.
    "salary",
    "published_date",
]

# Transitions anything may make. A status not reachable from its current value
# is refused rather than written, because an out-of-band status means two
# writers disagree about what happened, and the CSV cannot say which is right.
TRANSITIONS = {
    "new": {"queued", "skipped", "dropped", "expired", "applied"},
    "queued": {"applied", "skipped", "expired", "new"},
    "applied": {"rejected"},
    "dropped": {"new"},
    "skipped": {"new", "queued"},
    "expired": {"new"},
    "rejected": set(),
}

STATUSES = set(TRANSITIONS)

# Log statuses that mean "this job is finished, do not surface it again".
# `failed` and `incomplete` are deliberately absent: a posting that closed, or
# an application that hit a per-company quota, is worth retrying later.
LOG_TERMINAL = {"applied", "submitted_manually", "awaiting_review"}

COMPANY_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "gmbh", "sa", "sas", "bv", "nv", "plc",
    "corp", "corporation", "co", "ag", "ab", "oy", "srl", "spa", "pty", "kk",
    "technologies", "technology", "labs", "ai", "io",
}

# Seniority markers that sit in front of the actual job. "chief", "head of" and
# friends are deliberately absent: dropping them would collapse "Head of
# Engineering" into "Engineering", and an executive role is not a variant of an
# IC one. Only markers that modify the same job belong here.
SENIORITY_PREFIXES = [
    "senior", "sr", "staff", "principal", "lead", "junior", "jr", "associate",
]

# Roman and arabic levels, stripped so "Software Engineer II" and "Software
# Engineer" are one req. The level is returned as seniority so the junior filter
# can still see it.
LEVEL_SUFFIX = re.compile(r"\s+(i{1,3}|iv|v|[1-4])\s*$", re.IGNORECASE)

# Expanded so an abbreviation and its spelled-out form collide on purpose.
ROLE_EXPANSIONS = {
    "fde": "forward deployed engineer",
    "mts": "member of technical staff",
    "swe": "software engineer",
    "sre": "site reliability engineer",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "vp": "vice president",
    "cto": "chief technology officer",
    "eng": "engineering",
}

# Applicant tracking systems recognisable from a posting URL, and the slug each
# one is keyed by. This is how a sweep turns a link it happened to see into a
# board it can harvest directly on every later run, so the list is the main
# thing worth extending when a new ATS turns up.
#
# Every entry here has been confirmed to serve a public listing endpoint. An ATS
# the user merely applies through, with no way to list its roles, does not
# belong: iCIMS, Oracle HCM and the like are places you arrive from a search
# source, not places to sweep.
ATS_PATTERNS = [
    ("ashby", r"jobs\.ashbyhq\.com/([^/?#]+)"),
    ("greenhouse", r"(?:job-boards(?:\.eu)?|boards)\.greenhouse\.io/([^/?#]+)"),
    ("lever", r"jobs\.lever\.co/([^/?#]+)"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)"),
    ("workable", r"apply\.workable\.com/([^/?#]+)"),
    ("teamtailor", r"([a-z0-9-]+)\.teamtailor\.com"),
    ("recruitee", r"([a-z0-9-]+)\.recruitee\.com"),
    ("personio", r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)"),
    ("rippling", r"ats\.rippling\.com/([^/?#]+)"),
    ("breezy", r"([a-z0-9-]+)\.breezy\.hr"),
    # Workday needs the tenant, the numbered pod and the site, because a POST to
    # the wrong combination returns 422 rather than anything recoverable. Keyed
    # as tenant/wdN/site so the whole triple survives into the directory.
    # The optional locale segment is skipped explicitly: a bare [a-z-]+ would
    # also match the site name itself and capture whatever followed it. The site
    # is restricted to URL-shaped characters so a bare tenant URL, which several
    # logged applications are, yields nothing rather than capturing trailing
    # prose as a site name. A Workday POST needs all three parts exactly, and a
    # wrong one returns 422, so half a match is worse than no match.
    ("workday",
     r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
]

# Trailing qualifiers that describe who may apply rather than what the job is.
# Two postings differing only by one of these are the same req to a candidate.
ROLE_QUALIFIER = re.compile(
    r"""
    \s*[-–—,(\[]\s*
    (
        [a-z\s]*speaking
      | remote[a-z\s]*
      | hybrid[a-z\s]*
      | onsite[a-z\s]*
      | m\s*/\s*f\s*(/\s*[dx])?
      | [hf]/[mf]
      | all\s+genders?
      | uk | us | usa | emea | apac | eu | europe | ireland | england
      | united\s+kingdom | united\s+states | london | dublin | paris | berlin
      | new\s+york | san\s+francisco | remote | france | germany | spain
      | full[\s-]?time | part[\s-]?time | contract | permanent
      | \d+ | [ivx]+
    )
    \s*[)\]]?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def slug(text: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def normalize_company(company: str) -> str:
    """Reduce a company name to a stable key.

    Strips a parenthetical ("Bjak (ActAI)" is one company) and legal or filler
    suffixes, so the same employer keys identically however a board writes it.
    """
    name = re.sub(r"\([^)]*\)", " ", company or "")
    name = re.sub(r"[^\w\s&-]", " ", name)
    # Boards prefix a company with the ATS vendor ("Ash by Slingshot AI" is
    # Ashby rendering Slingshot). Left in, it would key one company two ways
    # depending on which board found it.
    name = re.sub(r"^\s*ash\s+by\s+", " ", name, flags=re.IGNORECASE)
    parts = [p for p in re.split(r"[\s_-]+", name.lower()) if p]
    while len(parts) > 1 and parts[-1] in COMPANY_SUFFIXES:
        parts.pop()
    return slug(" ".join(parts)) or slug(company or "")


def normalize_role(role: str) -> tuple[str, str]:
    """Reduce a job title to a stable key, returning (key, seniority).

    Seniority is captured rather than discarded: it is the one qualifier that
    decides whether a role is a blocker, so dropping it silently would make the
    junior-IC filter unenforceable.
    """
    text = (role or "").lower().strip().strip('"')
    # Keep bracket characters for now: the qualifier pattern uses them as the
    # anchor that tells "(UK)" from a word that merely happens to be last.
    text = re.sub(r"[^\w\s&/+(),\[\]-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Repeat: "Senior Staff Engineer (UK), French Speaking" has several layers.
    seniority: list[str] = []
    changed = True
    while changed:
        changed = False
        stripped = QUALIFIER_STRIP(text)
        if stripped != text:
            text, changed = stripped, True
        for prefix in SENIORITY_PREFIXES:
            if text.startswith(prefix + " "):
                seniority.append(prefix)
                text = text[len(prefix) + 1:].strip()
                changed = True
        level = LEVEL_SUFFIX.search(text)
        if level:
            seniority.append(level.group(1).lower())
            text = text[: level.start()].strip()
            changed = True

    words = []
    for word in re.split(r"[\s,()\[\]]+", text):
        if not word:
            continue
        word = ROLE_EXPANSIONS.get(word, word)
        # Fold the plural so "Solution Engineer" and "Solutions Engineer" are one
        # req. Boards use both spellings for the same job.
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        words.append(word)
    return slug(" ".join(words)), " ".join(seniority)


def QUALIFIER_STRIP(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = ROLE_QUALIFIER.sub("", text).strip(" -–—,([")
    return text


def job_key(company: str, role: str) -> str:
    company_key = normalize_company(company)
    role_key, _ = normalize_role(role)
    return f"{company_key}__{role_key}"


def board_slug_from_url(url: str) -> str | None:
    """Return `ats:slug` when a URL is recognisably an ATS board, else None.

    One place decides what a board slug looks like, so mining a log and
    discovering a board mid-sweep cannot disagree about the same URL. A slug
    that differs between the two would split one board into two directory
    entries, and the second would never be swept.
    """
    for ats, pattern in ATS_PATTERNS:
        found = re.search(pattern, url or "", re.IGNORECASE)
        if not found:
            continue
        parts = [g for g in found.groups() if g]
        # Workday carries tenant, pod and site; everything else is one slug.
        return f"{ats}:{'/'.join(p.lower() for p in parts)}"
    return None


def canonical_url(url: str) -> str:
    """Strip what varies between two links to the same posting.

    Tracking parameters are the common case: the same LinkedIn card yields a
    different href every time it is rendered.
    """
    u = (url or "").strip()
    u = re.sub(r"[?#].*$", "", u)
    u = re.sub(r"/+$", "", u)
    u = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)
    u = re.sub(r"^www\.", "", u, flags=re.IGNORECASE)
    return u.lower()


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def write_pipeline(path: Path, rows: list[dict]) -> None:
    """Write atomically, into the same directory so the replace is on one device.

    A half-written pipeline loses the user's triage, which is the one thing in
    the workspace that cannot be regenerated by re-running a sweep.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in FIELDS})
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def sort_rows(rows: list[dict]) -> list[dict]:
    """Deterministic reading order. Not a ranking.

    Track first because the user works one CV track at a time, then source so a
    board is reviewed as a block, then newest first.
    """
    return sorted(
        rows,
        key=lambda r: (
            r.get("track", ""),
            r.get("source", ""),
            _invert_date(r.get("first_seen", "")),
            r.get("company", "").lower(),
        ),
    )


def _invert_date(value: str) -> str:
    # Sort dates descending inside an otherwise ascending key.
    digits = re.sub(r"\D", "", value or "")
    return str(99999999 - int(digits)) if digits else "99999999"


# --------------------------------------------------------------------------
# criteria


def parse_criteria(path: Path) -> dict:
    """Parse profile/search.md.

    The file is hand-edited markdown `key: value`, matching profile/targets.md,
    so one tolerant parser covers both. Values continue across indented lines.
    Unknown keys are kept rather than rejected: a user adding a note to the file
    should never break a sweep.
    """
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("#"):
            key = None
            continue
        if re.match(r"^\s+\S", line) and key:
            data[key] += " " + line.strip()
            continue
        match = re.match(r"^([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            data[key] = value
    return {k: re.sub(r"\s+", " ", v).strip() for k, v in data.items()}


def as_list(value: str) -> list[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


# --------------------------------------------------------------------------
# blockers


JUNIOR_TITLE = re.compile(
    r"\b(intern|internship|graduate|apprentice|placement|trainee|working\s+student)\b",
    re.IGNORECASE,
)
JUNIOR_SENIORITY = {"junior", "jr", "associate"}
US_AUTH = re.compile(
    r"(must\s+be\s+(legally\s+)?authoriz|require[sd]?\s+us\s+work|us\s+citizen"
    r"|green\s+card|security\s+clearance|ts/sci|work\s+authorization\s+in\s+the\s+u)",
    re.IGNORECASE,
)


# "Remote - Texas" is a location requirement wearing the word remote: you must
# be in Texas, there is simply no office. Only UNqualified remote is genuinely
# location-independent. Every qualified string contains the bare word, so the
# qualified test has to run first or it never fires.
#
# The negative lookahead lists the qualifiers that are still reachable, so
# "Remote - EMEA" is not treated as a location requirement.
QUALIFIED_REMOTE = re.compile(
    r"remote[\s\-–—,]*(?:in\s+)?"
    r"(?!global|anywhere|worldwide|international|emea|europe|eu\b|uk\b|int\b"
    r"|united\s+kingdom)[a-z]",
    re.IGNORECASE,
)
UNQUALIFIED_REMOTE = re.compile(
    r"^\s*(remote|anywhere|global"
    r"|remote\s*[-–—,]\s*(global|anywhere|worldwide|international|emea|europe|int))"
    r"\s*$",
    re.IGNORECASE,
)

# Subdivisions of commonly excluded countries. exclude_locations names countries,
# but boards name states and provinces, so "Remote - Texas" never matches a
# "United States" exclusion without this. It lives here rather than in
# search.md because nobody should have to enumerate fifty states by hand.
COUNTRY_SUBDIVISIONS = {
    "united states": [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "maine", "maryland", "massachusetts", "michigan", "minnesota",
        "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
        "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania",
        "rhode island", "south carolina", "south dakota", "tennessee", "texas",
        "utah", "vermont", "virginia", "washington", "west virginia",
        "wisconsin", "wyoming", "washington d.c.", "washington dc",
        "district of columbia", "u.s.", "usa", "us",
        # Cities distinctive enough to name a country on their own.
        "san francisco", "new york city", "nyc", "seattle", "austin", "boston",
        "chicago", "denver", "atlanta", "los angeles", "palo alto", "mountain view",
    ],
    "canada": ["ontario", "quebec", "british columbia", "alberta", "toronto",
               "vancouver", "montreal", "ottawa", "calgary"],
    "australia": ["new south wales", "victoria", "queensland", "sydney",
                  "melbourne", "brisbane", "perth"],
    "india": ["bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
              "chennai", "karnataka", "maharashtra"],
    "singapore": [],
}


def location_mentions(location: str, place: str) -> bool:
    """Word-boundary test for a place inside a location string.

    A substring test matches `uk` inside unrelated words, which is the same
    class of bug as the bare `remote` token.
    """
    return bool(re.search(rf"(?<![a-z]){re.escape(place)}(?![a-z])",
                          location or "", re.IGNORECASE))


# A hiring policy rather than a place. "Remote-Friendly (Travel-Required) |
# San Francisco, CA | Seattle, WA" lists two US offices and a policy, and the
# policy is not a third location the user could take. Left in, it reads as an
# unnamed reachable place and rescues a posting whose every real location is
# excluded.
POLICY_NOT_A_PLACE = re.compile(
    r"^\s*(remote[\s-]*friendly|hybrid|flexible|distributed|travel[\s-]*required"
    r"|multiple\s+locations?|various(\s+locations?)?|\d+\s+locations?)"
    r"[\s\w-]*(\([^)]*\))?\s*$",
    re.IGNORECASE,
)


def location_parts(location: str) -> list[str]:
    """Split a multi-location posting into its individual locations.

    "Doha, Qatar; London, UK" is reachable because London is in it. Testing the
    whole string as one blob would drop it on Doha.

    Policy fragments are removed rather than treated as locations, since a
    posting that says "Remote-Friendly" alongside two US offices is offering
    those two offices.
    """
    parts = [p.strip() for p in re.split(r"[;|]|\s+or\s+", location or "") if p.strip()]
    places = [p for p in parts if not POLICY_NOT_A_PLACE.match(p)]
    # If every part was a policy, fall back to the raw parts: "Remote" alone is
    # a policy and an answer, and dropping it would leave nothing to test.
    return places or parts


def blocked_location(location: str, work_mode: str, criteria: dict) -> bool:
    """True when every location on a posting is somewhere the user cannot be.

    A posting is kept if ANY of its locations is reachable, because a role
    offered in London and New York is a London role to someone in London.
    """
    excluded = [e.lower() for e in as_list(criteria.get("exclude_locations", ""))]
    if not excluded:
        return False
    parts = location_parts(location)
    if not parts:
        # An absent location is unknown, not excluded. A results page often
        # omits it, and a false drop costs a job while a false keep costs a
        # glance.
        return False

    geography = [g.lower() for g in as_list(criteria.get("geography", ""))]

    for part in parts:
        qualified = QUALIFIED_REMOTE.search(part)
        if UNQUALIFIED_REMOTE.match(part):
            return False            # genuinely location-independent

        # Qualified remote names the country you must live in. Test it against
        # `geography` rather than `exclude_locations`, because an exclusion list
        # can never be complete: "Remote - Mexico" is unreachable whether or not
        # anyone thought to write Mexico down. Reachability is the shorter and
        # more honest question.
        if qualified and geography:
            if not any(location_mentions(part, g) for g in geography):
                continue            # this location is out; try the next part
        hit = None
        for country in excluded:
            if location_mentions(part, country):
                hit = country
                break
            for sub in COUNTRY_SUBDIVISIONS.get(country, []):
                if location_mentions(part, sub):
                    hit = country
                    break
            if hit:
                break
        if hit is None:
            return False            # this location is reachable, so keep the row
        # This location is excluded. work_mode: remote only rescues it when the
        # remote is unqualified, which the check above already handled: a role
        # advertised as "Remote - Canada" with work_mode remote still requires
        # being in Canada.
        if not qualified and work_mode == "remote" and not location_mentions(part, "remote"):
            return False
    return True


def blocker_for(job: dict, criteria: dict) -> str | None:
    """Return a drop reason, or None to keep.

    Only true blockers drop a row: things the user cannot legally take or has
    ruled out permanently. Everything else is kept, because the policy is to
    apply widely and a preference is not a reason to hide a job.
    """
    role = job.get("role", "")
    _, seniority = normalize_role(role)

    markers = seniority.split()
    if JUNIOR_TITLE.search(role):
        return "junior-ic"
    if any(word in JUNIOR_SENIORITY for word in markers):
        return "junior-ic"
    # A bare level of I or II, with no senior marker alongside it, is the
    # mechanical reading of "junior or mid-level IC". Levels III and up, and
    # anything carrying senior/staff/principal, are kept.
    senior_markers = {"senior", "sr", "staff", "principal", "lead"}
    if not senior_markers.intersection(markers):
        if any(m in {"i", "ii", "1", "2"} for m in markers):
            return "junior-ic"

    haystack = " ".join([role, job.get("location", ""), job.get("notes", "")])
    if US_AUTH.search(haystack):
        return "us-work-auth"

    # A role in a different profession. Matched on the role title with word
    # boundaries, so "pr" cannot match inside "product" and "sales" cannot match
    # inside "pre-sales". The terms are deliberately multi-word phrases for the
    # same reason: "head of sales" removes the sales leadership role while
    # leaving "Solutions Engineer, Pre-Sales", which is a real engineering job.
    for term in as_list(criteria.get("query_terms_exclude", "")):
        if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", role, re.IGNORECASE):
            return "function-excluded"

    location = job.get("location") or ""
    if blocked_location(location, (job.get("work_mode") or "").lower(), criteria):
        return "location"

    onsite_city = (criteria.get("onsite_requires_city") or "").strip()
    if onsite_city and (job.get("work_mode") or "").lower() == "onsite" and location:
        # Case-insensitive and on word boundaries, like every other location
        # test here. A case-sensitive compare drops every onsite role in the
        # user's own city, which is the worst possible direction for this
        # blocker to fail in: it is silent, and it removes the roles they most
        # want. A multi-location posting is onsite-acceptable if any of its
        # locations is the right city.
        if not any(location_mentions(part, onsite_city)
                   for part in location_parts(location)):
            return "onsite-elsewhere"

    company_norm = normalize_company(job.get("company", ""))
    for entry in as_list(criteria.get("companies_never", "")):
        if normalize_company(entry) == company_norm:
            return "company-excluded"
    for entry in as_list(criteria.get("company_cooldown", "")):
        name = re.split(r"\s+until\s+", entry, maxsplit=1)
        if normalize_company(name[0]) != company_norm:
            continue
        if len(name) == 2:
            until = name[1].strip()
            if until and until >= date.today().isoformat():
                return "cooldown"
        else:
            return "cooldown"

    for industry in as_list(criteria.get("industries_avoid", "")):
        if industry.lower() in haystack.lower():
            return "industry"

    return None


def infer_track(job: dict, criteria: dict) -> str:
    """Pick a track from the query-term lists, or say `both` rather than guess.

    A wrong track sends the wrong CV, so an unmatched title is reported as
    ambiguous and left for job-apply to resolve against the posting text.
    """
    if job.get("track") in {"fde", "leadership", "both"}:
        return job["track"]
    role = (job.get("role") or "").lower()
    hits = set()
    for track in ("fde", "leadership"):
        for term in as_list(criteria.get(f"query_terms_{track}", "")):
            if term.lower() in role:
                hits.add(track)
    if len(hits) == 1:
        return hits.pop()
    return "both"


# --------------------------------------------------------------------------
# commands


def cmd_key(args) -> int:
    role_key, seniority = normalize_role(args.role)
    print(json.dumps({
        "job_key": job_key(args.company, args.role),
        "company_key": normalize_company(args.company),
        "role_key": role_key,
        "seniority": seniority,
    }, indent=2))
    return 0


def cmd_mine(args) -> int:
    """Summarise applications/log.csv so setup can seed from evidence.

    Mining what the user actually applied to beats interviewing them about what
    they want: the log is a record of revealed preference, and it already names
    the boards worth sweeping.
    """
    log = Path(args.log)
    if not log.exists():
        die(f"no application log at {log}")
    rows = read_csv(log)
    if not rows:
        die(f"{log} has no rows to mine")

    platforms = Counter()
    tracks = Counter()
    per_company = Counter()
    companies: dict[str, str] = {}
    titles: dict[str, str] = {}
    boards: set[str] = set()
    cooldown: list[dict] = []
    retryable: list[dict] = []

    for row in rows:
        platform = (row.get("platform") or "").strip()
        if platform:
            platforms[platform] += 1
        track = (row.get("track") or "").strip()
        if track:
            tracks[track] += 1

        company = (row.get("company") or "").strip()
        if company:
            companies.setdefault(normalize_company(company), company)
            per_company[normalize_company(company)] += 1
        role = (row.get("role") or "").strip()
        if role:
            titles.setdefault(slug(role), role)

        url = row.get("url") or ""
        board = board_slug_from_url(url)
        if board:
            boards.add(board)

        notes = (row.get("notes") or "").lower()
        status = (row.get("status") or "").strip().lower()
        # Require wording that is actually about a limit on applying. Matching a
        # bare "cap" or "application" pulls in every ordinary submission note and
        # would cool down boards the user is applying through happily.
        if re.search(
            r"caps? applications|capped at|application cap|per-candidate"
            r"|we limit|limiting applications|limit of \d+|quota"
            r"|\d+\s+applications?\s+per|per \d+ days",
            notes,
        ):
            # One entry per company: the same cap mentioned on five applications
            # is still one company to avoid, and a repeated list is noise a user
            # then has to hand-deduplicate.
            if not any(c["company_key"] == normalize_company(company) for c in cooldown):
                stated = re.search(r"(?:cap\w*(?:\s+\w+){0,3}?|limit of)\s+(\d+)", notes)
                cooldown.append({
                    "company": company,
                    "company_key": normalize_company(company),
                    "evidence": row.get("notes", "")[:200],
                    # A cap is only a reason to skip a board once it is reached.
                    # Reporting the stated limit next to the number actually sent
                    # stops a mention of "caps at 3" from silently blocking a
                    # board the user has used once.
                    "stated_cap": int(stated.group(1)) if stated else None,
                })
        if status in {"failed", "incomplete", "draft"}:
            retryable.append({
                "company": company,
                "role": role,
                "status": status,
                "notes": row.get("notes", ""),
            })

    for entry in cooldown:
        entry["applications_logged"] = per_company[entry["company_key"]]
        cap = entry.get("stated_cap")
        # Advisory only. The user decides; mining just stops them guessing.
        # An unparseable cap is unknown, not satisfied. Real notes often state
        # the limit in prose with no number ("we limit the number of
        # applications"), and treating that as "not reached" would quietly keep
        # sweeping a board that has already rejected an application on quota.
        # None means the user decides; it never silently means no.
        entry["cap_reached"] = (
            None if cap is None else entry["applications_logged"] >= cap
        )
        entry["rejected_on_cap"] = bool(
            re.search(r"rejected[^.]*cap|couldn.?t submit|could not submit",
                      (entry["evidence"] or "").lower())
        )

    summary = {
        "applications": len(rows),
        "companies": len(companies),
        "platforms": platforms.most_common(),
        "tracks": tracks.most_common(),
        "known_company_boards": sorted(boards),
        "titles": sorted(titles.values()),
        "company_names": sorted(companies.values()),
        "cooldown_candidates": cooldown,
        "retryable": retryable,
    }

    if args.targets:
        target_titles = set()
        for line in Path(args.targets).read_text(encoding="utf-8").splitlines():
            match = re.match(r"^titles:\s*(.*)$", line.strip())
            if match:
                target_titles.update(t.strip().lower() for t in match.group(1).split(","))
        # The delta is the point of mining: titles the user applied to but never
        # wrote down as a target are exactly what a search would otherwise miss.
        #
        # Match on whole words, not substrings. A bare `in` test lets a short
        # abbreviation swallow an unrelated title: "cto" sits inside
        # "Engineering Director", which hid a real leadership title from the
        # delta until an eval caught it. A missed delta entry is a query the
        # user never runs again.
        def covered(title: str) -> bool:
            words = re.findall(r"[a-z0-9]+", title.lower())
            for target in target_titles:
                target_words = re.findall(r"[a-z0-9]+", target)
                if not target_words:
                    continue
                # Contiguous run of the target's words inside the title.
                for i in range(len(words) - len(target_words) + 1):
                    if words[i:i + len(target_words)] == target_words:
                        return True
            return False

        summary["titles_not_in_targets"] = sorted(
            t for t in titles.values() if not covered(t)
        )

    print(json.dumps(summary, indent=2))
    return 0


def parse_boards(path: Path) -> list[dict]:
    """Parse profile/boards.md into a list of board definitions.

    Same hand-editable `## Board: <name>` plus `key: value` shape as the other
    profile files, so a user can add a board by hand without learning a format.
    """
    if not path.exists():
        return []
    boards: list[dict] = []
    current: dict | None = None
    key = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        heading = re.match(r"^##\s+Board:\s*(.+)$", line)
        if heading:
            current = {"name": heading.group(1).strip()}
            boards.append(current)
            key = None
            continue
        if current is None or not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+\S", line) and key:
            current[key] += " " + line.strip()
            continue
        match = re.match(r"^([a-z_][a-z0-9_]*)\s*:\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            current[key] = value
    for board in boards:
        for k, v in list(board.items()):
            if isinstance(v, str):
                board[k] = re.sub(r"\s+", " ", v).strip()
    return boards


def cmd_boards(args) -> int:
    """Read profile/boards.md, or add a company to a board, deterministically.

    Editing this file by hand during a fan-out run is how two agents clobber
    each other's discoveries, so every write goes through here and the
    orchestrator is the only caller.
    """
    path = Path(args.boards)
    boards = parse_boards(path)
    by_name = {b["name"]: b for b in boards}

    if args.add_board:
        name = args.add_board.strip()
        if name in by_name:
            die(f"board {name!r} already exists in {path}. Use --add-company to "
                f"add a slug to it, or edit the block by hand to change it.")
        if not args.api:
            die("--add-board needs --api, the endpoint the recipe calls", 2)
        if not args.fields:
            die("--add-board needs --fields, the source_key->column mapping. "
                "Without it a later sweep has to rediscover the payload shape", 2)

        block = [f"\n## Board: {name}",
                 f"kind: {args.kind_of or 'board'}",
                 f"tier: {args.tier_of or '1'}",
                 f"api: {args.api}"]
        if args.board_url:
            block.append(f"board_url: {args.board_url}")
        block.append(f"fields: {args.fields}")
        if args.posting_pattern:
            block.append(f"posting_pattern: {args.posting_pattern}")
        # Absent rather than empty when unverified: a `verified:` line with no
        # date reads as a field someone forgot to fill, while no line at all is
        # unambiguous. --verified-only keys on presence.
        if args.verified:
            block.append(f"verified: {args.verified}")
        if args.notes:
            block.append(f"notes: {args.notes}")
        block.append("companies:")

        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(block) + "\n")
        boards = parse_boards(path)
        by_name = {b["name"]: b for b in boards}

    if args.add_company:
        for entry in args.add_company:
            if ":" not in entry:
                die(f"--add-company expects <board>:<slug>, got {entry!r}", 2)
            name, company = entry.split(":", 1)
            name, company = name.strip(), company.strip()
            if name not in by_name:
                die(f"no board named {name!r} in {path}. Discover it first, or "
                    f"add a '## Board: {name}' block by hand.")
            board = by_name[name]
            known = [c.strip() for c in board.get("companies", "").split(",") if c.strip()]
            if company not in known:
                known.append(company)
                board["companies"] = ", ".join(sorted(known))

        # Rewrite only the companies lines, so hand-written comments and any key
        # this version does not know about survive untouched.
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        out, current = [], None
        for line in lines:
            heading = re.match(r"^##\s+Board:\s*(.+)$", line)
            if heading:
                current = heading.group(1).strip()
            if re.match(r"^companies\s*:", line) and current in by_name:
                out.append(f"companies: {by_name[current].get('companies', '')}")
                continue
            out.append(line)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    if args.kind:
        boards = [b for b in boards if b.get("kind") == args.kind]
    if args.tier:
        boards = [b for b in boards if b.get("tier") == args.tier]
    if args.verified_only:
        boards = [b for b in boards if b.get("verified")]

    if args.format == "json":
        print(json.dumps(boards, indent=2))
    else:
        for b in boards:
            companies = [c for c in b.get("companies", "").split(",") if c.strip()]
            print(f"{b['name']}\t{b.get('kind','?')}\ttier{b.get('tier','?')}\t"
                  f"{len(companies)} companies\t{'verified' if b.get('verified') else 'UNVERIFIED'}")
    return 0


def cmd_merge(args) -> int:
    """Concatenate per-agent shard files into one harvest, for `upsert`.

    Under an orchestrated sweep each agent writes its own shard rather than a
    shared file, because several agents writing one accumulated list means
    last-writer-wins and every other agent's rows vanish. This puts them back
    together in one place, so the orchestrator never hand-assembles JSON and the
    single-upsert rule stays easy to follow.

    Shards are read in sorted filename order so a merge is reproducible. That
    only decides which URL of a cross-post becomes canonical, since dedup itself
    is order-independent, but a reproducible merge makes a rerun comparable.
    """
    rows: list[dict] = []
    blocked: list[str] = []
    slugs: list[str] = []
    per_shard: list[dict] = []

    paths = sorted(Path(p) for p in args.shard)
    for path in paths:
        if not path.exists():
            die(f"shard not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            die(f"{path} is not valid JSON: {exc}", 2)

        # A shard is either a bare array of rows, or an object carrying the rows
        # alongside what the agent could not sweep. Accept both: the bare form
        # is what a tier-1 agent with nothing to report naturally produces.
        if isinstance(payload, list):
            shard_rows, shard_blocked, shard_slugs = payload, [], []
        elif isinstance(payload, dict):
            shard_rows = payload.get("rows", [])
            shard_blocked = payload.get("blocked", [])
            shard_slugs = payload.get("slugs", [])
        else:
            die(f"{path} must hold a JSON array or object", 2)

        if not isinstance(shard_rows, list):
            die(f"{path}: rows must be an array", 2)

        rows.extend(shard_rows)
        blocked.extend(shard_blocked)
        slugs.extend(shard_slugs)
        per_shard.append({
            "shard": str(path),
            "rows": len(shard_rows),
            "blocked": len(shard_blocked),
        })

    # Deduplicate the reported slugs and blocked lines, preserving order. Two
    # agents can legitimately discover the same board.
    blocked = list(dict.fromkeys(blocked))
    slugs = list(dict.fromkeys(slugs))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    summary = {
        "shards": len(paths),
        "rows": len(rows),
        "per_shard": per_shard,
        "blocked": blocked,
        "slugs": slugs,
        "out": args.out or None,
    }
    # An empty shard is not automatically wrong, but it is worth seeing: it is
    # what a broken selector and a genuinely quiet board look like alike.
    summary["empty_shards"] = [s["shard"] for s in per_shard if s["rows"] == 0]

    if args.rows_only:
        print(json.dumps(rows, indent=2))
    else:
        print(json.dumps(summary, indent=2))
    return 0


def cmd_upsert(args) -> int:
    """Merge one sweep's harvest into the pipeline.

    Takes the whole run as a single payload rather than a row at a time, because
    deduping within a run is impossible if the first source is written before
    the last one has been swept.
    """
    try:
        harvest = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        die(f"harvest on stdin is not valid JSON: {exc}", 2)
    if isinstance(harvest, dict) and isinstance(harvest.get("rows"), list):
        # search.md tells a sweep to checkpoint as {"rows": [...], "blocked":
        # [...]} so the blocked list survives a crash, then feed the partial to
        # upsert. Accept that shape rather than making every caller remember to
        # extract .rows first: refusing the format this skill documents is a
        # papercut that costs a run.
        harvest = harvest["rows"]
    if not isinstance(harvest, list):
        die("harvest must be a JSON array of job objects, or an object with a "
            "rows array", 2)

    pipeline_path = Path(args.pipeline)
    criteria = parse_criteria(Path(args.criteria)) if args.criteria else {}
    today = args.today or date.today().isoformat()

    # The cap is documented in profile/search.md, so read it from there when the
    # flag is absent. A config value the tool ignores unless the operator
    # retypes it is a trap: the file keeps claiming 60 while the run used
    # something else, and nothing shows the disagreement.
    max_new = args.max_new
    cap_source = "--max-new"
    if not max_new and criteria.get("max_new_rows_per_run", "").strip().isdigit():
        max_new = int(criteria["max_new_rows_per_run"])
        cap_source = "profile/search.md"

    existing = read_csv(pipeline_path)
    by_key = {r["job_key"]: r for r in existing if r.get("job_key")}

    # Axis 1: what has already been applied to.
    applied_by_key: dict[str, dict] = {}
    applied_by_url: dict[str, dict] = {}
    if args.log:
        for row in read_csv(Path(args.log)):
            company, role = row.get("company", ""), row.get("role", "")
            if not company or not role:
                continue
            record = {
                "date": row.get("date", ""),
                "status": (row.get("status") or "").strip().lower(),
                "notes": row.get("notes", ""),
            }
            applied_by_key[job_key(company, role)] = record
            if row.get("url"):
                applied_by_url[canonical_url(row["url"])] = record

    stats = Counter()
    ambiguous: list[dict] = []
    seen: dict[str, dict] = {}

    for job in harvest:
        company = (job.get("company") or "").strip()
        role = (job.get("role") or "").strip()
        url = (job.get("url") or "").strip()
        if not company or not role or not url:
            die(f"harvest row missing company, role, or url: {json.dumps(job)[:200]}", 2)

        key = job_key(company, role)

        # Axis 3: within this run.
        if key in seen:
            prior = seen[key]
            if canonical_url(prior["url"]) != canonical_url(url):
                note = f"also: {url}"
                if note not in prior["notes"]:
                    prior["notes"] = (prior["notes"] + "; " + note).strip("; ")
                stats["cross_post_merged"] += 1
            continue

        row = {
            "job_key": key,
            "first_seen": today,
            "last_seen": today,
            "company": company,
            "role": role,
            "url": url,
            "platform": (job.get("platform") or "other").strip(),
            "location": (job.get("location") or "").strip(),
            "work_mode": (job.get("work_mode") or "unknown").strip(),
            "track": "",
            "source": (job.get("source") or "").strip(),
            "status": "new",
            "applied_date": "",
            "run_id": args.run_id or "",
            "drop_reason": "",
            "notes": (job.get("notes") or "").strip(),
            "salary": (job.get("salary") or "").strip(),
            "published_date": (job.get("published_date") or "").strip(),
        }
        row["track"] = infer_track({**job, "role": role}, criteria)
        if row["track"] == "both":
            ambiguous.append({"company": company, "role": role})

        reason = blocker_for(row, criteria)
        if reason:
            row["status"] = "dropped"
            row["drop_reason"] = reason
            stats[f"dropped_{reason}"] += 1

        applied = applied_by_url.get(canonical_url(url)) or applied_by_key.get(key)
        if applied and applied["status"] in LOG_TERMINAL:
            # Having applied outranks any blocker: the row is a record of what
            # happened, and a drop_reason alongside it would claim the job was
            # filtered out when it was actually applied to.
            if row["drop_reason"]:
                stats[f"dropped_{row['drop_reason']}"] -= 1
                row["drop_reason"] = ""
            row["status"] = "applied"
            row["applied_date"] = applied["date"]
            stats["already_applied"] += 1
        elif applied:
            # A failed or incomplete application is worth another attempt, so it
            # stays actionable with the reason attached rather than looking done.
            row["notes"] = "; ".join(filter(None, [
                row["notes"], f"previous attempt {applied['status']}: {applied['notes']}"[:300]
            ]))
            stats["retryable"] += 1

        seen[key] = row

    # Axis 2: against previous runs.
    #
    # Take new rows round-robin across sources rather than in harvest order. The
    # cap is a pacing device, not an editorial one, and it should not decide
    # that the first board swept gets every slot and the rest get none. A real
    # run hit a cap of 100 with 170 rows outstanding and wrote 100 rows from one
    # board, which reads as "a representative 100" and was not.
    #
    # Rows already in the pipeline are handled first and uncapped, since bumping
    # last_seen costs nothing and skipping it would lose the observation.
    def interleaved(items: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
        by_source: dict[str, list[tuple[str, dict]]] = {}
        for key, row in items:
            by_source.setdefault(row.get("source", ""), []).append((key, row))
        out, queues = [], list(by_source.values())
        while queues:
            for queue in list(queues):
                out.append(queue.pop(0))
                if not queue:
                    queues.remove(queue)
        return out

    added = 0
    for key, row in interleaved(list(seen.items())):
        if key in by_key:
            current = by_key[key]
            current["last_seen"] = today
            if current.get("status") == "expired":
                # A reposted req is a real opportunity, so it becomes actionable
                # again rather than staying buried as expired.
                current["status"] = "new"
                current["notes"] = "; ".join(filter(None, [
                    current.get("notes", ""), f"reappeared {today}"]))
                stats["reappeared"] += 1
            else:
                stats["seen_again"] += 1
            continue
        if max_new and added >= max_new:
            stats["over_cap"] += 1
            continue
        by_key[key] = row
        added += 1
        stats["added"] += 1

    rows = sort_rows(list(by_key.values()))
    if not args.dry_run:
        write_pipeline(pipeline_path, rows)

    print(json.dumps({
        "run_id": args.run_id or "",
        "harvested": len(harvest),
        "added": stats["added"],
        "seen_again": stats["seen_again"],
        "reappeared": stats["reappeared"],
        "already_applied": stats["already_applied"],
        "retryable": stats["retryable"],
        "cross_post_merged": stats["cross_post_merged"],
        "over_cap": stats["over_cap"],
        "max_new": max_new or None,
        "max_new_from": cap_source if max_new else None,
        "dropped": {k.removeprefix("dropped_"): v
                    for k, v in stats.items() if k.startswith("dropped_")},
        "ambiguous_track": ambiguous,
        "pipeline_rows": len(rows),
        "dry_run": bool(args.dry_run),
    }, indent=2))
    return 0


def cmd_list(args) -> int:
    rows = sort_rows(read_csv(Path(args.pipeline)))
    if args.status:
        wanted = set(as_list(args.status))
        rows = [r for r in rows if r.get("status") in wanted]
    if args.track:
        rows = [r for r in rows if r.get("track") in {args.track, "both"}]
    if args.source:
        rows = [r for r in rows if r.get("source") == args.source]
    if args.limit:
        rows = rows[: args.limit]

    if args.format == "json":
        print(json.dumps(rows, indent=2))
    elif args.format == "url":
        for row in rows:
            print(row.get("url", ""))
    else:
        # Tab-separated so downstream shell never has to parse quoted CSV.
        writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
        writer.writerow(["job_key", "company", "role", "track", "source", "status", "url"])
        for row in rows:
            writer.writerow([row.get(k, "") for k in
                             ("job_key", "company", "role", "track", "source", "status", "url")])
    return 0


def cmd_set_status(args) -> int:
    path = Path(args.pipeline)
    rows = read_csv(path)
    if args.status not in STATUSES:
        die(f"unknown status {args.status!r}; expected one of {sorted(STATUSES)}", 2)

    target = None
    for row in rows:
        if row.get("job_key") == args.job_key:
            target = row
            break
    if target is None:
        die(f"no row with job_key {args.job_key!r}")

    current = target.get("status", "new")
    if current == args.status:
        print(json.dumps({"job_key": args.job_key, "status": current, "changed": False}))
        return 0
    if args.status not in TRANSITIONS.get(current, set()):
        die(f"refusing {current} -> {args.status} for {args.job_key}: "
            f"allowed from {current} are {sorted(TRANSITIONS.get(current, set())) or 'none'}")

    target["status"] = args.status
    if args.status == "applied" and not target.get("applied_date"):
        target["applied_date"] = args.today or date.today().isoformat()
    if args.note:
        target["notes"] = "; ".join(filter(None, [target.get("notes", ""), args.note]))

    write_pipeline(path, sort_rows(rows))
    print(json.dumps({"job_key": args.job_key, "status": args.status, "changed": True}))
    return 0


def cmd_reconcile(args) -> int:
    """Pull application state from the log into the pipeline.

    A pull rather than a push, so job-apply needs no knowledge of this file. It
    writes the log it already owns, and the pipeline catches up on the next read.
    """
    path = Path(args.pipeline)
    rows = read_csv(path)
    log_rows = read_csv(Path(args.log))

    by_key: dict[str, dict] = {}
    by_url: dict[str, dict] = {}
    for row in log_rows:
        company, role = row.get("company", ""), row.get("role", "")
        record = {
            "date": row.get("date", ""),
            "status": (row.get("status") or "").strip().lower(),
        }
        if company and role:
            by_key[job_key(company, role)] = record
        if row.get("url"):
            by_url[canonical_url(row["url"])] = record

    changed = []
    for row in rows:
        if row.get("status") in {"applied", "rejected"}:
            continue
        hit = by_url.get(canonical_url(row.get("url", ""))) or by_key.get(row.get("job_key", ""))
        if hit and hit["status"] in LOG_TERMINAL:
            row["status"] = "applied"
            row["applied_date"] = hit["date"]
            changed.append(row["job_key"])

    if changed and not args.dry_run:
        write_pipeline(path, sort_rows(rows))
    print(json.dumps({"reconciled": len(changed), "job_keys": changed,
                      "dry_run": bool(args.dry_run)}, indent=2))
    return 0


def cmd_report(args) -> int:
    rows = sort_rows(read_csv(Path(args.pipeline)))

    # A row this run touched, not only a row this run created. An expired
    # posting that reappears keeps the run_id of the sweep that first found it,
    # so selecting on run_id alone hides the most interesting row in the run:
    # a job that came back from the dead and is actionable again.
    if args.run_id:
        touched = args.today or date.today().isoformat()
        run_rows = [
            r for r in rows
            if r.get("run_id") == args.run_id or r.get("last_seen") == touched
        ]
    else:
        run_rows = rows

    # Only rows upsert actually revived. A row from an earlier run that was
    # simply seen again is not news and belongs in neither section, so key on
    # the note upsert writes rather than on "old run_id, status new".
    reappeared = [
        r for r in run_rows
        if r.get("run_id") != args.run_id
        and r.get("status") == "new"
        and "reappeared" in (r.get("notes") or "")
    ] if args.run_id else []

    by_status = Counter(r.get("status", "") for r in run_rows)
    by_source = Counter(r.get("source", "") for r in run_rows)
    by_drop = Counter(r.get("drop_reason", "") for r in run_rows if r.get("status") == "dropped")

    lines = [f"# Sweep {args.run_id or 'all'}", ""]
    lines.append(f"{len(run_rows)} rows, {len(rows)} in the pipeline overall.")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---|")
    for status, count in by_status.most_common():
        lines.append(f"| {status} | {count} |")
    lines.append("")
    lines.append("| Source | Count |")
    lines.append("|---|---|")
    for source, count in by_source.most_common():
        lines.append(f"| {source or 'unknown'} | {count} |")

    if by_drop:
        lines += ["", "## Dropped", "",
                  "Kept in the pipeline so a later sweep does not re-evaluate them.", "",
                  "| Reason | Count |", "|---|---|"]
        for reason, count in by_drop.most_common():
            lines.append(f"| {reason} | {count} |")

    judged = [r for r in run_rows if r.get("drop_reason") == "function-excluded"]
    if judged:
        # Named rather than counted, because unlike a location this encodes a
        # judgement that can be wrong: an "Applied AI Architect, Partnerships"
        # is an engineering role that a partnerships exclusion removes. The user
        # can only spot a bad call if the row is visible.
        lines += ["", "## Dropped as a different profession", "",
                  "These matched `query_terms_exclude`. Unlike the other "
                  "blockers this is a judgement, so they are named rather than "
                  "counted:", "",
                  "| Company | Role |", "|---|---|"]
        for row in judged:
            lines.append(f"| {row.get('company','')} | {row.get('role','')} |")

    if args.blocked:
        lines += ["", "## Sources blocked", "",
                  "A board that refused us. Not the same as a board with "
                  "nothing open, and it needs the user to act:", ""]
        for entry in args.blocked:
            lines.append(f"- {entry}")

    if args.not_swept:
        # A third state, because folding it into "blocked" tells the user to go
        # clear a challenge that never happened, and folding it into the source
        # counts tells them a board is dry when nobody looked.
        lines += ["", "## Sources not attempted", "",
                  "Neither blocked nor empty: nothing tried to sweep these, so "
                  "they are not evidence of anything:", ""]
        for entry in args.not_swept:
            lines.append(f"- {entry}")

    if reappeared:
        lines += ["", "## Reappeared", "",
                  "Postings that had expired and are live again. They kept the "
                  "run id of the sweep that first found them.", "",
                  "| Track | Company | Role | Source | URL |", "|---|---|---|---|---|"]
        for row in reappeared:
            lines.append(f"| {row.get('track','')} | {row.get('company','')} | "
                         f"{row.get('role','')} | {row.get('source','')} | {row.get('url','')} |")

    reappeared_keys = {r.get("job_key") for r in reappeared}
    new_rows = [r for r in run_rows
                if r.get("status") == "new"
                and r.get("job_key") not in reappeared_keys]
    if new_rows:
        lines += ["", "## New", "", "| Track | Company | Role | Source | URL |", "|---|---|---|---|---|"]
        for row in new_rows:
            lines.append(f"| {row.get('track','')} | {row.get('company','')} | "
                         f"{row.get('role','')} | {row.get('source','')} | {row.get('url','')} |")

    text = "\n".join(lines) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(text)
    return 0


def cmd_init(args) -> int:
    path = Path(args.pipeline)
    if path.exists() and path.stat().st_size > 0:
        print(json.dumps({"created": False, "reason": "already exists", "path": str(path)}))
        return 0
    write_pipeline(path, [])
    print(json.dumps({"created": True, "path": str(path)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pipeline.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("key", help="compute the identity key for one job")
    p.add_argument("--company", required=True)
    p.add_argument("--role", required=True)
    p.set_defaults(func=cmd_key)

    p = sub.add_parser("mine", help="summarise applications/log.csv for setup")
    p.add_argument("--log", required=True)
    p.add_argument("--targets", help="profile/targets.md, to report the title delta")
    p.set_defaults(func=cmd_mine)

    p = sub.add_parser("init", help="create an empty pipeline.csv with the header")
    p.add_argument("--pipeline", required=True)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("boards", help="read profile/boards.md, or add a company")
    p.add_argument("--boards", required=True)
    p.add_argument("--kind", choices=["search", "board"])
    p.add_argument("--tier", choices=["1", "2"])
    p.add_argument("--verified-only", action="store_true",
                   help="skip boards that have never returned a row")
    p.add_argument("--add-company", action="append",
                   help="<board>:<slug>, repeatable. Adds a company to a board "
                        "that already exists.")
    p.add_argument("--add-board", help="record a newly discovered board type")
    p.add_argument("--api", help="with --add-board: the endpoint")
    p.add_argument("--fields", help="with --add-board: source_key->column mapping")
    p.add_argument("--board-url", help="with --add-board: where a human sees it")
    p.add_argument("--posting-pattern",
                   help="with --add-board: regex recognising it in a posting URL")
    p.add_argument("--kind-of", choices=["search", "board"],
                   help="with --add-board, default board")
    p.add_argument("--tier-of", choices=["1", "2"],
                   help="with --add-board, default 1")
    p.add_argument("--verified",
                   help="with --add-board: what it returned and when. Omit when "
                        "the recipe has not actually returned a row")
    p.add_argument("--notes", help="with --add-board: quirks, and what was guessed")
    p.add_argument("--format", choices=["tsv", "json"], default="tsv")
    p.set_defaults(func=cmd_boards)

    p = sub.add_parser("merge", help="concatenate per-agent shard files")
    p.add_argument("--shard", action="append", required=True,
                   help="a shard file; repeat once per agent")
    p.add_argument("--out", help="write the merged rows here, for upsert to read")
    p.add_argument("--rows-only", action="store_true",
                   help="print the merged rows instead of the summary, to pipe "
                        "straight into upsert")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("upsert", help="merge a sweep harvest (JSON on stdin)")
    p.add_argument("--pipeline", required=True)
    p.add_argument("--log")
    p.add_argument("--criteria")
    p.add_argument("--run-id")
    p.add_argument("--max-new", type=int, default=0)
    p.add_argument("--today")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("list", help="read rows in a deterministic order")
    p.add_argument("--pipeline", required=True)
    p.add_argument("--status")
    p.add_argument("--track")
    p.add_argument("--source")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--format", choices=["tsv", "json", "url"], default="tsv")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("set-status", help="move one row through the lifecycle")
    p.add_argument("--pipeline", required=True)
    p.add_argument("--job-key", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--note")
    p.add_argument("--today")
    p.set_defaults(func=cmd_set_status)

    p = sub.add_parser("reconcile", help="pull applied state from the log")
    p.add_argument("--pipeline", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("report", help="render a run report")
    p.add_argument("--pipeline", required=True)
    p.add_argument("--run-id")
    p.add_argument("--today", help="override the date used to pick rows this run "
                                   "touched; for tests and fixtures")
    p.add_argument("--not-swept", action="append", default=[],
                   help="a source nothing attempted this run, and why; repeat "
                        "per source. Distinct from blocked and from empty.")
    p.add_argument("--blocked", action="append", default=[],
                   help="a source that could not be swept; repeat per source. "
                        "Repeatable rather than comma-separated because a "
                        "blocked message usually contains a URL and a comma.")
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
