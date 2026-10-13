#!/usr/bin/env python3
"""
cro_research.py -- find where a site loses people before anyone suggests a fix.

A list of best practices is not an analysis. This reads the numbers you can
export without a developer and answers four questions, in the order they have
to be asked:

  1. Do you have enough traffic to A/B test at all?
  2. Which pages or groups of visitors convert worse than the rest?
  3. Where in the journey do people leave?
  4. Can a finished test result be trusted?

Usage:
  # Which pages lose people, and could you test a fix? (GA4 Landing page export)
  python3 cro_research.py --pages landing-pages.csv

  # The same question by device, browser or traffic source:
  python3 cro_research.py --segments devices.csv sources.csv

  # Where in the journey do they leave?
  python3 cro_research.py --funnel "Visited=12000; Started signup=1400; Paid=90"

  # Enough traffic to test? (when you only have the totals)
  python3 cro_research.py --visitors 12000 --conversions 300 --days 30

  # Read a finished test. Control first, each one as visitors/conversions:
  python3 cro_research.py --test 10210/512 9987/561

Exit codes: 0 nothing flagged | 1 findings to diagnose | 2 bad input.
Stdlib only. No network, no auth, no API keys.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import OrderedDict
from datetime import date, datetime
from statistics import NormalDist

NORMAL = NormalDist()

# --- column detection -------------------------------------------------------
# Listed in order of preference: when an export has both Sessions and Users,
# Sessions is the one a conversion rate is normally quoted against.

VISITOR_ALIASES = ("sessions", "total users", "active users", "users",
                   "visitors", "unique visitors", "visits", "views", "clicks")

CONVERSION_ALIASES = ("key events", "conversions", "transactions",
                      "ecommerce purchases", "purchases", "orders",
                      "goal completions", "completions", "sign-ups", "signups",
                      "sign ups", "leads", "trials", "demos", "submissions",
                      "bookings")

# "Engaged sessions", "Session key event rate" and "Views per session" all
# contain a word above and are none of them the count we are after.
NOT_A_COUNT = ("rate", "per ", "average", "avg", "new ", "engaged",
               "returning", "revenue", "value", "%", "time", "duration", "cost")

TOTAL_ROWS = ("total", "totals", "grand total", "sum", "all")


def die(msg):
    sys.stderr.write("cro-research: %s\n" % msg)
    sys.exit(2)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def to_num(value):
    """'1,234' -> 1234.0 ; '3.5%' -> 3.5 ; '' -> None. Never raises."""
    if value is None:
        return None
    s = str(value).strip().replace(" ", "").replace(",", "").replace("_", "")
    s = s.replace("%", "").replace("$", "")
    if not s or s in ("-", "--", "n/a", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def lead_num(value):
    """'1,234 (100%)' -> 1234.0. For funnel exports that decorate the count."""
    m = re.match(r"^\s*([\d][\d,_]*(?:\.\d+)?)", str(value or ""))
    return to_num(m.group(1)) if m else None


def find_col(header, aliases, override, what):
    """Index of the column holding `what`, or None."""
    normed = [norm(h) for h in header]
    if override:
        want = norm(override)
        for idx, h in enumerate(normed):
            if h == want:
                return idx
        die("there is no column called \"%s\".\n\n  The columns in that file "
            "are: %s." % (override, ", ".join(h for h in header if h.strip())))
    for alias in aliases:
        for idx, h in enumerate(normed):
            if h == alias:
                return idx
    for alias in aliases:
        for idx, h in enumerate(normed):
            if alias in h and not any(bad in h for bad in NOT_A_COUNT):
                return idx
    return None


# --- reading exports --------------------------------------------------------

def read_text(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        die("cannot read %s: %s" % (path, exc))
    # GA4 writes UTF-8. A file opened and re-saved in Excel may be anything.
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    die("cannot make sense of the text in %s" % path)


def read_blocks(path):
    """Return (days_covered, [tables]). Each table is a list of rows.

    GA4 exports open with '#' comment lines carrying the date range, and can
    hold more than one table separated by blank lines. Search Console and
    spreadsheet exports are a single table. Both come out the same here.
    """
    text = read_text(path)
    start = re.search(r"#\s*start date:\s*(\d{8})", text, re.I)
    end = re.search(r"#\s*end date:\s*(\d{8})", text, re.I)
    days = None
    if start and end:
        try:
            a = datetime.strptime(start.group(1), "%Y%m%d")
            b = datetime.strptime(end.group(1), "%Y%m%d")
            days = (b - a).days + 1
        except ValueError:
            days = None

    chunks, current = [], []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            if current:
                chunks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        chunks.append(current)

    tables = []
    for chunk in chunks:
        sample = "\n".join(chunk[:20])
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [r for r in csv.reader(chunk, dialect) if any(c.strip() for c in r)]
        if len(rows) >= 2:
            tables.append(rows)
    if not tables:
        die("%s has no data rows" % path)
    return days, tables


def load_breakdown(path, args, merge_urls):
    """Rows of {item, visitors, conversions} from a page or segment export."""
    days, tables = read_blocks(path)
    chosen = None
    for rows in sorted(tables, key=len, reverse=True):
        v = find_col(rows[0], VISITOR_ALIASES, args.visitors_col, "visitors")
        c = find_col(rows[0], CONVERSION_ALIASES, args.conversions_col,
                     "conversions")
        if v is not None and c is not None and v != c:
            chosen = (rows, v, c)
            break
    if not chosen:
        header = max(tables, key=len)[0]
        die("%s is missing something this needs.\n\n"
            "  Looking for a column of visits (Sessions, Users) and a column "
            "of conversions\n"
            "  (Key events, Conversions, Purchases, Leads). Found these "
            "columns: %s.\n\n"
            "  If the right columns are there under other names, point at "
            "them:\n"
            "      --visitors-col \"NAME\" --conversions-col \"NAME\"\n\n"
            "  In GA4 the Landing page report has both. Reports -> Share this "
            "report ->\n"
            "  Download File -> Download CSV."
            % (path, ", ".join(h for h in header if h.strip())
               or "nothing it recognised"))
    rows, v_idx, c_idx = chosen
    d_idx = next((i for i in range(len(rows[0])) if i not in (v_idx, c_idx)), None)
    if d_idx is None:
        die("%s has no column naming the pages or groups." % path)

    merged = OrderedDict()
    seen = 0
    for row in rows[1:]:
        if max(v_idx, c_idx, d_idx) >= len(row):
            continue
        key = (row[d_idx] or "").strip()
        if not key or norm(key) in TOTAL_ROWS:
            continue
        visitors = to_num(row[v_idx])
        if not visitors or visitors <= 0:
            continue
        seen += 1
        if merge_urls:
            # /pricing and /pricing?ref=x are one page that GA4 lists twice.
            key = re.split(r"[?#]", key, maxsplit=1)[0] or "/"
        rec = merged.setdefault(key, {"item": key, "visitors": 0.0,
                                      "conversions": 0.0})
        rec["visitors"] += visitors
        rec["conversions"] += to_num(row[c_idx]) or 0.0
    if not merged:
        die("%s has no rows with any visits in them" % path)
    return {
        "path": path,
        "days": days,
        "rows": list(merged.values()),
        "merged": seen - len(merged),
        "visitors_col": rows[0][v_idx].strip(),
        "conversions_col": rows[0][c_idx].strip(),
        "dimension_col": rows[0][d_idx].strip(),
    }


def load_funnel(spec):
    """Steps as [(name, people)] from a file, or from 'Name=123; Name=45'."""
    steps = OrderedDict()
    if os.path.exists(spec):
        _, tables = read_blocks(spec)
        rows = max(tables, key=len)
        width = max(len(r) for r in rows)
        body = rows[1:]

        def numeric_share(idx):
            cells = [r[idx] for r in body if idx < len(r) and r[idx].strip()]
            if not cells:
                return 0.0
            return sum(1 for c in cells if lead_num(c) is not None) / len(cells)

        count_idx = next((i for i in range(width) if numeric_share(i) >= 0.8), None)
        name_idx = next((i for i in range(width) if numeric_share(i) < 0.5
                         and any(i < len(r) and r[i].strip() for r in body)), None)
        if count_idx is None or name_idx is None:
            die("%s does not look like a list of steps.\n\n"
                "  It needs one column naming each step and one giving the "
                "number of people who\n"
                "  reached it. If that is awkward to export, type the numbers "
                "in instead:\n\n"
                "      --funnel \"Visited=12000; Started signup=1400; Paid=90\""
                % spec)
        for r in body:
            if max(count_idx, name_idx) >= len(r):
                continue
            name, n = r[name_idx].strip(), lead_num(r[count_idx])
            if name and n is not None and norm(name) not in TOTAL_ROWS:
                # The same step once per device or segment: add them up.
                steps[name] = steps.get(name, 0.0) + n
    else:
        for part in re.split(r"[;,]", spec):
            if not part.strip():
                continue
            if "=" not in part:
                die("cannot read the step \"%s\".\n\n"
                    "  Write each step as Name=number, in order, with no "
                    "commas inside the numbers:\n\n"
                    "      --funnel \"Visited=12000; Started signup=1400; "
                    "Paid=90\"\n\n"
                    "  If you meant a file, it was not found at that path."
                    % part.strip())
            name, _, value = part.rpartition("=")
            n = to_num(value)
            if n is None or not name.strip():
                die("cannot read the step \"%s\" -- it needs a name and a "
                    "number." % part.strip())
            steps[name.strip()] = n
    if len(steps) < 2:
        die("a journey needs at least two steps; found %d." % len(steps))
    return list(steps.items())


# --- arithmetic -------------------------------------------------------------

def chi2_sf(x, df):
    """Chance of a chi-squared value this large or larger, by pure luck."""
    if x <= 0:
        return 1.0
    a, x = df / 2.0, x / 2.0
    scale = math.exp(-x + a * math.log(x) - math.lgamma(a))
    if x < a + 1.0:
        term = total = 1.0 / a
        n = a
        for _ in range(2000):
            n += 1.0
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * scale)
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h * scale


def two_rate_p(n1, c1, n2, c2):
    """Two-sided chance that two conversion rates differ this much by luck."""
    if n1 <= 0 or n2 <= 0:
        return None
    pooled = (c1 + c2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1.0 / n1 + 1.0 / n2)) if 0 < pooled < 1 else 0
    if se == 0:
        return None
    z = (c1 / n1 - c2 / n2) / se
    return 2 * (1 - NORMAL.cdf(abs(z)))


def required_n(base, lift, alpha, power):
    """People needed in EACH version to catch a relative `lift` on `base`."""
    target = base * (1.0 + lift)
    if not (0 < base < 1) or not (0 < target < 1) or lift == 0:
        return None
    za = NORMAL.inv_cdf(1 - alpha / 2)
    zb = NORMAL.inv_cdf(power)
    mid = (base + target) / 2
    top = (za * math.sqrt(2 * mid * (1 - mid))
           + zb * math.sqrt(base * (1 - base) + target * (1 - target)))
    return int(math.ceil(top * top / (target - base) ** 2))


def smallest_detectable(base, per_version, alpha, power):
    """Smallest relative lift a test of this size reliably catches, or None."""
    if per_version < 2 or not (0 < base < 1):
        return None
    hi = min(10.0, (1 - base) / base * 0.999)
    need = required_n(base, hi, alpha, power)
    if need is None or need > per_version:
        return None
    lo = 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        need = required_n(base, mid, alpha, power)
        if need is not None and need <= per_version:
            hi = mid
        else:
            lo = mid
    return hi


# --- 1. enough traffic to test? ---------------------------------------------

def analyse_gate(visitors, conversions, days, source, args, counts_events=False):
    if counts_events:
        return {"status": "insufficient",
                "detail": "some rows show more conversions than visits, so "
                          "the export is counting events rather than people "
                          "and no rate worked out from it can be trusted. "
                          "Export again with the one event that is the actual "
                          "conversion."}
    if not days:
        return {"status": "insufficient",
                "detail": "the export does not say how many days it covers. "
                          "Add `--days N` and run it again."}
    if conversions <= 0:
        return {"status": "insufficient",
                "detail": "there are no conversions in these numbers at all. "
                          "That is a tracking question before it is a "
                          "conversion question: confirm a real conversion gets "
                          "counted, then come back."}
    base = conversions / visitors
    if base >= 1:
        return {"status": "insufficient",
                "detail": "there are more conversions than visits, so the "
                          "export is counting events rather than people. "
                          "Export again with the one event that is the actual "
                          "conversion."}
    weekly = visitors / days * 7.0
    per_version = int(weekly * args.weeks / 2)
    mde = smallest_detectable(base, per_version, args.alpha, args.power)
    ladder = []
    for lift in (0.05, 0.10, 0.20, 0.50):
        n = required_n(base, lift, args.alpha, args.power)
        ladder.append({"lift_pct": lift * 100, "per_version": n,
                       "weeks": int(math.ceil(2 * n / weekly)) if n else None})
    if mde is not None and mde <= 0.10:
        verdict = "TEST"
    elif mde is not None and mde <= 0.30:
        verdict = "BIG CHANGES ONLY"
    else:
        verdict = "DO NOT TEST"
    return {
        "status": "ok", "source": source, "days": days,
        "visitors": visitors, "conversions": conversions,
        "weekly_visitors": round(weekly, 1),
        "baseline_pct": round(base * 100, 3),
        "weeks": args.weeks, "per_version": per_version,
        "smallest_detectable_pct": round(mde * 100, 1) if mde is not None else None,
        "ladder": ladder, "verdict": verdict,
    }


# --- 2. which pages or groups convert worse than the rest? ------------------

def analyse_leaks(table, days, args):
    rows = table["rows"]
    total_v = sum(r["visitors"] for r in rows)
    total_c = sum(r["conversions"] for r in rows)
    out = {"path": table["path"], "label": table["dimension_col"],
           "visitors_col": table["visitors_col"],
           "conversions_col": table["conversions_col"],
           "merged": table["merged"], "rows": len(rows),
           "visitors": total_v, "conversions": total_c}
    if total_c <= 0:
        out.update(status="insufficient",
                   detail="no conversions anywhere in %s. Nothing can be "
                          "compared until a conversion is being counted."
                          % table["path"])
        return out

    # GA4's "Key events" counts events, and one visit can fire several.
    events = [r for r in rows if r["conversions"] > r["visitors"]]
    out["counts_events"] = len(events)

    judged = [r for r in rows if r["visitors"] >= args.min_visitors]
    out["too_small"] = len(rows) - len(judged)
    if len(judged) < 2:
        out.update(status="insufficient",
                   detail="fewer than two rows have %d or more visits, so "
                          "there is nothing to compare. Export a longer date "
                          "range, or lower `--min-visitors`."
                          % args.min_visitors)
        return out

    # Many rows means many chances for one to look bad by luck, so the bar
    # rises with the number of rows judged.
    bar = 0.05 / len(judged)
    weak, strong = [], []
    for r in judged:
        n, c = r["visitors"], min(r["conversions"], r["visitors"])
        rest_n = total_v - n
        rest_c = min(total_c - r["conversions"], rest_n)
        if rest_n <= 0:
            continue
        rate, rest_rate = c / n, rest_c / rest_n
        p = two_rate_p(n, c, rest_n, rest_c)
        if p is None or p >= bar:
            continue
        rec = {"item": r["item"], "visitors": n,
               "conversions": r["conversions"],
               "rate_pct": round(rate * 100, 2),
               "rest_rate_pct": round(rest_rate * 100, 2)}
        if rate < rest_rate:
            rec["missed"] = round(n * (rest_rate - rate), 1)
            rec["testable"] = testable(n, rate, days, args)
            rec["diagnosis"] = None   # the agent must fill this in
            weak.append(rec)
        else:
            strong.append(rec)
    weak.sort(key=lambda r: r["missed"], reverse=True)
    strong.sort(key=lambda r: r["visitors"], reverse=True)
    out.update(status="ok", weak=weak[:args.top], more=max(0, len(weak) - args.top),
               strong=strong[:3], judged=len(judged))
    return out


def testable(visitors, rate, days, args):
    """Could a fix to this one row be A/B tested on its own traffic?"""
    if rate <= 0:
        return "nothing converts here -- check it is being counted"
    if not days:
        return "not known (add --days)"
    need = required_n(rate, 0.20, args.alpha, args.power)
    if need is None:
        return "--"
    weeks = int(math.ceil(2 * need / (visitors / days * 7.0)))
    if weeks <= args.max_weeks:
        return "yes -- about %d week%s to catch a 20%% lift" % (
            weeks, "" if weeks == 1 else "s")
    return "no -- fix it and compare before and after"


# --- 3. where in the journey do they leave? ---------------------------------

def analyse_funnel(steps):
    first = steps[0][1]
    table, miscounted = [], []
    prev = None
    for name, n in steps:
        entry = {"step": name, "people": n,
                 "of_start_pct": round(n / first * 100, 1) if first else None,
                 "kept_pct": None, "lost": None}
        if prev is not None:
            entry["kept_pct"] = round(n / prev * 100, 1) if prev else None
            entry["lost"] = prev - n
            if n > prev:
                miscounted.append(name)
        table.append(entry)
        prev = n
    gaps = [{"from": a["step"], "to": b["step"], "lost": b["lost"],
             "kept_pct": b["kept_pct"]}
            for a, b in zip(table, table[1:]) if b["kept_pct"] is not None]
    return {
        "status": "ok", "steps": table, "miscounted": miscounted,
        "most_lost": max(gaps, key=lambda g: g["lost"]) if gaps else None,
        "worst_kept": min(gaps, key=lambda g: g["kept_pct"]) if gaps else None,
    }


# --- 4. can a finished test be trusted? -------------------------------------

def parse_arms(specs, split):
    arms = []
    for i, spec in enumerate(specs):
        m = re.match(r"^(?:(.+?)[:=])?\s*([\d][\d,_]*)\s*/\s*([\d][\d,_]*)$",
                     spec.strip())
        if not m:
            die("cannot read the test numbers \"%s\".\n\n"
                "  Give each version as visitors/conversions, the original "
                "first:\n\n"
                "      --test 10210/512 9987/561\n"
                "      --test control:10210/512 new-page:9987/561" % spec)
        name = m.group(1) or ("control" if i == 0 else
                              "variant" if len(specs) == 2 else "variant %d" % i)
        n, c = to_num(m.group(2)), to_num(m.group(3))
        if c > n:
            die("%s has more conversions (%s) than visitors (%s). The order "
                "is visitors/conversions." % (name, fmt(c), fmt(n)))
        arms.append({"name": name.strip(), "visitors": n, "conversions": c})
    if len(arms) < 2:
        die("a test needs at least two versions: the original and one other.")
    if split:
        shares = [to_num(s) for s in re.split(r"[/:]", split)]
        if len(shares) != len(arms) or any(not s or s <= 0 for s in shares):
            die("--split needs one number per version, like 50/50 or 1/1/2.")
    else:
        shares = [1.0] * len(arms)
    total = sum(shares)
    for arm, share in zip(arms, shares):
        arm["intended_share"] = share / total
    return arms


def analyse_test(arms, args):
    total = sum(a["visitors"] for a in arms)
    chi = 0.0
    for a in arms:
        a["expected"] = total * a["intended_share"]
        a["got_share_pct"] = round(a["visitors"] / total * 100, 2)
        chi += (a["visitors"] - a["expected"]) ** 2 / a["expected"]
    p_split = chi2_sf(chi, len(arms) - 1)
    out = {"arms": arms, "split_p": p_split, "split_bar": args.split_alpha,
           "split_ok": p_split >= args.split_alpha}
    if not out["split_ok"]:
        return out

    control = arms[0]
    bar = args.alpha / (len(arms) - 1)
    out["bar"] = bar
    out["results"] = []
    for arm in arms[1:]:
        n1, c1, n2, c2 = (control["visitors"], control["conversions"],
                          arm["visitors"], arm["conversions"])
        r1, r2 = c1 / n1, c2 / n2
        res = {"name": arm["name"], "control_rate_pct": round(r1 * 100, 2),
               "rate_pct": round(r2 * 100, 2)}
        if min(c1, n1 - c1, c2, n2 - c2) < 10:
            res["verdict"] = "TOO FEW"
            out["results"].append(res)
            continue
        p = two_rate_p(n1, c1, n2, c2)
        se = math.sqrt(r1 * (1 - r1) / n1 + r2 * (1 - r2) / n2)
        z = NORMAL.inv_cdf(1 - bar / 2)
        lo, hi = (r2 - r1) - z * se, (r2 - r1) + z * se
        mde = smallest_detectable(r1, int(min(n1, n2)), bar, args.power)
        lift = (r2 - r1) / r1
        res.update(
            lift_pct=round(lift * 100, 1), p=p,
            range_pct=[round(lo / r1 * 100, 1), round(hi / r1 * 100, 1)],
            smallest_detectable_pct=round(mde * 100, 1) if mde is not None else None)
        if p is not None and p < bar:
            res["verdict"] = "WON" if lift > 0 else "LOST"
            res["flattered"] = mde is None or abs(lift) < mde
        else:
            res["verdict"] = "NO DIFFERENCE YOU CAN RELY ON"
        out["results"].append(res)
    return out


# --- reporting --------------------------------------------------------------

def fmt(v):
    if v is None:
        return "--"
    if isinstance(v, float) and v.is_integer():
        return "{:,}".format(int(v))
    if isinstance(v, float):
        return "{:,.1f}".format(v)
    return "{:,}".format(v)


def pct(v):
    if v is None:
        return "--"
    return ("%.2f%%" if abs(v) < 10 else "%.1f%%") % v


def odds(p):
    if p >= 0.95:
        return "almost every time"
    if p >= 0.15:
        return "about %d times in 10" % round(p * 10)
    if p < 1e-9:
        return "less than 1 time in a billion"
    n = 1 / p
    n = round(n, 1 - int(math.floor(math.log10(n))))   # two figures, no more
    if n >= 1e6:
        return "about 1 time in %g million" % (n / 1e6)
    return "about 1 time in {:,}".format(int(n))


def duration(weeks):
    if weeks is None:
        return "--"
    if weeks > 104:
        return "years"
    if weeks > 52:
        return "over a year"
    return "%d week%s" % (weeks, "" if weeks == 1 else "s")


def cap(s):
    return s[:1].upper() + s[1:]


def plural(n, one, many):
    return "%s %s" % (fmt(n), one if n == 1 else many)


def truncate(s, n=60):
    s = str(s).replace("|", "\\|")
    return s if len(s) <= n else s[:n - 1] + "…"


def render_gate(g, args, out):
    out.append("### 1. Do you have enough traffic to A/B test?")
    out.append("")
    if not g:
        out.append("**Not answered.** Give the totals for the page or journey "
                   "you want to improve: `--visitors N --conversions N --days "
                   "N`. Or pass a page export with `--pages` and it is worked "
                   "out for you.")
        out.append("")
        return
    if g["status"] != "ok":
        out.append("**Could not answer this.** %s" % cap(g["detail"]))
        out.append("")
        return
    out.append("About **%s visits a week**, converting at **%s** (%s visits "
               "and %s conversions over %d days, from %s)."
               % (fmt(round(g["weekly_visitors"])), pct(g["baseline_pct"]),
                  fmt(g["visitors"]), fmt(g["conversions"]), g["days"],
                  g["source"]))
    out.append("")
    if g["verdict"] == "TEST":
        out.append("**Yes. You have enough traffic to test.** A %d-week test "
                   "of two versions would reliably catch an improvement of "
                   "%s%% or more." % (g["weeks"], g["smallest_detectable_pct"]))
    elif g["verdict"] == "BIG CHANGES ONLY":
        out.append("**Only for big changes.** A %d-week test of two versions "
                   "would only catch an improvement of %s%% or more. That "
                   "rules out headlines and button wording, win or lose. Test "
                   "a different offer, a rebuilt page or a shorter form, and "
                   "decide the small things by research instead."
                   % (g["weeks"], g["smallest_detectable_pct"]))
    else:
        catch = ("an improvement of %s%% or more" % g["smallest_detectable_pct"]
                 if g["smallest_detectable_pct"] is not None
                 else "nothing short of conversions multiplying several times over")
        out.append("**No. Do not A/B test.** A %d-week test of two versions "
                   "would only catch %s. Anything you ran would end without an "
                   "answer and be read as one anyway. Find the problem by "
                   "watching and asking, fix it, and compare before and after."
                   % (g["weeks"], catch))
    out.append("")
    out.append("| To catch an improvement of | People needed in each version "
               "| How long that takes you |")
    out.append("|---|---:|---:|")
    for step in g["ladder"]:
        out.append("| %d%% (%s to %s) | %s | %s |" % (
            step["lift_pct"], pct(g["baseline_pct"]),
            pct(g["baseline_pct"] * (1 + step["lift_pct"] / 100.0)),
            fmt(step["per_version"]), duration(step["weeks"])))
    out.append("")
    note = ("> Worked out at the usual settings: %d%% confidence and %d%% "
            "chance of catching a real improvement of that size."
            % (round((1 - args.alpha) * 100), round(args.power * 100)))
    if g["source"] != "the totals you gave":
        note += (" **This is the best case**, because it uses the traffic of "
                 "everything in the export. A test on one page only gets that "
                 "page's visits, which is what the table in section 2 shows.")
    out.append(note)
    out.append("")


def render_leaks(leak, kind, out):
    what = "page" if kind == "pages" else "group"
    if leak["status"] != "ok":
        out.append("**Could not answer this for `%s`.** %s"
                   % (os.path.basename(leak["path"]), cap(leak["detail"])))
        out.append("")
        return
    out.append("From `%s`: %s rows, %s visits, %s conversions. Reading "
               "\"%s\" as visits and \"%s\" as conversions."
               % (os.path.basename(leak["path"]), fmt(leak["rows"]),
                  fmt(leak["visitors"]), fmt(leak["conversions"]),
                  leak["visitors_col"], leak["conversions_col"]))
    notes = []
    if leak["merged"]:
        notes.append("rows for the same page with different tracking codes "
                     "on the end were added together (%s merged)"
                     % fmt(leak["merged"]))
    if leak["too_small"]:
        notes.append("%s too few visits to judge and %s left out"
                     % (plural(leak["too_small"], "row had", "rows had"),
                        "was" if leak["too_small"] == 1 else "were"))
    if notes:
        out.append("%s." % cap("; ".join(notes)))
    out.append("")
    if leak["counts_events"]:
        out.append("> **This export counts events, not people.** %s "
                   "more conversions than visits, which happens when one visit "
                   "fires several counted events. The comparison below still "
                   "points the right way, but export again with the single "
                   "event that is the real conversion before quoting any rate."
                   % plural(leak["counts_events"], "row shows", "rows show"))
        out.append("")
    if not leak["weak"]:
        out.append("No %s converts reliably worse than the rest. That is not "
                   "the same as nothing being wrong. It means that if there is "
                   "a problem it is spread evenly, and only watching people "
                   "use the site will find it." % what)
        out.append("")
    else:
        out.append("| %s | Visits | Conversions | Converts at | Everything "
                   "else converts at | Conversions this gap costs | Could you "
                   "A/B test a fix here? | Why is it low? |"
                   % what.capitalize())
        out.append("|---|---:|---:|---:|---:|---:|---|---|")
        for r in leak["weak"]:
            out.append("| %s | %s | %s | %s | %s | %s | %s | **NEEDS AN "
                       "ANSWER** |" % (
                           truncate(r["item"]), fmt(r["visitors"]),
                           fmt(r["conversions"]), pct(r["rate_pct"]),
                           pct(r["rest_rate_pct"]), fmt(round(r["missed"])),
                           r["testable"]))
        if leak["more"]:
            out.append("")
            out.append("%s flagged and left off. Raise `--top` to see them."
                       % plural(leak["more"], "more row was", "more rows were"))
        out.append("")
    if leak["strong"]:
        out.append("Converting reliably **better** than the rest, and worth "
                   "studying before you change anything else: %s."
                   % "; ".join("`%s` at %s" % (truncate(r["item"], 40),
                                               pct(r["rate_pct"]))
                               for r in leak["strong"]))
        out.append("")


def render_open_rows(out):
    out.append("> **A row still saying NEEDS AN ANSWER means the job is "
               "not finished.** A low number says where to look, never "
               "what is wrong. For each row, find out which of these it "
               "is. For a device or browser, start with the third:")
    out.append(">")
    out.append("> - **it has a different job.** An article is not meant to "
               "convert like a pricing page. Compare it with its own kind "
               "and say so. This is not a leak")
    out.append("> - **the wrong people are arriving.** An advert, search "
               "result or link promised something the page does not "
               "deliver. Export the same page by traffic source")
    out.append("> - **it is broken for some people.** Export it by device "
               "and by browser, then open it on the worst one yourself")
    out.append("> - **the page itself loses them.** The offer is unclear, "
               "something is hard to do, or a worry goes unanswered. Only "
               "watching recordings and asking people can establish this")
    out.append("> - **it is not being counted.** People who start here "
               "convert somewhere the tracking does not follow")
    out.append(">")
    out.append('> If you cannot find out, write "not known" and say what '
               "you would need. Do not fill the gap with a best practice.")
    out.append("")


def render_funnel(f, out):
    out.append("### 3. Where in the journey do people leave?")
    out.append("")
    if not f:
        out.append("**Not answered.** Give the number of people reaching each "
                   "step, in order: `--funnel \"Visited=12000; Started "
                   "signup=1400; Paid=90\"`.")
        out.append("")
        return
    out.append("| Step | People | Kept from the step before | Lost on the way "
               "here | "
               "Still here, of everyone who started |")
    out.append("|---|---:|---:|---:|---:|")
    for e in f["steps"]:
        out.append("| %s | %s | %s | %s | %s |" % (
            truncate(e["step"]), fmt(e["people"]),
            ("%.1f%%" % e["kept_pct"]) if e["kept_pct"] is not None else "--",
            fmt(e["lost"]) if e["lost"] is not None else "--",
            ("%.1f%%" % e["of_start_pct"]) if e["of_start_pct"] is not None else "--"))
    out.append("")
    if f["miscounted"]:
        out.append("**The counting is wrong, so stop here.** More people "
                   "reached %s than the step before it, which cannot happen in "
                   "a real journey. The steps are being counted in different "
                   "ways, or people can join halfway. Fix that before reading "
                   "anything into this table."
                   % " and ".join("\"%s\"" % s for s in f["miscounted"]))
        out.append("")
        return
    most, worst = f["most_lost"], f["worst_kept"]
    if not most:
        out.append("Nobody reached the first step, so there is nothing to "
                   "compare.")
    elif most == worst:
        out.append("**Go and watch what happens between \"%s\" and \"%s\" "
                   "first.** It loses the most people (%s) and lets the "
                   "smallest share through (%.1f%%)."
                   % (most["from"], most["to"], fmt(most["lost"]),
                      most["kept_pct"]))
    else:
        out.append("**Go and watch two places.** The most people (%s) are "
                   "lost between \"%s\" and \"%s\". The smallest share "
                   "(%.1f%%) gets through between \"%s\" and \"%s\"."
                   % (fmt(most["lost"]), most["from"], most["to"],
                      worst["kept_pct"], worst["from"], worst["to"]))
    out.append("")
    out.append("> The table says where to look, not what to fix. Improving any "
               "one step by a tenth gives a tenth more at the end, whichever "
               "step it is, so the size of a drop does not tell you which step "
               "is easiest to improve. Early steps usually lose the most "
               "because most visitors were never going to buy. Watch "
               "recordings of people leaving at the steps named above before "
               "deciding anything.")
    out.append("")


def render_test(t, args, out, numbered):
    out.append("### %sCan you trust this test result?" % ("4. " if numbered else ""))
    out.append("")
    out.append("| Version | Visitors | Share it should have had | Share it got "
               "| Conversions | Converted at |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for a in t["arms"]:
        out.append("| %s | %s | %.1f%% | %.2f%% | %s | %s |" % (
            truncate(a["name"], 30), fmt(a["visitors"]),
            a["intended_share"] * 100, a["got_share_pct"],
            fmt(a["conversions"]),
            pct(a["conversions"] / a["visitors"] * 100)))
    out.append("")
    if not t["split_ok"]:
        out.append("**STOP. The visitors were not split the way the test was "
                   "set up, so the result cannot be trusted.** A split this "
                   "far off would happen by luck %s. Something sent the wrong "
                   "people into one version, or lost them on the way to being "
                   "counted, and whatever did it can also fake a win or a "
                   "loss." % odds(t["split_p"]))
        out.append("")
        out.append("**The result is deliberately not shown.** A number here "
                   "would get quoted. Find the cause first. The usual ones:")
        out.append("")
        out.append("- one version redirects, loads slower or errors, so some "
                   "of its visitors leave before they are counted")
        out.append("- bots or internal traffic are filtered out of one version "
                   "more than the other")
        out.append("- the share going to each version was changed while the "
                   "test was running")
        out.append("- visitors are only counted once they reach something "
                   "that one version makes easier to reach")
        out.append("")
        out.append("If the test was not meant to be an even split, say so with "
                   "`--split`, for example `--split 90/10`.")
        out.append("")
        return
    out.append("**The split is sound.** A difference this size between the "
               "shares would happen by luck %s, so there is no sign of "
               "visitors going missing. This check comes first because a "
               "broken split makes everything below it meaningless."
               % odds(t["split_p"]))
    out.append("")
    several = len(t["results"]) > 1
    for r in t["results"]:
        name = truncate(r["name"], 30)
        if r["verdict"] == "TOO FEW":
            out.append("**%s: too few conversions to say anything.** One of "
                       "the two versions has fewer than ten conversions or "
                       "fewer than ten non-conversions. The arithmetic does "
                       "not hold at that size." % name)
        elif r["verdict"] in ("WON", "LOST"):
            out.append("**%s %s.** It converted at %s against %s, %s%% %s. "
                       "The true difference is probably somewhere between "
                       "%+.1f%% and %+.1f%%. A gap this size would happen by "
                       "luck %s."
                       % (name, "won" if r["verdict"] == "WON" else "lost",
                          pct(r["rate_pct"]), pct(r["control_rate_pct"]),
                          abs(r["lift_pct"]),
                          "better" if r["lift_pct"] > 0 else "worse",
                          r["range_pct"][0], r["range_pct"][1], odds(r["p"])))
            if r["flattered"]:
                out.append("")
                out.append("> **Do not quote the %s%%.** This test was too "
                           "small to reliably catch a difference of that size, "
                           "and a small test only reaches a clear result when "
                           "the measured gap happens to be flattering. The "
                           "direction is probably right. The size is probably "
                           "overstated." % abs(r["lift_pct"]))
        else:
            reach = ("%s%% or more" % r["smallest_detectable_pct"]
                     if r["smallest_detectable_pct"] is not None
                     else "several times the current rate")
            out.append("**%s: no difference you can rely on.** It converted at "
                       "%s against %s (%+.1f%%), and a gap that size would "
                       "happen by luck %s. This test could only reliably catch "
                       "a difference of %s, so this is \"we could not tell\", "
                       "not \"it makes no difference\"."
                       % (name, pct(r["rate_pct"]), pct(r["control_rate_pct"]),
                          r["lift_pct"], odds(r["p"]), reach))
        out.append("")
    if several:
        out.append("> With %d versions against the original there are %d "
                   "chances for one to look good by luck, so the bar for each "
                   "was raised to match." % (len(t["results"]), len(t["results"])))
        out.append("")
    out.append("> Three things these numbers cannot show, so check them "
               "yourself. Was the length of the test fixed before it started, "
               "or was it stopped when it looked good? Did it run for whole "
               "weeks? Did anything else get worse, such as refunds, order "
               "size or sign-ups that never came back?")
    out.append("")


def render(result, args):
    out = ["## Conversion research -- %s" % date.today().isoformat(), ""]
    research = any(k in result for k in ("gate", "pages", "segments", "funnel"))
    if research:
        render_gate(result.get("gate"), args, out)

        out.append("### 2. Which pages or groups convert worse than the rest?")
        out.append("")
        if "pages" not in result and "segments" not in result:
            out.append("**Not answered.** Pass a page export with `--pages`, "
                       "or the same numbers split by device, browser or "
                       "traffic source with `--segments`. In GA4: Reports -> "
                       "the Landing page report -> Share this report -> "
                       "Download File -> Download CSV.")
            out.append("")
        if "pages" in result:
            render_leaks(result["pages"], "pages", out)
        for leak in result.get("segments", []):
            render_leaks(leak, "segments", out)
        if any(leak.get("weak") for leak in
               [result.get("pages") or {}] + result.get("segments", [])):
            render_open_rows(out)

        render_funnel(result.get("funnel"), out)
    if "test" in result:
        render_test(result["test"], args, out, research)
    if research:
        out.append("### %d. What the numbers cannot tell you"
                   % (5 if "test" in result else 4))
        out.append("")
        out.append("Everything above says where. None of it says why, and no "
                   "export can. For each row or step flagged above, this part "
                   "is on you:")
        out.append("")
        out.append("- **Watch.** Recordings of people who left from that page "
                   "or step, until the same thing has gone wrong more than "
                   "once.")
        out.append("- **Ask.** People who left: what were you looking for? "
                   "People who bought: what nearly stopped you?")
        out.append("- **Try it.** On the device and browser that converts "
                   "worst, as a stranger would.")
        out.append("")
        out.append("A recommendation with none of these behind it is an "
                   "opinion. Label it as one.")
        out.append("")
    return "\n".join(out)


def _force_utf8_stdout():
    """Windows consoles default to cp1252 and choke on arrows and ellipses."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    _force_utf8_stdout()
    p = argparse.ArgumentParser(
        description="Find where a site loses people, whether you have the "
                    "traffic to A/B test a fix, and whether a finished test "
                    "can be trusted.")
    p.add_argument("--pages", metavar="FILE",
                   help="a list of pages with visits and conversions. In GA4: "
                        "the Landing page report -> Share this report -> "
                        "Download File -> Download CSV")
    p.add_argument("--segments", metavar="FILE", nargs="+", default=[],
                   help="the same numbers split another way: by device, "
                        "browser, or traffic source. One file per split")
    p.add_argument("--funnel", metavar="STEPS",
                   help="people reaching each step, in order: \"Visited=12000; "
                        "Started signup=1400; Paid=90\". Or a file with one "
                        "row per step")
    p.add_argument("--test", metavar="V/C", nargs="+",
                   help="a finished A/B test, the original first, each "
                        "version as visitors/conversions: 10210/512 9987/561")
    p.add_argument("--split", metavar="A/B",
                   help="how the test was meant to divide visitors, if not "
                        "evenly: 90/10")
    p.add_argument("--visitors", type=float, metavar="N",
                   help="total visits, when you have no export to give")
    p.add_argument("--conversions", type=float, metavar="N",
                   help="total conversions over the same period")
    p.add_argument("--days", type=float, metavar="N",
                   help="how many days the numbers cover. Read from a GA4 "
                        "export automatically; needed for anything else")
    p.add_argument("--weeks", type=int, default=4, metavar="N",
                   help="how long a test you are willing to run (default 4)")
    p.add_argument("--max-weeks", type=int, default=8, metavar="N",
                   help="call a page untestable if a test on it would take "
                        "longer than this (default 8)")
    p.add_argument("--min-visitors", type=float, default=200.0, metavar="N",
                   help="leave out rows with fewer visits than this, so small "
                        "pages stay out (default 200)")
    p.add_argument("--top", type=int, default=15, metavar="N",
                   help="show at most this many flagged rows (default 15)")
    p.add_argument("--keep-query", action="store_true",
                   help="do not add /page?a=1 and /page?b=2 together")
    p.add_argument("--visitors-col", metavar="NAME",
                   help="the column holding visits, if it was not found")
    p.add_argument("--conversions-col", metavar="NAME",
                   help="the column holding conversions, if it was not found "
                        "or the wrong one was picked")
    p.add_argument("--alpha", type=float, default=0.05, metavar="P",
                   help="how often you accept being fooled by luck "
                        "(default 0.05)")
    p.add_argument("--power", type=float, default=0.80, metavar="P",
                   help="chance of catching a real improvement (default 0.80)")
    p.add_argument("--split-alpha", type=float, default=0.001, metavar="P",
                   help="how unlikely an uneven split must be before the test "
                        "is stopped (default 0.001)")
    p.add_argument("--json", action="store_true",
                   help="output for another program instead of for reading")
    args = p.parse_args()

    totals = args.visitors is not None or args.conversions is not None
    if not (args.pages or args.segments or args.funnel or args.test or totals):
        p.error("nothing to look at. Give --pages for a page export, --funnel "
                "for the steps of a journey, --test for a finished test, or "
                "--visitors, --conversions and --days for the totals.")
    if totals and (args.visitors is None or args.conversions is None):
        p.error("--visitors and --conversions go together, with --days.")
    if args.split and not args.test:
        p.error("--split describes a test, so it needs --test.")

    result = {}
    tables = []
    if args.pages:
        tables.append(("pages", load_breakdown(args.pages, args,
                                               not args.keep_query)))
    for path in args.segments:
        tables.append(("segments", load_breakdown(path, args, False)))

    exported_days = next((t["days"] for _, t in tables if t["days"]), None)
    days = args.days or exported_days

    if totals:
        if args.visitors <= 0:
            p.error("--visitors must be more than zero.")
        result["gate"] = analyse_gate(args.visitors, args.conversions, days,
                                      "the totals you gave", args)
    elif tables:
        _, first = tables[0]
        result["gate"] = analyse_gate(
            sum(r["visitors"] for r in first["rows"]),
            sum(r["conversions"] for r in first["rows"]), days,
            "`%s`" % os.path.basename(first["path"]), args,
            any(r["conversions"] > r["visitors"] for r in first["rows"]))

    for kind, table in tables:
        leak = analyse_leaks(table, days, args)
        if kind == "pages":
            result["pages"] = leak
        else:
            result.setdefault("segments", []).append(leak)

    if args.funnel:
        result["funnel"] = analyse_funnel(load_funnel(args.funnel))
    if args.test:
        result["test"] = analyse_test(parse_arms(args.test, args.split), args)

    if args.json:
        result["generated"] = date.today().isoformat()
        print(json.dumps(result, indent=2))
    else:
        print(render(result, args))

    findings = 0
    for leak in [result.get("pages")] + result.get("segments", []):
        if leak and leak.get("status") == "ok":
            findings += len(leak["weak"])
    if result.get("funnel", {}).get("miscounted"):
        findings += 1
    if "test" in result and not result["test"]["split_ok"]:
        findings += 1
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
