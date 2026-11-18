"""Explain one PR in a report, in plain English, from that report's own results file:
whether it was counted, which period it fell in, its times, each review and why it
did or didn't count, each value with its rule, and where each rule lives in metrics.py.

Usage (from the repo folder):
  python scripts/explain.py --repo cli/cli --pr 14815
  python scripts/explain.py --repo cli/cli --pr 14815 --run output/20261118-092624

Without --run, it uses the newest report run in output/.
Read-only: recalculates nothing, never contacts GitHub, writes nothing.
"""

import argparse
import inspect
import json
import sys
from datetime import datetime
from pathlib import Path

import metrics as m
from report import tz_from_offset


def where(func):
    """File, function and current line range, e.g. metrics.py per_pr (lines 245-300)."""
    lines, start = inspect.getsourcelines(func)
    return f"{Path(inspect.getsourcefile(func)).name} {func.__name__} (lines {start}-{start + len(lines) - 1})"


def rule(func):
    """The function's docstring as one paragraph."""
    return " ".join(inspect.getdoc(func).split())


def newest_run(slug):
    """The newest output/YYYYMMDD-HHMMSS folder that has this repo's results."""
    runs = sorted(p.parent for p in Path("output").glob(f"*/results-{slug}.json")
                  if p.parent.name[:8].isdigit())
    if not runs:
        m.stop(2, f"no report found in output/ for this repo. Run the report first.")
    return runs[-1]


def main():
    ap = argparse.ArgumentParser(description="Explain one PR in a report, in plain English.")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--pr", required=True, type=int, help="PR number")
    ap.add_argument("--run", help="report run folder, e.g. output/20261118-092624 (default: newest)")
    args = ap.parse_args()

    slug = args.repo.replace("/", "-")
    run = Path(args.run) if args.run else newest_run(slug)
    path = run / f"results-{slug}.json"
    if not path.exists():
        m.stop(2, f"{path} not found.")
    res = json.loads(path.read_text(encoding="utf-8"))
    if "left_out" not in res:
        m.stop(2, f"{path} was made before reports recorded their decisions. Run the report again.")
    notes, key = res["notes"], f"{args.repo}#{args.pr}"
    offset = notes["utc_offset"]
    tz = tz_from_offset(offset)
    local = lambda iso: (datetime.fromisoformat(iso).astimezone(tz).strftime("%d %b %Y %H:%M:%S")
                         if iso else "none")

    print(f"{key}, in report {run.as_posix()}")
    print(f"Report covers {notes['scope']}. Data as of {local(notes['data_as_of'])} (UTC{offset}).")
    row = next((r for r in res["prs"] if r["key"] == key), None)
    out = next((r for r in res.get("left_out", []) if r["key"] == key), None)

    if out:
        print(f"{out['title']}\n{out['url']}\nAuthor: {out['author']}\n")
        print(f"NOT COUNTED: {out['reason']}.")
        print(f"Rule ({where(m.left_out_reason)}): {rule(m.left_out_reason)}")
        return
    if row is None:
        print("\nNot in this report. It was not merged, closed or still open within the "
              "report's range, or it is not in the saved data.")
        return

    print(f"{row['title']}\n{row['url']}\nAuthor: {row['author']}\n")
    if row["column"]:
        print(f"Counted in period {row['column']} ({row['outcome'].replace('_', ' ')}).")
    else:
        print("Still open: it appears in the open PR counts and ages, not in any period's times.")
    print(f"Rule ({where(m.assign_periods)}): {rule(m.assign_periods)}\n")

    print(f"Times (UTC{offset})")
    print(f"  Opened         {local(row['created'])}")
    print(f"  Ready          {local(row['ready_at'] or row['created'])}  (taken from {row['ready_from']})")
    print(f"  First review   {local(row['first_review_at'])}")
    print(f"  Last approval  {local(row['last_approval_at'])}")
    print(f"  Merged         {local(row['merged'])}")
    if not row["merged"]:
        print(f"  Closed         {local(row['closed'])}")

    print(f"\nReviews ({len(row['reviews'])} collected)")
    for r in row["reviews"]:
        verdict = "counts" if r["why_not_counted"] is None else f"doesn't count: {r['why_not_counted']}"
        print(f"  {local(r['at']):20}  {r['by'] or 'unknown':30} {r['state']:18} {verdict}")
    print(f"Rule ({where(m.review_decision)}): {rule(m.review_decision)}\n")

    print(f"Values (rules from {where(m.per_pr)}, VALUE_RULES)")
    for name, text in m.VALUE_RULES.items():
        value = row[name]
        value = "blank" if value is None else "yes" if value is True else "no" if value is False else value
        print(f"  {name:24} {value}\n      {text}")


if __name__ == "__main__":
    sys.exit(main())
