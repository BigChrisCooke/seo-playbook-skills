#!/usr/bin/env python3
"""
trend_scan.py -- make direction the first question an audit asks.

A twelve-month aggregate can look healthy while five of those months are a
slide. This reads the series instead of the total and prints both side by
side, so the flattering number can never travel without the damning one.

Usage:
  # Direction, from a GSC "Dates" export (daily or monthly rows):
  python3 trend_scan.py --series Dates.csv

  # Trend breaks, from two exports of the same table over different windows:
  python3 trend_scan.py --prior Queries-2025H2.csv --recent Queries-2026H1.csv

  # Both, with JSON for a pipeline:
  python3 trend_scan.py --series Dates.csv --prior p.csv --recent r.csv --json

Thresholds (defaults match the runbook's Trend & Anomaly Scan):
  --click-drop 30       flag an item losing more than this % of clicks
  --position-drop 2.0   flag an item losing more than this many avg positions
  --concentration 25    flag portfolio risk above this % of clicks in one item
  --min-clicks 10       ignore items below this many prior clicks (noise floor)

Exit codes: 0 nothing flagged | 1 findings to diagnose | 2 bad input.
Stdlib only. No network, no auth, no API keys.
"""

import argparse
import csv
import json
import re
import sys
from collections import OrderedDict
from datetime import date, datetime

# --- column detection -------------------------------------------------------
# GSC exports vary by locale, UI version, and whether they came from the
# Export button or a copy-paste. Match on normalised substrings, not equality.

COLUMN_ALIASES = OrderedDict([
    ("date",        ("date", "datum", "fecha", "día", "day", "month", "week")),
    ("clicks",      ("clicks", "click", "klicks", "clics")),
    ("impressions", ("impressions", "impression", "impr", "impresiones")),
    ("ctr",         ("ctr", "click through rate", "click-through rate")),
    ("position",    ("position", "pos.", "ranking")),
])

# Anything that isn't a metric or a date is the thing being measured.
DIMENSION_HINTS = ("query", "queries", "page", "pages", "url", "landing",
                   "keyword", "search term", "country", "device")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def detect_columns(header):
    """Return {canonical_name: column_index} for whatever we can recognise."""
    found = {}
    for idx, raw in enumerate(header):
        h = norm(raw)
        if not h:
            continue
        for canon, aliases in COLUMN_ALIASES.items():
            if canon in found:
                continue
            # "average position" and "position" both land on position;
            # "ctr" must not be swallowed by a looser match, so test longest first.
            if any(a in h for a in aliases):
                found[canon] = idx
                break
    # Dimension: an explicit hint wins, else the first unclaimed column.
    claimed = set(found.values())
    for idx, raw in enumerate(header):
        if idx in claimed:
            continue
        if any(hint in norm(raw) for hint in DIMENSION_HINTS):
            found["dimension"] = idx
            break
    if "dimension" not in found:
        for idx, raw in enumerate(header):
            if idx not in claimed and norm(raw):
                found["dimension"] = idx
                break
    return found


def to_num(value):
    """'1,234' -> 1234.0 ; '3.5%' -> 3.5 ; '' -> None. Never raises."""
    if value is None:
        return None
    s = str(value).strip().replace(" ", "").replace(",", "")
    s = s.replace("%", "").replace("$", "")
    if not s or s in ("-", "--", "n/a", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y",
                "%Y-%m", "%b %Y", "%B %Y", "%d %b %Y", "%d %B %Y")


def to_month(value):
    """Parse a cell into 'YYYY-MM', or None if it isn't a date."""
    s = str(value or "").strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    m = re.match(r"^(\d{4})-(\d{1,2})", s)
    if m:
        return "%s-%02d" % (m.group(1), int(m.group(2)))
    return None


