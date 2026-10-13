---
name: cro-research
description: "Conversion rate optimization (CRO) research and A/B test analysis from GA4 CSV exports. Find which landing pages, devices, browsers, and traffic sources convert worse than the rest of the site, where a signup, checkout, or lead funnel loses people, whether there is enough traffic to run an A/B test, and whether a finished split test can be trusted. Use for CRO audits, landing page audits, low conversion rates, funnel drop-off and form abandonment analysis, sample size and test duration planning, statistical significance checks, and sample ratio mismatch (SRM) detection. Use before critiquing any page, including when someone shares a URL and asks for feedback. The Python helper flags where conversions are lost and withholds a test result when the visitor split is broken; it does not explain why people leave, connect to analytics accounts, or replace session recordings and user research."
metadata:
  last_verified: 2026-10-13
  requires: python3 (nothing to install, no logins, no API keys)
---

# Conversion research

Ask for help with a page that does not convert and you will be told to clarify
the value proposition, strengthen the call to action, add social proof and
reduce friction. You will be told that about any page, by anyone who has not
opened it. None of it is wrong. It is simply what advice looks like when nobody
looked.

People who do this for a living work the other way round. They find out where
the site loses people, then why, and only then propose a change. The list of
changes comes last and is different for every site, because it is made out of
what was found.

So this skill does not contain a checklist. It contains the looking.

## The order, and why it is the order

1. **Can you A/B test at all?** Most sites cannot, and it changes everything
   that follows. With enough traffic you propose tests. Without it you propose
   fixes and measure before and after. Find out first.
2. **Where are people lost?** Which pages, which devices, which step. The
   script answers this from exports.
3. **Why?** No export can say. Somebody has to watch, ask and try it.
4. **Only now, what to change.** Each recommendation tied to something that
   was seen.
5. **After a test, check the split before the result.** A test that sent
   uneven numbers of people to each version is broken, however good the result
   looks.

Do not skip to step 4. If steps 1 to 3 cannot be done, say which could not be
done and why. Do not fill the space with general advice.

## What you need

| File | Where to get it | What it answers |
|---|---|---|
| Pages, with visits and conversions | GA4 → Reports → the **Landing page** report → Share this report → Download File → Download CSV | Which pages convert worse than the rest? |
| The same numbers split by device, browser or traffic source | Any GA4 report that lists those next to sessions and key events, exported the same way | Is it broken for some people? Are the wrong people arriving? |
| The number of people reaching each step | Type them in. Any analytics tool will show them | Where in the journey do they leave? |
| Visitors and conversions for each version of a finished test | Your testing tool | Can the result be trusted? |

**Pick the conversion before you export.** GA4's "Key events" column adds up
every event marked as one, and a single visit can set off several. If the
report lets you choose one event, choose the one that is the actual sale or
sign-up. The script notices when conversions outnumber visits and tells you.

**Choose a date range made of whole weeks**, long enough to hold a few hundred
conversions. Weekdays and weekends behave differently, and a range that ends
on a Wednesday counts one kind more than the other.

## How to run it

```bash
# Which pages lose people, and is there enough traffic to test a fix?
python3 scripts/cro_research.py --pages landing-pages.csv

# The same question by device, browser or source. One file per split.
python3 scripts/cro_research.py --pages landing-pages.csv --segments devices.csv sources.csv

# Where in the journey do they leave?
python3 scripts/cro_research.py --funnel "Visited=12000; Started signup=1400; Paid=90"

# Enough traffic to test, when all you have is the totals
python3 scripts/cro_research.py --visitors 12000 --conversions 300 --days 30

# Read a finished test. Original first, each version as visitors/conversions.
python3 scripts/cro_research.py --test 10210/512 9987/561
python3 scripts/cro_research.py --test control:9000/450 new-page:1000/62 --split 90/10
```

A GA4 export says which dates it covers, and the script reads that. For any
other file, add `--days 30`.

If it picks the wrong column, name the right one:

```bash
python3 scripts/cro_research.py --pages export.csv \
  --visitors-col "Sessions" --conversions-col "Purchases"
```

It stops with an error if it cannot answer, and tells you which file to use
instead. It never guesses.

## What it does not mind

The comment lines GA4 puts above the table. Commas, semicolons or tabs between
the columns. Numbers written as 1,234. A totals row. The same page listed
several times with different tracking codes on the end, which it adds together
and tells you it did (`--keep-query` stops that).

## Reading the report

**1. Do you have enough traffic to A/B test?** One of three answers: yes, only
for big changes, or no. Then a table of how long a test would take to catch
improvements of different sizes. Believe it. A test too small to catch the
change you made does not come back saying "too small". It comes back saying
"no difference", and a good idea gets thrown away.

From a page export this is the best case, because it counts all the traffic in
the file. A test on one page only gets that page's visits. The next table
answers that page by page.

**2. Which pages or groups convert worse than the rest?** Every page or group
that converts reliably below everything else, with the number of conversions
that gap costs, and whether a fix could be tested on that page's own traffic.
Every row arrives saying **NEEDS AN ANSWER**.

Those rows are the work. A low number says where to look, never what is wrong.
For each row, establish which of these it is:

- it has a different job. An article is not meant to convert like a pricing
  page, so compare it with its own kind and say so. This is not a leak
- the wrong people are arriving, because an advert, a search result or a link
  promised something the page does not deliver
- it is broken for some people, on one device or one browser
- the page itself loses them: the offer is unclear, something is hard to do,
  or a worry goes unanswered
- it is not being counted, because people who start here convert somewhere the
  tracking does not follow

