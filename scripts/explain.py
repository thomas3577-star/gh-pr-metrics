"""Explain one PR's metrics in plain English: whether it is counted, which period it
falls in, the times and reviews used, each value and the rule behind it, and where
each rule lives in metrics.py.

Usage (from the repo folder; range options are the same as metrics.py):
  python scripts/explain.py --repo cli/cli --pr 14815
  python scripts/explain.py --repo cli/cli --pr 14815 --last "3 months"

Read-only: uses the saved data in data/, never contacts GitHub, writes nothing.
The rules are the docstrings of the functions in metrics.py, so they change with the code.
"""

import argparse
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

import metrics as m


def where(func):
    """File, function and current line range, e.g. metrics.py per_pr (lines 245-300)."""
    lines, start = inspect.getsourcelines(func)
    return f"{Path(inspect.getsourcefile(func)).name} {func.__name__} (lines {start}-{start + len(lines) - 1})"


def rule(func):
    """The function's docstring as one paragraph."""
    return " ".join(inspect.getdoc(func).split())


def value_rules():
    """Each value's rule, from the "name: rule" lines in per_pr's docstring."""
    rules, name = {}, None
    for line in inspect.getdoc(m.per_pr).splitlines():
        head, _, text = line.partition(": ")
        if text and head.isidentifier() and not line.startswith(" "):
            name = head
            rules[name] = text.strip()
        elif name and line.startswith(" "):
            rules[name] += " " + line.strip()
    return rules


def main():
    ap = argparse.ArgumentParser(description="Explain one PR's metrics in plain English.")
    ap.add_argument("--repo", required=True, help="owner/name, as in the config")
    ap.add_argument("--pr", required=True, type=int, help="PR number")
    ap.add_argument("--since-start", action="store_true")
    ap.add_argument("--last", help='e.g. "6 weeks" or "3 months"')
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to", dest="date_to")
    ap.add_argument("--config", default="pr-metrics.config.toml")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    cfg = m.load_config(args.config)
    if args.repo not in cfg["repos"]:
        m.stop(2, f"{args.repo} is not in the config's repos.")
    all_prs, meta = m.load_data(args.data_dir, [args.repo])
    key = f"{args.repo}#{args.pr}"
    tz = cfg["tz"]
    local = lambda iso: m.when(iso).astimezone(tz).strftime("%d %b %Y %H:%M:%S") if iso else "none"
    print(f"{key}")
    print(f"Data as of {local(meta[args.repo]['last_success_started_at'])} (UTC{cfg['utc_offset']}).")
    pr = all_prs.get(key)
    if pr is None:
        print("Not in the saved data. Either it was last updated before history_start "
              f"({cfg['history_start']}), or it was created after the data was fetched.")
        return
    author = (pr.get("author") or {}).get("login") or "ghost"
    print(f"{pr['title']}\n{pr['url']}\nAuthor: {author}\n")

    reason = m.left_out_reason(pr, cfg)
    if reason:
        print(f"NOT COUNTED: {reason}.")
        print(f"Rule ({where(m.left_out_reason)}): {rule(m.left_out_reason)}")
        return

    now = datetime.now(timezone.utc).astimezone(tz)
    columns, _ = m.choose_columns(cfg, args, now)
    row = m.per_pr(key, pr, m.find_reverted(all_prs))
    m.assign_periods([row], columns)
    first, last = m.label(*columns[0]), m.label(*columns[-1])
    print(f"Report range: {first} to {last}.")
    if row["column"]:
        print(f"Counted in period {row['column']} ({row['outcome'].replace('_', ' ')}).")
    elif row["outcome"] == "open":
        print("Still open: it appears in the open PR counts and ages, not in any period's times.")
    else:
        print(f"{row['outcome'].replace('_', ' ').capitalize()} outside the report range, "
              "so it is not in any period.")
    print(f"Rule ({where(m.assign_periods)}): {rule(m.assign_periods)}\n")

    print(f"Times (UTC{cfg['utc_offset']})")
    print(f"  Opened         {local(pr['createdAt'])}")
    events = [n["createdAt"] for n in pr["timelineItems"]["nodes"] if n]
    print(f"  Ready          {local(min(events)) if events else local(pr['createdAt']) + ' (never a draft: opened time used)'}")
    print(f"  Merged         {local(pr['mergedAt'])}")
    if not pr["mergedAt"]:
        print(f"  Closed         {local(pr['closedAt'])}")

    counted = m.counted_reviews(pr, author, m.when(pr["mergedAt"]))
    print(f"\nReviews ({len(pr['reviews']['nodes'])} collected, {len(counted)} count)")
    for r in sorted(pr["reviews"]["nodes"], key=lambda r: r.get("submittedAt") or ""):
        who = (r.get("author") or {}).get("login") or "unknown"
        if who == author:
            who += " (author)"
        elif (r.get("author") or {}).get("__typename") == "Bot":
            who += " (bot)"
        mark = "counts" if any(r is c for c in counted) else "doesn't count"
        print(f"  {local(r.get('submittedAt')):20}  {who:38} {r['state']:18} {mark}")
    print(f"Rule ({where(m.counted_reviews)}): {rule(m.counted_reviews)}\n")

    print(f"Values (rules from {where(m.per_pr)})")
    rules = value_rules()
    shown = {"key", "url", "title", "author", "outcome", "created", "merged", "closed",
             "updated", "column", "ready_at", "first_review_at", "last_approval_at"}
    for name, value in row.items():
        if name in shown:
            continue
        value = "blank" if value is None else ("yes" if value is True else "no" if value is False else value)
        print(f"  {name:24} {value}")
        print(f"      {rules.get(name, 'No rule written for this value in per_pr.')}")


if __name__ == "__main__":
    sys.exit(main())
