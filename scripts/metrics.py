"""Calculate every number defined in METRICS.md from data/prs.json.

Usage (from the repo folder), one of:
  python scripts/metrics.py                          the last `show_last` columns
  python scripts/metrics.py --since-start            every column from history_start
  python scripts/metrics.py --last "3 months"        columns in the last 3 months (or "6 weeks")
  python scripts/metrics.py --from 2026-11-02 --to 2026-11-15
                                                     that range as one column, beside the
                                                     same number of days just before it

Columns follow `group_by` ("1 week", "2 weeks" or "month") in the config, lined
up with `group_starts_on`. Reads only saved data (no GitHub access).
Step 1 works out each PR's values; step 2 the median, p75 and counts per column.
Creates a run folder output/YYYYMMDD-HHMMSS (local time), writes results.json
into it, and prints a summary for the agent to repeat word for word.

Exit codes: 0 ok, 2 setup, config or range problem.
"""

import argparse
import calendar
import json
import re
import statistics
import sys
import tomllib
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ELITE_PR_LINES = 100  # METRICS.md, PR size, references [1][2][7]

# Measures where lower is clearly better, so the report marks better or worse.
# Draft time and closed-without-merging are left out on purpose.
MARKED = {
    "time_to_merge_days": ("Time to merge", "median d"),
    "stage_wait_first_review_days": ("Waiting for first review", "median d"),
    "stage_in_review_days": ("In review", "median d"),
    "stage_wait_to_merge_days": ("Waiting to merge", "median d"),
    "merged_without_approval": ("Merged without approval", "%"),
    "reverted_minimum": ("Reverted (minimum)", "%"),
    "size_lines": ("PR size", "median lines"),
    "open_pr_age_days": ("Open PR age at column end", "median d"),
}


def stop(code, message):
    print(f"STOPPED: {message}", file=sys.stderr)
    sys.exit(code)


def when(text):
    return datetime.fromisoformat(text) if text else None


def days(start, end):
    return (end - start).total_seconds() / 86400


def prs(n):
    return f"{n} PR" if n == 1 else f"{n} PRs"


# ---------- config and data ----------

def load_config(path):
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        stop(2, f"config file not found: {path}. Copy pr-metrics.config.sample.toml "
                f"to {path} and fill in your values.")
    except tomllib.TOMLDecodeError as e:
        stop(2, f"config file {path} is not valid: {e}")

    def a_date(key):
        v = cfg.get(key)
        if not isinstance(v, date) or isinstance(v, datetime):
            stop(2, f"config '{key}' must be a date, e.g. {key} = 2026-05-18")
        return v

    authors = cfg.get("authors", [])
    if not isinstance(authors, list) or not all(isinstance(a, str) for a in authors):
        stop(2, "config 'authors' must be a list of logins, or [] for everyone")
    group_by = cfg.get("group_by")
    if group_by not in ("1 week", "2 weeks", "month"):
        stop(2, 'config \'group_by\' must be "1 week", "2 weeks" or "month"')
    show_last = cfg.get("show_last")
    if not isinstance(show_last, int) or show_last < 1:
        stop(2, "config 'show_last' must be a whole number, e.g. show_last = 6")
    m = re.fullmatch(r"([+-])(\d{2}):(\d{2})", str(cfg.get("utc_offset", "")))
    if not m:
        stop(2, "config 'utc_offset' must look like \"+05:30\"")
    sign = 1 if m[1] == "+" else -1
    tz = timezone(sign * timedelta(hours=int(m[2]), minutes=int(m[3])))
    return {"authors": [a.lower() for a in authors], "history_start": a_date("history_start"),
            "group_by": group_by,
            "group_starts_on": a_date("group_starts_on") if group_by != "month" else None,
            "show_last": show_last, "utc_offset": m[0], "tz": tz}


def load_data(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        stop(2, f"no saved data at {path}. Run scripts/fetch.py first.")
    except json.JSONDecodeError:
        stop(2, f"saved data {path} is damaged. Run a full fetch to rebuild it.")


# ---------- columns ----------

def midnight(d, tz):
    return datetime.combine(d, time(0), tz)


def months_shift(dt, n):
    """Same moment n months later (or earlier), day clipped to the month's length."""
    y, m = divmod(dt.month - 1 + n, 12)
    year, month = dt.year + y, m + 1
    return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1]))


