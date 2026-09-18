---
name: claim-check
description: Find stale claims, outdated statistics, undated pricing, obsolete software versions, changed product limits, deprecated features, and unsupported search-engine claims in Markdown and text. Use for fact-checking workflows, source verification, content freshness audits, SEO report QA, research review, citation checks, and pre-publication editorial checks. The Python helper flags time-sensitive statements and missing or old verification dates; the agent then checks primary sources and records evidence. A clean scan is not proof of accuracy, and the script does not browse the web or determine whether claims are true.
metadata:
  last_verified: 2026-09-04
  requires: python3 (nothing to install, no logins, no API keys)
---

# Claim check

The dangerous sentence is not the one that was always wrong. Somebody would
have caught that. The dangerous one is the sentence that was right when you
wrote it, that nobody put a date on, and that quietly stopped being right while
it sat there looking authoritative.

Nobody re-reads their own work to ask "is this still true". Files get tidied,
reformatted, renamed and moved, and the sentence rides along untouched, picking
up credibility every year nobody challenges it.

So this does not try to tell you what is true. It finds the sentences whose
truth wears off, tells you whether anyone wrote down when they last checked,
and works out how long ago that was. Checking is your job, against the real
source. Making the list so nothing gets missed is the script's job.

## Two halves, split on purpose

**The script** finds the sentences, spots the dates, works out what is old, and
puts the list in order. Run it twice on the same file and you get the same
answer.

**You** go and check them, and write down when you did.

The script has no internet access, deliberately. A tool that guessed at what
was true would be the exact problem it exists to catch.

## Locate the helper files

Resolve `scripts/` and `references/` relative to the directory containing this
`SKILL.md`, not the project working directory. Use an absolute script path when
running from another folder, and keep input/output paths relative to the user
project or make them absolute. On Windows, use `python` if `python3` is unavailable.

## How to run it

```bash
# One file
python3 scripts/claim_check.py README.md

# A whole folder
python3 scripts/claim_check.py -r docs/

# Stricter: anything not confirmed in the last three months
python3 scripts/claim_check.py -r docs/ --max-age 90

# Only the most urgent
python3 scripts/claim_check.py -r . --min-urgency 3

# On writing full of worked examples, where the money is made up
python3 scripts/claim_check.py -r . --ignore prices
```

## The three groups

**Check these first.** Something that changes often, with no note of when
anyone last looked: a price, a limit, a version number, a feature being
switched off, or a claim about what a search engine will show. These are the
ones that put something false in front of a client.

**Check these next.** A number or a named source with no link. This is exactly
what a made-up source looks like: "According to [plausible organisation]'s
[plausible year] report, [confident number]." It reads as though you did your
homework, which is why it survives being read.

**These just need a date.** Probably fine today. Put a date on them so that
next time, anyone can see at a glance how old they are.

## What to do with each one

Go and look at the original source — the company's own page, not somebody's
blog post about it — then do one of three things:

1. **It is still right.** Add a short note: `(checked on 2026-09-04)`. Now
   anyone can see how old it is without re-reading the whole thing.
2. **It has changed.** Fix it, and say what changed and when. A dated
   correction is far more useful than a silent edit, because the next reader
   can tell the difference.
3. **You cannot find the source at all.** Delete it. A source you cannot find
   is the most damaging kind, because it still reads as though you did the
   work.

**Never put today's date on something you did not actually go and check.** That
turns an honest gap into a false reassurance, and nobody reading it later —
including you in six months — has any way to tell the difference.

## What counts as a date

Any of these, in the sentence itself or near the top of the file:

```
last_verified: 2026-09-04
as of 2026-09-04          as of September 2026        as of 4 September 2026
verified on 2026-09-04    checked 4 September 2026    (2026-09-04)
```

A date near the top of a file covers everything in that file. For a reference
document that is the cheapest fix there is: one line at the top, updated
whenever you genuinely re-read it.

A sentence can also carry its own date, as in "Google switched this off on
7 May 2026". That is not the same as a note saying when you checked, but it
does mean a reader can go and verify it, so those drop to the bottom of the
list rather than the top.

## What it leaves alone

Example code, the settings block at the top of a file, headings, questions, and
standard project files like LICENSE and CHANGELOG. A code sample is not a
claim, a heading names a subject without claiming anything about it, and a
question claims nothing at all.

It also knows that "Rich Results Test" and "Search Console" are the names of
tools rather than statements about what Google shows.

It is deliberately cautious about what it flags. A checker that flags
everything gets switched off within a week, and a checker people ignore is
worse than none at all, because it makes the file look as though someone
checked it.

## What it cannot do — read this before trusting a clean run

**A clean run is not a certificate.** It means nothing tripped a pattern. It
does not mean the document is right.

**A plain list of names is invisible to it.** A table row reading
`| FAQPage | FAQ content | mainEntity |` does not claim anything in a way a
computer can read, so it will not be flagged. What does get flagged is the
sentence nearby that frames it — "enables rich results in search" — and going
to check *that* is what takes you to the table. Finding wrong values inside a
list needs someone who knows the subject.

**It reads one line at a time.** If your number is on one line and the link to
its source is three lines below, it will look unsourced.

**Age is a rough guide, not an answer.** A claim about something stable can be
two hundred days old and perfectly fine. A claim about pricing can be thirty
days old and already wrong. Set `--max-age` to suit what you are checking, and
set it low for anything a company can change whenever it likes.

## When to run it

- On any draft, before it goes out.
- On someone else's skill files, before you trust them on client work. An
  installed skill is unversioned writing by someone who is not maintaining it
  for you.
- Every few months on your own reference material, with `--max-age 90`.

## Where this came from

Most of this is method rather than fact, but the claims it does make are
sourced:

- The problem, measured: across 130 skill files in five published collections,
  not one put a date on a factual claim, and two contained statements that were
  already wrong when they were written —
  [Advice Is Not a Skill](https://claude.ai/code/artifact/79095478-5de7-44ce-9c69-682a678e4461)
  and the [Marketing Skills Tier List](https://claude.ai/code/artifact/ef3990d6-21a1-46de-91b4-936304253417).
- The example it was built against: Google stopped showing HowTo results in
  September 2023 and stopped showing FAQ results for every site on 7 May 2026,
  per [Google's own list of what it shows](https://developers.google.com/search/docs/appearance/structured-data/search-gallery).
  A skill installed millions of times still listed both as live.
- [Google's rules for structured data](https://developers.google.com/search/docs/appearance/structured-data/sd-policies),
  for checking anything this flags about search results.

Checked on 4 September 2026. Every subject has its own words for things
that wear off, so look over the list of what this catches before you trust a
clean run on your own writing.