def read_table(path):
    """Return (columns, rows) where rows are raw lists. Tolerates BOM."""
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(8192)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = [r for r in csv.reader(fh, dialect) if any(c.strip() for c in r)]
    except OSError as exc:
        die("cannot read %s: %s" % (path, exc))
    if len(rows) < 2:
        die("%s has no data rows" % path)
    return detect_columns(rows[0]), rows[1:]


def die(msg):
    sys.stderr.write("trend-scan: %s\n" % msg)
    sys.exit(2)


def pct_change(old, new):
    if old in (None, 0) or new is None:
        return None
    return (new - old) / old * 100.0


# --- 1. direction -----------------------------------------------------------

def analyse_direction(path):
    cols, rows = read_table(path)
    if "date" not in cols or "clicks" not in cols:
        # Being told what is missing is no use on its own. Work out what the
        # file actually is and say what to do with it instead.
        if "dimension" in cols and "clicks" in cols:
            die("%s has no dates in it.\n\n"
                "  It looks like a list of pages or search terms, so it can "
                "answer two of the four\n"
                "  questions but not this one. Try:\n\n"
                "      --recent \"%s\"                      how much rides on "
                "one page\n"
                "      --prior OLDER.csv --recent \"%s\"    what dropped, and "
                "how much\n\n"
                "  For \"is traffic going up or down\", you need the file with "
                "one row per date.\n"
                "  In Search Console that is Performance -> Export -> the "
                "Dates tab."
                % (path, path, path))
        die("%s is missing something this needs.\n\n"
            "  Looking for a column of dates and a column of clicks. Found: "
            "%s.\n"
            "  In Search Console, use Performance -> Export and pick the Dates "
            "tab."
            % (path, ", ".join(sorted(cols)) or "nothing it recognised"))

    months = OrderedDict()
    skipped = 0
    for row in rows:
        try:
            month = to_month(row[cols["date"]])
        except IndexError:
            skipped += 1
            continue
        if month is None:
            skipped += 1
            continue
        bucket = months.setdefault(month, {"clicks": 0.0, "impressions": 0.0,
                                           "pos_sum": 0.0, "pos_n": 0})
        clicks = to_num(row[cols["clicks"]]) if cols["clicks"] < len(row) else None
        bucket["clicks"] += clicks or 0.0
        if "impressions" in cols and cols["impressions"] < len(row):
            bucket["impressions"] += to_num(row[cols["impressions"]]) or 0.0
        if "position" in cols and cols["position"] < len(row):
            p = to_num(row[cols["position"]])
            if p is not None:
                bucket["pos_sum"] += p
                bucket["pos_n"] += 1

    if len(months) < 2:
        return {"status": "insufficient",
                "detail": "need at least 2 months of rows; parsed %d "
                          "(%d rows had no usable date)" % (len(months), skipped)}

    ordered = sorted(months.items())
    series = []
    prev = None
    for month, b in ordered:
        entry = {
            "month": month,
            "clicks": round(b["clicks"], 1),
            "impressions": round(b["impressions"], 1) if b["impressions"] else None,
            "position": round(b["pos_sum"] / b["pos_n"], 1) if b["pos_n"] else None,
            "delta_pct": round(pct_change(prev, b["clicks"]), 1)
                         if prev not in (None, 0) else None,
        }
        series.append(entry)
        prev = b["clicks"]

    # Longest run of consecutive monthly declines ending at the last month.
    decline_run = 0
    for entry in reversed(series[1:]):
        if entry["delta_pct"] is not None and entry["delta_pct"] < 0:
            decline_run += 1
        else:
            break

    total = sum(e["clicks"] for e in series)
    half = max(1, min(3, len(series) // 2))
    recent = sum(e["clicks"] for e in series[-half:])
    prior = sum(e["clicks"] for e in series[-2 * half:-half])
    recent_vs_prior = pct_change(prior, recent)

    yoy = None
    if len(series) >= 24:
        last12 = sum(e["clicks"] for e in series[-12:])
        prev12 = sum(e["clicks"] for e in series[-24:-12])
        yoy = pct_change(prev12, last12)

    block = "month" if half == 1 else "%d months" % half
    if decline_run >= 3:
        verdict = ("FALLING -- clicks declined in each of the last %d months"
                   % decline_run)
    elif recent_vs_prior is not None and recent_vs_prior <= -15:
        verdict = ("FALLING -- the last %s sit %.1f%% below the %s before"
                   % (block, abs(recent_vs_prior), block))
    elif recent_vs_prior is not None and recent_vs_prior >= 15:
        verdict = ("RISING -- the last %s sit %.1f%% above the %s before"
                   % (block, recent_vs_prior, block))
    else:
        verdict = ("FLAT -- no move beyond +/-15%% between the last two "
                   "%s-long blocks" % block)

    return {
        "status": "ok",
        "series": series,
        "window": "%s to %s" % (series[0]["month"], series[-1]["month"]),
        "months": len(series),
        "total_clicks": round(total, 1),
        "recent_block": half,
        "recent_block_label": block,
        "recent_vs_prior_pct": round(recent_vs_prior, 1) if recent_vs_prior is not None else None,
        "yoy_pct": round(yoy, 1) if yoy is not None else None,
        "consecutive_declines": decline_run,
        "verdict": verdict,
    }


# --- 2. trend breaks + 3. concentration ------------------------------------

def load_dimension(path):
    cols, rows = read_table(path)
    if "clicks" not in cols or "dimension" not in cols:
        die("%s is missing something this needs.\n\n"
            "  Looking for a column of clicks and a column listing your pages "
            "or search terms.\n"
            "  Found: %s.\n"
            "  In Search Console, use Performance and export either the "
            "Queries tab or the Pages tab."
            % (path, ", ".join(sorted(cols)) or "nothing it recognised"))
    table = {}
    for row in rows:
        if cols["dimension"] >= len(row):
            continue
        key = (row[cols["dimension"]] or "").strip()
        if not key:
            continue
        rec = {"clicks": to_num(row[cols["clicks"]]) if cols["clicks"] < len(row) else None}
        for metric in ("impressions", "position", "ctr"):
            if metric in cols and cols[metric] < len(row):
                rec[metric] = to_num(row[cols[metric]])
            else:
                rec[metric] = None
        table[key] = rec
    return table


def analyse_breaks(prior_path, recent_path, click_drop, position_drop, min_clicks):
    prior = load_dimension(prior_path)
    recent = load_dimension(recent_path)

    movers, lost = [], []
    for key, before in prior.items():
        b_clicks = before.get("clicks") or 0.0
        if b_clicks < min_clicks:
            continue
        after = recent.get(key)
        if after is None:
            lost.append({"item": key, "prior_clicks": b_clicks,
                         "flags": ["gone from the newer list altogether"]})
            continue
        a_clicks = after.get("clicks") or 0.0
        d_clicks = pct_change(b_clicks, a_clicks)

        b_pos, a_pos = before.get("position"), after.get("position")
        d_pos = (a_pos - b_pos) if (b_pos is not None and a_pos is not None) else None

        flags = []
        if d_clicks is not None and d_clicks <= -click_drop:
            flags.append("lost %.0f%% of its clicks" % abs(d_clicks))
        if d_pos is not None and d_pos >= position_drop:
            flags.append("slipped %.1f places down" % d_pos)
        if flags:
            movers.append({
                "item": key,
                "prior_clicks": b_clicks, "recent_clicks": a_clicks,
                "clicks_delta_pct": round(d_clicks, 1) if d_clicks is not None else None,
                "prior_position": b_pos, "recent_position": a_pos,
                "position_delta": round(d_pos, 1) if d_pos is not None else None,
                "flags": flags,
                "diagnosis": None,   # the agent must fill this in
            })

    movers.sort(key=lambda m: m["prior_clicks"], reverse=True)
    lost.sort(key=lambda m: m["prior_clicks"], reverse=True)
    return movers, lost


def analyse_concentration(path, threshold):
    table = load_dimension(path)
    ranked = sorted(((k, v.get("clicks") or 0.0) for k, v in table.items()),
                    key=lambda kv: kv[1], reverse=True)
    total = sum(c for _, c in ranked)
    if total <= 0:
        return {"status": "insufficient", "detail": "no clicks in %s" % path}
    top1 = ranked[0]
    share1 = top1[1] / total * 100.0
    share3 = sum(c for _, c in ranked[:3]) / total * 100.0
    share10 = sum(c for _, c in ranked[:10]) / total * 100.0
    return {
        "status": "ok",
        "items": len(ranked),
        "top_item": top1[0],
        "top_item_clicks": top1[1],
        "top_1_share_pct": round(share1, 1),
        "top_3_share_pct": round(share3, 1),
        "top_10_share_pct": round(share10, 1),
        "at_risk": share1 >= threshold,
        "threshold_pct": threshold,
    }


# --- reporting --------------------------------------------------------------

def render(result, args):
    out = []
    out.append("## Traffic check -- %s" % date.today().isoformat())
    out.append("")

    # --- 1 ------------------------------------------------------------------
    d = result.get("direction")
    out.append("### 1. Is traffic going up or down?")
    out.append("")
    if not d:
        out.append("**Not answered.** This needs the export with one row per "
                   "date. In Search Console: Performance -> Export -> Dates, "
                   "then pass it with `--series`.")
        out.append("")
    elif d["status"] != "ok":
        out.append("**Could not answer this.** %s" % d["detail"])
        out.append("")
        out.append('Do not fall back on the total for the whole period '
                   'instead. Write "we could not check the trend, because" and '
                   'what was missing. Saying nothing reads as good news.')
        out.append("")
    else:
        out.append("| Month | Clicks | Change on last month | Times shown | "
                   "Average place in results |")
        out.append("|---|---:|---:|---:|---:|")
        for e in d["series"]:
            out.append("| %s | %s | %s | %s | %s |" % (
                e["month"], fmt(e["clicks"]),
                ("%+.1f%%" % e["delta_pct"]) if e["delta_pct"] is not None else "--",
                fmt(e["impressions"]), fmt(e["position"])))
        out.append("")
        out.append("**%s**" % plain_verdict(d))
        out.append("")
        label = d.get("recent_block_label", "%d months" % d["recent_block"])
        change = (("%+.1f%%" % d["recent_vs_prior_pct"])
                  if d["recent_vs_prior_pct"] is not None else "not comparable")
        yoy = ((" Against the same period a year earlier: %+.1f%%."
                % d["yoy_pct"]) if d["yoy_pct"] is not None else "")
        out.append("> **Quote both of these numbers, never just the first.** "
                   "Across the whole period (%s) the site got **%s clicks**. "
                   "But the last %s came in **%s** compared with the %s before "
                   "it.%s A total for a long period can look healthy while the "
                   "recent months are falling."
                   % (d["window"], fmt(d["total_clicks"]), label, change,
                      label, yoy))
        out.append("")

    # --- 2 ------------------------------------------------------------------
    out.append("### 2. What dropped?")
    out.append("")
    if "movers" not in result:
        out.append("**Not answered.** This one needs two lists to compare: the "
                   "same Search Console table exported twice, over two "
                   "different date ranges. Pass the older one as `--prior` and "
                   "the newer one as `--recent`. Until then, treat this "
                   "question as still open rather than as nothing to report.")
        out.append("")
    else:
        movers, lost = result["movers"], result["lost"]
        if not movers and not lost:
            out.append("Nothing dropped far enough to flag. The bar was: lost "
                       "more than %d%% of its clicks, or slipped more than %.1f "
                       "places down the results, having started with at least "
                       "%d clicks."
                       % (args.click_drop, args.position_drop, args.min_clicks))
            out.append("")
        else:
            out.append("| Page or search term | Clicks | Change | Place in "
                       "results | Why it is here | What caused it |")
            out.append("|---|---|---:|---|---|---|")
            for m in movers:
                out.append("| %s | %s to %s | %s | %s to %s | %s | **NEEDS AN "
                           "ANSWER** |" % (
                               truncate(m["item"]),
                               fmt(m["prior_clicks"]), fmt(m["recent_clicks"]),
                               ("%+.1f%%" % m["clicks_delta_pct"])
                               if m["clicks_delta_pct"] is not None else "--",
                               fmt(m["prior_position"]), fmt(m["recent_position"]),
                               ", ".join(m["flags"])))
            for m in lost:
                out.append("| %s | %s to 0 | -100%% | -- | %s | **NEEDS AN "
                           "ANSWER** |"
                           % (truncate(m["item"]), fmt(m["prior_clicks"]),
                              ", ".join(m["flags"])))
            out.append("")
            out.append("> **A row still saying NEEDS AN ANSWER means the job "
                       "is not finished.** For each one, replace it with the "
                       "reason:")
            out.append(">")
            out.append("> - the page has not been updated in a long time and "
                       "better pages have overtaken it")
            out.append("> - a competitor published something newer -- check the "
                       "dates on the pages now sitting above you")
            out.append("> - Google started showing an AI summary or a featured "
                       "box that takes the click instead")
            out.append("> - people still see the page but stop clicking, which "
                       "usually points at the title or the description")
            out.append("> - something technical broke: the page got blocked, "
                       "redirected, or much slower")
            out.append(">")
            out.append('> If you genuinely do not know, write "not known" and '
                       'say what you would need in order to find out. An honest '
                       '"not known" is worth more than a guess.')
            out.append(">")
            out.append("> Before blaming anything, check what you changed and "
                       "when. If a drop lines up with a release, that is worth "
                       'noting -- but write **"happened at the same time as"**, '
                       'not "caused by", unless you have actually proved it.')
            out.append("")

    # --- 3 ------------------------------------------------------------------
    c = result.get("concentration")
    out.append("### 3. How much rides on one page?")
    out.append("")
    if not c:
        out.append("**Not answered.** Pass a list of pages or search terms as "
                   "`--recent` and this one answers itself.")
        out.append("")
    elif c["status"] != "ok":
        out.append("**Could not answer this.** %s" % c["detail"])
        out.append("")
    else:
        out.append("- Biggest single one: `%s` -- **%.1f%% of all clicks** (%s "
                   "clicks)" % (truncate(c["top_item"]), c["top_1_share_pct"],
                                fmt(c["top_item_clicks"])))
        out.append("- Top three together: %.1f%%. Top ten: %.1f%%. Out of %d in "
                   "the list." % (c["top_3_share_pct"], c["top_10_share_pct"],
                                  c["items"]))
        out.append("")
        if c["at_risk"]:
            out.append("**Too much rides on one page.** It brings in %.1f%% of "
                       "the clicks, well over the %d%% mark. Say so in the "
                       "report and add an action to spread the traffic wider. A "
                       "site living off one page is one Google update away from "
                       "losing most of its traffic overnight."
                       % (c["top_1_share_pct"], c["threshold_pct"]))
        else:
            out.append("Reasonably spread out -- nothing is over the %d%% mark."
                       % c["threshold_pct"])
        out.append("")

    # --- 4 ------------------------------------------------------------------
    out.append("### 4. What is Google telling you directly?")
    out.append("")
    out.append("This one cannot be worked out from an export, so it is on you. "
               "Go through every message and recommendation in Search Console, "
               "plus anything under Manual Actions and Security Issues, and "
               "answer each one. A message you have not looked at is an open "
               "question, not a clean bill of health.")
    out.append("")
    return "\n".join(out)


def plain_verdict(d):
    """Say what the numbers mean, in words a non-technical reader can act on."""
    v = d["verdict"]
    if v.startswith("FALLING"):
        if d["consecutive_declines"] >= 3:
            return ("Traffic is falling. Clicks have gone down every month for "
                    "the last %d months." % d["consecutive_declines"])
        return ("Traffic is falling. The most recent stretch came in %.1f%% "
                "below the one before it." % abs(d["recent_vs_prior_pct"]))
    if v.startswith("RISING"):
        return ("Traffic is growing. The most recent stretch came in %.1f%% "
                "above the one before it." % d["recent_vs_prior_pct"])
    return ("Traffic is holding steady. Nothing has moved more than 15% either "
            "way between the two most recent stretches.")


def fmt(v):
    if v is None:
        return "--"
    if isinstance(v, float) and v.is_integer():
        return "{:,}".format(int(v))
    if isinstance(v, float):
        return "{:,.1f}".format(v)
    return "{:,}".format(v)


def truncate(s, n=60):
    s = str(s).replace("|", "\\|")
    return s if len(s) <= n else s[:n - 1] + "…"


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
        description="Work out whether traffic is going up or down, what "
                    "dropped, and how much rides on one page.")
    p.add_argument("--series", metavar="FILE",
                   help="the export with one row per date. Answers \"is traffic "
                        "going up or down\". In Search Console: Performance -> "
                        "Export -> Dates")
    p.add_argument("--recent", metavar="FILE",
                   help="a list of pages or search terms for the LATER period. "
                        "On its own, answers \"how much rides on one page\"")
    p.add_argument("--prior", metavar="FILE",
                   help="the same list for an EARLIER period. Add this to "
                        "--recent to see what dropped")
    p.add_argument("--click-drop", type=float, default=30.0, metavar="PCT",
                   help="flag anything that lost more than this share of its "
                        "clicks (default 30%%)")
    p.add_argument("--position-drop", type=float, default=2.0, metavar="N",
                   help="flag anything that slipped more than this many places "
                        "down the results (default 2)")
    p.add_argument("--one-page-limit", "--concentration", type=float,
                   default=25.0, metavar="PCT", dest="concentration",
                   help="warn when a single page or search term brings in more "
                        "than this share of all the clicks (default 25%%)")
    p.add_argument("--min-clicks", type=float, default=10.0, metavar="N",
                   help="ignore anything that had fewer than this many clicks "
                        "to begin with, so small wobbles stay out (default 10)")
    p.add_argument("--json", action="store_true",
                   help="output for another program instead of for reading")
    args = p.parse_args()

    if not args.series and not args.recent:
        p.error("nothing to look at. Give --series for a date export, "
                "--recent for a list of pages or search terms, or both.")
    if args.prior and not args.recent:
        p.error("--prior is the earlier period, so it needs --recent to compare "
                "against. Give both, or give --recent on its own.")

    result = {}
    if args.series:
        result["direction"] = analyse_direction(args.series)
    if args.recent:
        # One table answers "how much rides on one page" by itself. Only the
        # comparison needs two.
        result["concentration"] = analyse_concentration(args.recent,
                                                        args.concentration)
        if args.prior:
            movers, lost = analyse_breaks(args.prior, args.recent,
                                          args.click_drop, args.position_drop,
                                          args.min_clicks)
            result["movers"] = movers
            result["lost"] = lost

    if args.json:
        result["generated"] = date.today().isoformat()
        print(json.dumps(result, indent=2))
    else:
        print(render(result, args))

    findings = 0
    d = result.get("direction")
    if d and d.get("status") == "ok" and d["verdict"].startswith("FALLING"):
        findings += 1
    findings += len(result.get("movers", [])) + len(result.get("lost", []))
    c = result.get("concentration")
    if c and c.get("status") == "ok" and c.get("at_risk"):
        findings += 1
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