def all_groups(cfg, now):
    """Every group from the one containing history_start up to the one containing now."""
    first = midnight(cfg["history_start"], cfg["tz"])
    groups = []
    if cfg["group_by"] == "month":
        start = first.replace(day=1)
        while start <= now:
            groups.append((start, months_shift(start, 1)))
            start = months_shift(start, 1)
    else:
        length = timedelta(weeks=1 if cfg["group_by"] == "1 week" else 2)
        anchor = midnight(cfg["group_starts_on"], cfg["tz"])
        start = anchor + ((first - anchor) // length) * length
        while start <= now:
            groups.append((start, start + length))
            start += length
    return groups


def label(start, end, is_month):
    last = end - timedelta(days=1)
    if is_month:
        return start.strftime("%b %Y")
    if start.month == last.month:
        return f"{start.day}–{last.day} {last.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')}–{last.day} {last.strftime('%b')}"


def choose_columns(cfg, args, now):
    """List of (start, end, is_month) for the columns this report shows."""
    tz, first = cfg["tz"], midnight(cfg["history_start"], cfg["tz"])
    if args.date_from or args.date_to:
        if not (args.date_from and args.date_to):
            stop(2, "give both --from and --to, e.g. --from 2026-11-02 --to 2026-11-15")
        try:
            a, b = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)
        except ValueError:
            stop(2, "dates must be written YYYY-MM-DD, e.g. 2026-11-02")
        if b < a:
            stop(2, f"--to {b} is before --from {a}")
        start, end = midnight(a, tz), midnight(b + timedelta(days=1), tz)
        if start < first:
            stop(2, f"{a} is before history_start {cfg['history_start']}. Ask for a later date, "
                    "or set an earlier history_start and run a full fetch.")
        return [(start - (end - start), start, False), (start, end, False)]
    groups = all_groups(cfg, now)
    if args.since_start:
        chosen = groups
    elif args.last:
        m = re.fullmatch(r"\s*(\d+)\s*(weeks?|months?)\s*", args.last)
        if not m:
            stop(2, 'write --last like "6 weeks" or "3 months"')
        n = int(m[1])
        since = now - timedelta(weeks=n) if m[2].startswith("week") else months_shift(now, -n)
        chosen = [g for g in groups if g[1] > since]
    else:
        chosen = groups[-cfg["show_last"]:]
    return [(s, e, cfg["group_by"] == "month") for s, e in chosen]


# ---------- step 1: per PR ----------

REF_NUMBER = re.compile(r"(?:([\w.-]+/[\w.-]+))?#(\d+)\b")
REF_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")


def find_reverted(all_prs):
    """Keys of merged PRs that a later merged 'Revert...' PR points to (any author)."""
    by_sha = {}
    for key, pr in all_prs.items():
        if pr.get("mergeCommit"):
            by_sha[(key.split("#")[0], pr["mergeCommit"]["oid"])] = key
    reverted = set()
    for key, pr in all_prs.items():
        if not pr.get("mergedAt") or not pr["title"].lower().startswith("revert"):
            continue
        repo = key.split("#")[0]
        text = f"{pr['title']}\n{pr.get('body') or ''}"
        targets = {f"{r or repo}#{n}" for r, n in REF_NUMBER.findall(text)}
        for sha in REF_SHA.findall(text):
            targets |= {k for (r, full), k in by_sha.items() if r == repo and full.startswith(sha)}
        for t in targets - {key}:
            orig = all_prs.get(t)
            if orig and orig.get("mergedAt") and orig["mergedAt"] <= pr["mergedAt"]:
                reverted.add(t)
    return reverted


def per_pr(key, pr, reverted):
    author = (pr.get("author") or {}).get("login") or "ghost"
    created, merged, closed = when(pr["createdAt"]), when(pr["mergedAt"]), when(pr["closedAt"])
    outcome = "merged" if merged else ("closed_unmerged" if closed else "open")
    ready_events = [when(n["createdAt"]) for n in pr["timelineItems"]["nodes"] if n]
    ready = min(ready_events) if ready_events else created

    # Reviews by someone other than the author, submitted by the time of merge.
    cutoff = merged or datetime.max.replace(tzinfo=timezone.utc)
    others = [r for r in pr["reviews"]["nodes"]
              if r.get("submittedAt") and (r.get("author") or {}).get("login") not in (None, author)
              and when(r["submittedAt"]) <= cutoff]
    first_review = min((when(r["submittedAt"]) for r in others), default=None)
    approvals = [when(r["submittedAt"]) for r in others if r["state"] == "APPROVED"]
    last_approval = max(approvals, default=None)

    row = {
        "key": key, "url": pr["url"], "title": pr["title"], "author": author,
        "outcome": outcome, "created": pr["createdAt"], "merged": pr["mergedAt"],
        "closed": pr["closedAt"], "updated": pr["updatedAt"], "column": None,
        "size_lines": pr["additions"] + pr["deletions"],
        "time_to_merge_days": None, "draft_days": None, "wait_first_review_days": None,
        "in_review_days": None, "wait_to_merge_days": None,
        "approved": bool(last_approval), "reverted": key in reverted,
        "reviews_truncated": pr["reviews"]["totalCount"] > len(pr["reviews"]["nodes"]),
    }
    if merged:
        row["time_to_merge_days"] = days(created, merged)
        row["draft_days"] = max(days(created, ready), 0)
        if first_review:
            row["wait_first_review_days"] = max(days(ready, first_review), 0)
        if first_review and last_approval:
            row["in_review_days"] = max(days(first_review, last_approval), 0)
        if last_approval:
            row["wait_to_merge_days"] = days(last_approval, merged)
    return row