It also lists what converts reliably better than the rest. Study those before
changing anything. What works on this site, for these visitors, is better
evidence than what worked on someone else's.

**3. Where in the journey do people leave?** People at each step, the share
kept from the step before, and where to go and watch. The size of a drop does
not say which step to fix. Improving any step by a tenth gives a tenth more at
the end, whichever step it is, and early steps usually lose the most because
most visitors were never going to buy.

If more people reach a step than reached the one before it, the report stops
and says so. The steps are being counted differently and nothing in the table
means anything until that is fixed.

**4. Can you trust this test result?** The split is checked first. If the
visitors were not divided the way the test was set up, the report says STOP
and **does not show the result at all**, because a number that is on the page
gets quoted. Otherwise it gives one of four answers for each version: won,
lost, no difference you can rely on, or too few conversions to say.

"No difference you can rely on" comes with the smallest difference the test
could have caught. If that figure is large, the honest summary is "we could
not tell".

A win from a test that was too small comes with a warning not to quote the
size. Small tests only reach a clear result when the measured gap happens to
be flattering, so the direction is probably right and the number is probably
too big.

## Finding out why

This is the part the script cannot do and the part that produces the
recommendations. Match the method to the open question:

| Open question | How to find out |
|---|---|
| Is it broken for some people? | Open the page on the device and browser that converts worst. Complete the whole journey, slowly, as a stranger |
| What do people do before they leave? | Session recordings and scroll maps for the flagged page, filtered to visits that left. Keep watching until the same thing has gone wrong more than once |
| Why did they leave? | A one-question poll on the page: "What were you looking for today?" |
| What nearly stopped the people who did buy? | Ask them straight after: "What nearly stopped you?" Read sales calls and support tickets for the same thing |
| Can a newcomer use it at all? | Sit a handful of people who have never seen it in front of it, give them the task, and say nothing |
| Did the visit start with the wrong promise? | Read the advert, search result or email that sent them, next to the page they landed on |

If you are an agent with no way to see recordings, polls or customers, say so.
List exactly what the person needs to go and look at, row by row, and stop
there. A recording tool or a survey export the user can hand over is worth
asking for. Guessing at what the recordings would have shown is not research.

A read-through of the page by someone who knows the subject is allowed, and it
comes last. It is an opinion and has to be labelled as one.

## Rules for writing it up

- **Every recommendation names what was seen.** Mark each one **Measured**
  (from an export), **Watched** (recordings or people using it), **Told**
  (customers' own words) or **Opinion** (none of those).
- **Opinions go last**, however confident. Never present one as a finding.
- **Order by evidence and by conversions at stake.** There is no fixed order
  of importance that holds for every page.
- **Do not propose a test the traffic cannot support.** If section 1 said no,
  propose the fix and a before-and-after comparison over whole weeks. Write
  "happened at the same time as", not "caused", unless a test proved it.
- **Put the date range on every number.**
- **Compare a site with itself.** Another company's conversion rate tells you
  nothing about this page. The comparison here is always against the rest of
  the same site.
- **Never quote the size of a win the report warned about.**

## What it cannot do

It reads files you export. It does not log into anything, so it runs on any
computer with Python, including a client's.

It finds where, not why. Every reason in the finished report is one you
established.

It compares each page with the rest of the site, so on a site where everything
converts badly, nothing is flagged. The report says so when that happens.

The test readout assumes the test ran for a length fixed in advance and that
each visitor was counted once. If your testing tool uses a method built for
checking results as they come in, use the tool's own verdict for the result
and this for the split check, which holds either way. With an uneven split,
the "smallest difference it could have caught" figure is approximate.

## The bars it uses, and whose they are

Ours, chosen to be cautious, and all adjustable:

- **Enough traffic**: a four-week test must be able to catch a 10% improvement
  for "yes", 30% for "big changes only" (`--weeks`).
- **A page is testable** if a test on its own traffic would catch a 20%
  improvement within eight weeks (`--max-weeks`).
- **Rows under 200 visits are left out** as too small to judge
  (`--min-visitors`). The bar for flagging a row also rises with the number of
  rows, so a long list does not produce false alarms by sheer length.

Other people's:

- **The split check** stops a test when an imbalance that large would happen
  by luck less than one time in a thousand (`--split-alpha 0.001`), the bar
  [Eppo documents for the same check](https://docs.geteppo.com/statistics/sample-ratio-mismatch/).
  Lukas Vermeer's checker
  [used one in a hundred](https://www.lukasvermeer.nl/srm/docs/faq/).
- **95% confidence and 80% power** for sample sizes, the conventional
  settings, using the standard formula for comparing two rates
  ([sample-size calculations for A/B testing](https://arxiv.org/abs/2305.16459)).

## Where the rules came from

- [Diagnosing Sample Ratio Mismatch in Online Controlled Experiments](https://www.lukasvermeer.nl/publications/papers/2019/07/25/diagnosing-sample-ratio-mismatch-in-online-controlled-experiments.html)
  (Fabijan and others, KDD 2019), for why an uneven split invalidates a test
  and what usually causes one.
- [Conversion research](https://cxl.com/conversion-optimization/conversion-research/)
  from CXL, for the principle this is built on: gather the evidence first,
  then turn one list of found problems into actions.
- [Share and export reports](https://support.google.com/analytics/answer/9317657)
  in Google Analytics Help, for the export steps. A CSV export holds up to
  100,000 rows.

Checked on 13 October 2026. The arithmetic was checked against standard
statistical tables on the same day. Menu names in GA4 change often, so check the export
steps before sending them to a client.
