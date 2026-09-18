#!/usr/bin/env python3
"""
claim_check.py -- find the things you wrote that might have gone out of date.

This does not tell you whether something is true. It finds the sentences whose
truth wears off, tells you whether anyone wrote down when they last checked,
and works out how long ago that was. Checking is your job. Building the list so
nothing gets missed is this script's job.

The problem it catches: something you wrote that was correct at the time, that
nobody dated, and that quietly stopped being correct. A price that changed. A
feature that got switched off. A limit that moved.

Usage:
  python3 claim_check.py FILE [FILE ...]
  python3 claim_check.py -r docs/                 look in a whole folder
  python3 claim_check.py -r . --max-age 90        stricter: flag after 3 months
  python3 claim_check.py FILE --json              output for another program

Exit codes: 0 nothing to check | 1 things to check | 2 something went wrong.
Uses only what comes with Python. No internet access, on purpose: a tool that
guessed at the truth would be the exact problem it is meant to catch.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime

# --- what kinds of sentence wear off -----------------------------------------
# Each entry is a name, a plain-English description used in the report, and the
# pattern that spots it.

PERISHABLE = [
    ("switch-offs", "mentions something being retired or switched off",
     r"\b(deprecat\w*|retired?|sunset|discontinued?|end[- ]of[- ]life"
     r"|no longer (?:supported?|available|works?|earns?)|removed support"
     r"|killed off|superseded)\b"),
    ("time words", "says \"currently\" or \"right now\"",
     r"\b(currently|at present|as it stands|right now|these days"
     r"|nowadays|as of (?:today|writing))\b"),
    ("version numbers", "names a version number",
     r"(?<![/=_-])\b(v\d+\.\d+(?:\.\d+)*|version \d+(?:\.\d+)*"
     r"|\d+\.\d+\.\d+|release \d+(?:\.\d+)*)\b"),
    ("prices", "quotes a price",
     r"(\$\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]* ?(?:usd|eur|gbp)\b"
     r"|\bfree tier\b|\b\d[\d,]*\s?(?:/|per )(?:seat|month|user|year))"),
    ("limits", "quotes a limit or an allowance",
     r"\b(rate limit|quota of \d+|max(?:imum)? of \d+"
     r"|token limit|context window of \d+)\b"),
    ("what search engines show", "says what a search engine will or will not show",
     r"\b(rich results?|rich snippets?|eligible for|eligibility"
     r"|supported types?|algorithm update|core update|ranking factors?)\b"),
    ("numbers", "quotes a number or a percentage",
     r"\b\d+(?:\.\d+)?\s?%|\b\d+(?:\.\d+)?x\b"
     r"|\b(?:increase[sd]?|boost|lift|decrease[sd]?|drop) of \d+"),
    ("named sources", "says where the information came from",
     r"\b(according to|research (?:shows?|found)|stud(?:y|ies) (?:show|found)"
     r"|reports? that|per [A-Z][a-z]+(?:'s)?|survey (?:of|by|found))\b"),
]

DESCRIPTIONS = {name: desc for name, desc, _ in PERISHABLE}

# These wear off fastest, so they go to the top of the list.
FAST_CHANGING = ("switch-offs", "version numbers", "prices", "limits",
                 "what search engines show")

# Product names that merely contain flagged words. "Rich Results Test" is the
# name of a Google tool, not a statement about what Google shows.
PRODUCT_NAMES = [
    "rich results test", "schema.org validator", "search console",
    "rich result test", "structured data testing tool",
    "core web vitals", "search central",
]

# A note saying when someone last checked. This is what we most want to find.
CHECKED_ON = [
    r"\blast[_ -]verified\s*[:=]?\s*(\d{4}-\d{2}-\d{2})",
    r"\bas of\s+(\d{4}-\d{2}-\d{2})",
    r"\bas of\s+([A-Z][a-z]+ \d{4})",
    r"\bas of\s+(\d{1,2} [A-Z][a-z]+ \d{4})",
    # "checked against Search Central on 4 September 2026" and the same
    # sentence written with an ISO date. Both forms are common; missing one of
    # them punishes exactly the people who did the work.
    r"\b(?:verified|checked|confirmed|accurate)\s+(?:on\s+|against .{0,60}?on\s+)?"
    r"(\d{1,2} [A-Z][a-z]+ \d{4})",
    r"\b(?:verified|checked|confirmed|accurate)\s+(?:on\s+|against .{0,60}?on\s+)?"
    r"(\d{4}-\d{2}-\d{2})",
    r"\((\d{4}-\d{2}-\d{2})\)",
]

# A date written into the sentence itself, as in "Google switched this off on
# 7 May 2026". That is not a note of when you checked, but it does mean a
# reader can go and check it, which is much better than nothing.
MONTHS = ("January|February|March|April|May|June|July|August|September"
          "|October|November|December")
DATE_IN_SENTENCE = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2} (?:%s) \d{4}\b" % MONTHS,
    r"\b(?:%s) \d{1,2},? \d{4}\b" % MONTHS,
    r"\b(?:%s) \d{4}\b" % MONTHS,
    r"\b(?:in|since|across|during|before|after|from) (?:19|20)\d{2}\b",
]

URL_RE = re.compile(r"https?://[^\s)>\]\"']+")
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
# Something has to actually be claimed. "Which rich results are possible?"
# claims nothing at all.
ASSERTION_RE = re.compile(
    r"\b(is|are|was|were|enables?|supports?|gives?|earns?|requires?"
    r"|includes?|lists?|provides?|allows?|means?|shows?|remains?|becomes?"
    r"|has|have|had|can|must|should|will|does|do|use|using|add|adds"
    r"|always|never)\b", re.IGNORECASE)

DATE_PARSE = ("%Y-%m-%d", "%B %Y", "%b %Y", "%d %B %Y", "%d %b %Y")
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".mdx", ".rst"}

# Standard project files whose dates and version numbers are not claims about
# the world.
SKIP_BASENAMES = ("license", "licence", "notice", "changelog", "contributing",
                  "code_of_conduct", "authors", "copying")


def parse_stamp(raw):
    for fmt in DATE_PARSE:
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def find_checked_on(text):
    """Find a note saying when someone last checked. Returns (date, as written)."""
    for pattern in CHECKED_ON:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            parsed = parse_stamp(m.group(1))
            if parsed:
                return parsed, m.group(1)
    return None, None


def has_date_in_sentence(text):
    """True if the sentence carries its own date, however it is phrased."""
    return any(re.search(p, text, re.IGNORECASE) for p in DATE_IN_SENTENCE)


def strip_product_names(line):
    """Blank out product names so they cannot trigger a match on their own."""
    out = line
    for name in PRODUCT_NAMES:
        out = re.sub(re.escape(name), " ", out, flags=re.IGNORECASE)
    return out


def is_boilerplate(path):
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return stem in SKIP_BASENAMES


# --- deciding how urgent each one is ----------------------------------------
# 3 = check these first, 2 = check these next, 1 = just needs a date.

def classify(checked_on, age_days, max_age, has_url, dated_in_text, kinds):
    fast = any(k in FAST_CHANGING for k in kinds)

    if checked_on is not None and age_days is not None and age_days > max_age:
        return 3, ("Last checked %s, which was %d days ago. Anything older than "
                   "%d days is worth looking at again."
                   % (checked_on.isoformat(), age_days, max_age))
    if checked_on is None and fast and not dated_in_text:
        return 3, ("This is the kind of fact that changes, and there is no note "
                   "of when anyone last checked it.")
    if checked_on is None and fast and dated_in_text:
        return 1, ("There is a date in the sentence, so a reader can go and "
                   "check it. Worth adding a note of when you last confirmed "
                   "it is still right.")
    if checked_on is None and "named sources" in kinds and not has_url:
        return 2, ("This says where the information came from but does not link "
                   "to it. Made-up sources look exactly like this.")
    if checked_on is None and "numbers" in kinds and not has_url:
        return 2, ("A number with no link to where it came from. Worth checking "
                   "it exists before it goes any further.")
    if checked_on is None and kinds and not dated_in_text:
        return 1, "A fact with no date on it."
    return 0, "Fine"


def scan_file(path, max_age, today):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
    except OSError as exc:
        sys.stderr.write("claim-check: could not open %s: %s\n" % (path, exc))
        return []

    # A "last checked" note near the top of a file covers everything in it.
    file_checked, file_checked_raw = find_checked_on("\n".join(lines[:20]))

    findings = []
    in_fence = False
    in_frontmatter = bool(lines) and lines[0].strip() == "---"
    for n, line in enumerate(lines, 1):
        if in_frontmatter:
            if n > 1 and line.strip() == "---":
                in_frontmatter = False
            continue                      # the settings block at the top
        if CODE_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue                      # example code is not a claim
        stripped = line.strip()
        if not stripped or stripped.startswith(("|---", "---", "===")):
            continue
        if HEADING_RE.match(line):
            continue                      # a heading names a topic, claims nothing
        if stripped.endswith("?"):
            continue                      # a question claims nothing

        searchable = strip_product_names(line)
        kinds = [name for name, _, pattern in PERISHABLE
                 if re.search(pattern, searchable, re.IGNORECASE)]
        if not kinds:
            continue
        # Weaker signs need something actually claimed on the same line, or
        # every passing mention becomes a finding.
        if not any(k in FAST_CHANGING for k in kinds):
            if not ASSERTION_RE.search(stripped):
                continue

        checked_on, checked_raw = find_checked_on(line)
        if checked_on is None and file_checked is not None:
            checked_on = file_checked
            checked_raw = file_checked_raw + " (from the top of the file)"

        age = (today - checked_on).days if checked_on else None
        has_url = bool(URL_RE.search(line))
        dated_in_text = has_date_in_sentence(line)

        urgency, reason = classify(checked_on, age, max_age, has_url,
                                   dated_in_text, kinds)
        if urgency == 0:
            continue

        findings.append({
            "file": path,
            "line": n,
            "urgency": urgency,
            "kinds": kinds,
            "last_checked": checked_on.isoformat() if checked_on else None,
            "last_checked_written_as": checked_raw,
            "days_since_checked": age,
            "has_link": has_url,
            "date_in_sentence": dated_in_text,
            "reason": reason,
            "text": stripped,
        })
    return findings


def collect_paths(inputs, recurse):
    paths = []
    for item in inputs:
        if os.path.isdir(item):
            if not recurse:
                sys.stderr.write("claim-check: %s is a folder. Add -r to look "
                                 "inside it.\n" % item)
                continue
            for root, dirs, files in os.walk(item):
                dirs[:] = [d for d in dirs
                           if d not in (".git", "node_modules", "__pycache__",
                                        ".venv", "dist", "build")]
                for f in sorted(files):
                    if (os.path.splitext(f)[1].lower() in TEXT_EXTENSIONS
                            and not is_boilerplate(f)):
                        paths.append(os.path.join(root, f))
        elif os.path.isfile(item):
            paths.append(item)
        else:
            sys.stderr.write("claim-check: cannot find %s\n" % item)
    return paths


URGENCY_HEADING = {
    3: "Check these first",
    2: "Check these next",
    1: "These just need a date",
}


def render(findings, paths, max_age, today):
    out = []
    out.append("## What might have gone out of date")
    out.append("")
    out.append("Checked %d file%s on %s. Anything last confirmed more than %d "
               "days ago is flagged."
               % (len(paths), "" if len(paths) == 1 else "s",
                  today.isoformat(), max_age))
    out.append("")

    if not findings:
        out.append("Nothing to look at. Everything that could go out of date "
                   "either has a date on it or a link to where it came from.")
        out.append("")
        return "\n".join(out)

    counts = {}
    for f in findings:
        counts[f["urgency"]] = counts.get(f["urgency"], 0) + 1
    out.append("**%d thing%s to look at** — %s"
               % (len(findings), "" if len(findings) == 1 else "s",
                  ", ".join("%d to %s" % (counts[u], URGENCY_HEADING[u].lower())
                            for u in sorted(counts, reverse=True))))
    out.append("")

    for urgency in (3, 2, 1):
        group = [f for f in findings if f["urgency"] == urgency]
        if not group:
            continue
        out.append("### %s (%d)" % (URGENCY_HEADING[urgency], len(group)))
        out.append("")
        for f in group:
            out.append("**`%s`, line %d** — %s" % (f["file"], f["line"], f["reason"]))
            out.append("")
            out.append("> %s" % shorten(f["text"], 300))
            out.append("")
            why = [DESCRIPTIONS[k] for k in f["kinds"]]
            bits = ["flagged because it " + " and ".join(why)]
            if f["last_checked"]:
                bits.append("last checked %s" % f["last_checked"])
            elif f["date_in_sentence"]:
                bits.append("has a date in the sentence")
            else:
                bits.append("no date")
            bits.append("has a link" if f["has_link"] else "no link")
            out.append("<sub>%s</sub>" % " · ".join(bits))
            out.append("")

    out.append("---")
    out.append("")
    out.append("### How to deal with these")
    out.append("")
    out.append("Work down the list. For each one, go and look at the original "
               "source — the company's own page, not somebody's blog post about "
               "it — and then do one of three things:")
    out.append("")
    out.append("1. **It is still right.** Add a short note saying so, like "
               "`(checked on %s)`. Next time, you will be able to see at a "
               "glance how old it is." % today.isoformat())
    out.append("2. **It has changed.** Fix it, and say what changed and when. A "
               "dated correction is far more useful than a silent edit.")
    out.append("3. **You cannot find the source at all.** Delete it. A source "
               "you cannot find is the most damaging kind, because it still "
               "reads as though you did your homework.")
    out.append("")
    out.append("Never fix one of these by putting today's date on something you "
               "did not actually go and check. That turns an honest gap into a "
               "false reassurance, and nobody reading it later can tell.")
    out.append("")
    return "\n".join(out)


def shorten(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:n - 1] + "…"


def _force_utf8_output():
    """Windows terminals default to an old encoding that cannot print arrows."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    _force_utf8_output()
    p = argparse.ArgumentParser(
        description="Find the things you wrote that might have gone out of date.")
    p.add_argument("paths", nargs="+", help="files or folders to look at")
    p.add_argument("-r", "--recurse", action="store_true",
                   help="look inside folders (.md, .txt, .mdx, .rst)")
    p.add_argument("--max-age", type=int, default=180, metavar="DAYS",
                   help="how old a checked-on note can be before it is flagged "
                        "again (default 180 days)")
    p.add_argument("--json", action="store_true",
                   help="output for another program instead of for reading")
    p.add_argument("--min-urgency", "--min-severity", type=int, default=1,
                   choices=(1, 2, 3), dest="min_urgency",
                   help="1 shows everything, 2 hides the ones that only need a "
                        "date, 3 shows only the most urgent (default 1)")
    p.add_argument("--ignore", "--exclude", default="", metavar="KINDS",
                   dest="ignore",
                   help="kinds to leave out, separated by commas. Use "
                        "'prices' on writing full of worked examples, where "
                        "made-up figures are illustrations rather than claims. "
                        "Kinds: %s" % ", ".join(n for n, _, _ in PERISHABLE))
    args = p.parse_args()

    ignored = {k.strip().lower() for k in args.ignore.split(",") if k.strip()}
    known = {n for n, _, _ in PERISHABLE}
    unknown = ignored - known
    if unknown:
        sys.stderr.write("claim-check: don't know the kind %s. Choose from: %s\n"
                         % (", ".join(sorted(unknown)), ", ".join(sorted(known))))
        sys.exit(2)

    today = date.today()
    paths = collect_paths(args.paths, args.recurse)
    if not paths:
        sys.stderr.write("claim-check: nothing to look at\n")
        sys.exit(2)

    findings = []
    for path in paths:
        findings.extend(scan_file(path, args.max_age, today))
    if ignored:
        # Only drop a finding if every reason it was flagged is being ignored.
        findings = [f for f in findings
                    if {k.lower() for k in f["kinds"]} - ignored]
    findings = [f for f in findings if f["urgency"] >= args.min_urgency]
    findings.sort(key=lambda f: (-f["urgency"], f["file"], f["line"]))

    if args.json:
        print(json.dumps({"generated": today.isoformat(),
                          "files_checked": len(paths),
                          "max_age_days": args.max_age,
                          "findings": findings}, indent=2))
    else:
        print(render(findings, paths, args.max_age, today))

    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