# ---------- step 2: per column ----------

def spread(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"median": None, "p75": None, "count": 0}
    p75 = values[0] if len(values) == 1 else statistics.quantiles(values, n=4, method="inclusive")[2]
    return {"median": round(statistics.median(values), 1), "p75": round(p75, 1), "count": len(values)}


def share(hits, total):
    return {"count": hits, "of": total, "pct": round(100 * hits / total) if total else None}


def per_column(rows, columns, cfg, now):
    first = midnight(cfg["history_start"], cfg["tz"])
    out = []
    for start, end, is_month in columns:
        name = label(start, end, is_month)
        for r in rows:
            t = when(r["merged"] or r["closed"])
            if r["outcome"] != "open" and start <= t < end:
                r["column"] = name
        merged = [r for r in rows if r["column"] == name and r["outcome"] == "merged"]
        closed = [r for r in rows if r["column"] == name and r["outcome"] == "closed_unmerged"]
        in_progress = end > now
        age_at = now if in_progress else end
        open_then = [r for r in rows if when(r["created"]) < age_at
                     and not (when(r["merged"] or r["closed"]) or age_at) < age_at]
        out.append({
            "label": name, "start": start.date().isoformat(),
            "end": (end - timedelta(days=1)).date().isoformat(),
            "in_progress": in_progress, "partial": start < first,
            "time_to_merge_days": spread(r["time_to_merge_days"] for r in merged),
            "stage_draft_days": spread(r["draft_days"] for r in merged),
            "stage_wait_first_review_days": spread(r["wait_first_review_days"] for r in merged),
            "stage_in_review_days": spread(r["in_review_days"] for r in merged),
            "stage_wait_to_merge_days": spread(r["wait_to_merge_days"] for r in merged),
            "never_reviewed": sum(r["wait_first_review_days"] is None for r in merged),
            "merged_without_approval": share(sum(not r["approved"] for r in merged), len(merged)),
            "reverted_minimum": share(sum(r["reverted"] for r in merged), len(merged)),
            "size_lines": spread(r["size_lines"] for r in merged),
            "open_pr_age_days": spread(days(when(r["created"]), age_at) for r in open_then),
            "closed_without_merging": share(len(closed), len(merged) + len(closed)),
        })
    return out


def headline(m):
    """The single value compared between columns: median, or % for shares."""
    return m.get("median") if "median" in m else m.get("pct")


def add_markers(cols):
    """Mark the latest complete column against the one before; return their labels."""
    done = [c for c in cols if not c["in_progress"]]
    if len(done) < 2:
        return None
    last, prev = done[-1], done[-2]
    last["markers"] = {}
    for key in MARKED:
        a, b = headline(prev[key]), headline(last[key])
        if a is not None and b is not None:
            last["markers"][key] = "better" if b < a else "worse" if b > a else "same"
    return [last["label"], prev["label"]]


# ---------- summary for the agent ----------

def cell(m):
    v = headline(m)
    n = m.get("count") if "median" in m else m.get("of")
    return "-" if v is None else f"{v:g}{'%' if 'pct' in m else ''} ({n})"


def summary_lines(cols, compared, activity):
    marked = next((c["markers"] for c in cols if c.get("markers")), {})
    lines = []
    for key, (lab, unit) in MARKED.items():
        mark = marked.get(key)
        tail = (f"  -> {compared[0]} {'same as' if mark == 'same' else mark + ' than'} {compared[1]}"
                if mark else "")
        lines.append(f"  {lab} ({unit}, PR count): "
                     + " | ".join(f"{c['label']} {cell(c[key])}" for c in cols) + tail)
    lines.append(f"  PR size benchmark: elite teams under {ELITE_PR_LINES} lines")
    cur = next((c for c in cols if c["in_progress"]), None)
    if cur:
        lines.append(f"In progress: {cur['label']}, {prs(cur['time_to_merge_days']['count'])} "
                     f"merged so far. Open PRs now: median age {cell(cur['open_pr_age_days'])}; "
                     f"median time since last activity {cell(activity)} (days, PR count)")
    return lines


