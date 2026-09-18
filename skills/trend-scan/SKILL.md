---
name: trend-scan
description: Analyze SEO traffic trends and diagnose organic search traffic drops from Google Search Console (GSC) CSV exports. Check monthly clicks, traffic growth or decline, month-over-month and year-over-year comparisons, ranking losses, declining pages and search queries, missing keywords, and single-page traffic concentration. Use for SEO audits, traffic decline analysis, search performance reviews, content decay investigations, and anomaly triage before writing an audit report. The Python helper flags changes for investigation; it does not prove their cause or connect directly to analytics accounts.
metadata:
  last_verified: 2026-09-04
  requires: python3 (nothing to install, no logins, no API keys)
---

# Trend scan

A total for the last twelve months can look perfectly healthy while five of
those months were a steady slide. The total hides the direction. That is how a
site quietly loses half its traffic while every report says it is fine.

So the first question is always: which way is it going? Not how much traffic
there is, but whether there is more or less of it than there was. A site that
is losing traffic needs a report that opens by saying so. Anything else is the
wrong report, however good the rest of it is.

## When to run it

First, before anything else. Before the other skills, before the outline,
before you start writing. What you find here changes what the whole report
should say and what order the recommendations go in.

## What you need

Two kinds of file, both of which anyone can export without a developer:

| File | Where to get it | What it answers |
|---|---|---|
| One row per date, with clicks | Search Console → Performance → Export → the **Dates** tab | Is traffic going up or down? |
| A list of pages or search terms | Search Console → Performance → the **Queries** or **Pages** tab → Export | How much rides on one page? |
| The same list, exported twice over two different date ranges | As above, changing the dates in between | What dropped? |

**Change the dates before you export.** Search Console shows you the last three
months by default, and GA4 shows the last seven days. If you export before
changing that, you get a small recent slice and miss the trend completely,
which is the exact thing this is meant to catch. Set the longest range you can
— Search Console keeps sixteen months — and write down the range you actually
used.

## Locate the helper files

Resolve `scripts/` and `references/` relative to the directory containing this
`SKILL.md`, not the project working directory. Use an absolute script path when
running from another folder, and keep input/output paths relative to the user
project or make them absolute. On Windows, use `python` if `python3` is unavailable.

## How to run it

```bash
# Is traffic going up or down?
python3 scripts/trend_scan.py --series Dates.csv

# How much rides on one page?
python3 scripts/trend_scan.py --recent Queries.csv

# What dropped? (two exports of the same table, different date ranges)
python3 scripts/trend_scan.py --prior Queries-last-year.csv --recent Queries-now.csv

# All four questions at once
python3 scripts/trend_scan.py --series Dates.csv --prior old.csv --recent new.csv
```

You can change where the bar sits:

```bash
python3 scripts/trend_scan.py --prior old.csv --recent new.csv \
  --click-drop 30 --position-drop 2 --one-page-limit 25 --min-clicks 10
```

`--min-clicks` keeps small wobbles out of the report. On a small site drop it
to 3, on a big one raise it to 50, or the table fills up with pages that went
from four clicks to two.

It stops with an error if it cannot answer, and tells you which file to use
instead. It never guesses.

## What it does not mind

Commas, semicolons or tabs between the columns. Column headings in any
capitalisation. Dates written as 2026-04-01, 01/04/2026 or April 2026. Numbers
written as 1,234. Percentages written as 4.78%. Daily rows, which it adds up
into months for you.

If it cannot find what it needs, it says which columns it did find and which
file to export instead. Do not edit the CSV to make it work — if it will not
read your file, you have almost certainly exported the wrong tab.

## Reading the report

**1. Is traffic going up or down?** A month-by-month table, then a plain
answer, then the most important line in the whole report: the flattering total
and the recent trend printed side by side. Use both numbers or neither.

**2. What dropped?** Everything that lost a big share of its clicks or slipped
a long way down the results, plus anything that vanished from the newer list
altogether. Every row arrives saying **NEEDS AN ANSWER**.

Those rows are the actual work. For each one, write down which of these it was:

- the page has not been touched in a long time and better pages have overtaken it
- a competitor published something newer — look at the dates on the pages now above you
- Google started showing an AI summary or a featured box that takes the click
- people still see it but stop clicking, which usually means the title or description
- something technical broke: blocked, redirected, or much slower

If you do not know, write "not known" and say what you would need in order to
find out. An honest "not known" is worth more than a confident guess, and a row
left saying NEEDS AN ANSWER means the job is not finished.

Before you blame anything, check what you changed and when. If a drop lines up
with a release, that is worth writing down — but say **"happened at the same
time as"**, not "caused by", unless you have actually proved it. Two things
happening in the same week is not proof that one caused the other.

**3. How much rides on one page?** If one page or one search term brings in
more than a quarter of the clicks, say so and add an action to spread the
traffic wider. A site living off one page is one Google update away from losing
most of its traffic overnight.

**4. What is Google telling you directly?** This one cannot be worked out from
a spreadsheet. Go through every message and recommendation in Search Console,
plus Manual Actions and Security Issues, and answer each one. A message you
have not read is an open question, not good news.

## Rules that matter when a client is reading

- **Never let a total stand in for a trend.** If you could not get the data,
  write "we could not check the trend, because —" and say what was missing.
  Staying quiet reads as good news.
- **The month-by-month view beats the snapshot.** A page can look like your
  best asset in the totals — lots of impressions, sitting around position five
  — and be dying in the monthly view: position three to seven, clicks
  collapsing. Believe the monthly view.
- **Put the exact date range on every number**, every time.
- **Do not add up per-page numbers and call it the site total.** Use the
  number Search Console itself shows for the range you are quoting. If you do
  work something out yourself, say so and show how.
- **The last day or two is always incomplete.** Search Console has not finished
  counting yet, so a "drop" right at the end of the chart is usually just that.
  Check before you panic.
- **Do not undo a change just because rankings fell within a week.** Undo it if
  a technical test failed or you crossed a limit you agreed in advance.
  Otherwise leave it, keep a note of what changed, and look again at two, four
  and eight weeks.

## What it cannot do

It reads files you export. It does not log into anything, so there is nothing
to set up and it runs on any computer with Python, including a client's.

It does no statistics, so on a small site treat small movements as noise and
raise `--min-clicks`.

And it finds things, it does not explain them. Every reason in the finished
report is one you established. None of them is one the tool worked out.

## Where the rules came from

- [How long Search Console keeps your data](https://support.google.com/webmasters/answer/7576553) — sixteen months
- [Known gaps and oddities in Search Console data](https://support.google.com/webmasters/answer/9679690)
- [Google Search status dashboard](https://status.search.google.com/) — check here before blaming yourself for a drop
- [Confirmed Google ranking updates](https://developers.google.com/search/updates/ranking) — check whether a drop lines up with one

Checked against Google's own pages on 4 September 2026. Check again before you
rely on any of it in something you send a client.