def plain_notes(n):
    msgs = []
    if n["authors_with_no_prs"]:
        msgs.append("No PRs found for login(s) " + ", ".join(n["authors_with_no_prs"])
                    + ". Check the spelling in the config.")
    if n["reviews_cut_at_100"]:
        msgs.append(f"{prs(len(n['reviews_cut_at_100']))} had over 100 reviews; only the first "
                    "100 were read, so their review times may be slightly off.")
    if n["partial_columns"]:
        msgs.append("Column(s) " + ", ".join(n["partial_columns"]) + " start before history_start, "
                    "so only part of that time is counted.")
    msgs.append(f"Not counted: {prs(n['bot_prs_left_out'])} by bots and "
                f"{prs(n['unlisted_author_prs_left_out'])} by people not in the list.")
    return msgs


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Calculate PR metrics from saved data.")
    ap.add_argument("--config", default="pr-metrics.config.toml")
    ap.add_argument("--data", default="data/prs.json")
    ap.add_argument("--out-dir", default="output")
    rng = ap.add_mutually_exclusive_group()
    rng.add_argument("--since-start", action="store_true")
    rng.add_argument("--last")
    rng.add_argument("--from", dest="date_from")
    ap.add_argument("--to", dest="date_to")
    args = ap.parse_args()

    cfg = load_config(args.config)
    data = load_data(args.data)
    now = datetime.now(timezone.utc).astimezone(cfg["tz"])
    if midnight(cfg["history_start"], cfg["tz"]) > now:
        stop(2, f"history_start {cfg['history_start']} is in the future.")
    columns = choose_columns(cfg, args, now)
    if not columns:
        stop(2, "no columns in that range. Try a longer --last or --since-start.")

    reverted = find_reverted(data["prs"])  # across every saved PR, any author
    rows, bots, not_listed = [], 0, 0
    for key, pr in data["prs"].items():
        author = pr.get("author") or {}
        if author.get("__typename") == "Bot":
            bots += 1
        elif cfg["authors"] and (author.get("login") or "").lower() not in cfg["authors"]:
            not_listed += 1
        else:
            rows.append(per_pr(key, pr, reverted))

    cols = per_column(rows, columns, cfg, now)
    compared = add_markers(cols)
    activity = spread(days(when(r["updated"]), now) for r in rows if r["outcome"] == "open")
    shown = [r for r in rows if r["column"] or r["outcome"] == "open"]
    found = {r["author"].lower() for r in rows}
    first, last = cols[0], cols[-1]
    if args.date_from:
        scope = f"{last['start']} to {last['end']}, beside {first['start']} to {first['end']}"
    else:
        unit = "1 month" if cfg["group_by"] == "month" else cfg["group_by"]
        scope = f"{len(cols)} columns of {unit}, {first['start']} to {last['end']}"
    notes = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "data_as_of": data["meta"]["last_success_started_at"],
        "host": data["meta"]["host"], "repos": data["meta"]["repos"],
        "authors": cfg["authors"] or "everyone", "scope": scope,
        "utc_offset": cfg["utc_offset"], "compared": compared,
        "bot_prs_left_out": bots, "unlisted_author_prs_left_out": not_listed,
        "partial_columns": [c["label"] for c in cols if c["partial"]],
        "reviews_cut_at_100": [r["key"] for r in shown if r["reviews_truncated"]],
        "authors_with_no_prs": sorted(set(cfg["authors"]) - found),
    }
    notes["messages"] = plain_notes(notes)
    results = {
        "summary": {"columns": cols, "current_time_since_last_activity_days": activity,
                    "elite_pr_lines": ELITE_PR_LINES},
        "notes": notes,
        "prs": shown,
    }
    run_dir = Path(args.out_dir) / now.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"PR metrics, data as of {notes['data_as_of']}, {prs(len(shown))} in this report")
    print(f"Report covers: {scope}")
    for line in summary_lines(cols, compared, activity):
        print(line)
    for msg in notes["messages"]:
        print(f"Note: {msg}")
    print(f"Run folder: {run_dir.as_posix()}")


if __name__ == "__main__":
    main()
