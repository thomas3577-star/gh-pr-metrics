"""Turn a run folder's results.json (and the agent's insights.md) into report.html.

Usage (from the repo folder):
  python scripts/report.py output/20261116-083143

Does no calculations: every number comes from results.json, written by
metrics.py. The page is a single self-contained file that works offline.

Exit codes: 0 ok, 2 setup problem.
"""

import html
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LINKS = {
    "LinearB 2026": "https://linearb.io/library/engineering-benchmarks-and-research",
    "Google review guidance": "https://google.github.io/eng-practices/review/developer/small-cls.html",
}

SECTIONS = [
    ("1. How long does a PR take to merge?", [
        ("Time to merge", "time_to_merge_days")]),
    ("2. Where do PRs spend the most time?", [
        ("Draft", "stage_draft_days"),
        ("Waiting for first review", "stage_wait_first_review_days"),
        ("In review", "stage_in_review_days"),
        ("Waiting to merge", "stage_wait_to_merge_days"),
        ("Never formally reviewed", "never_reviewed")]),
    ("3. Are reviews skipped?", [
        ("Merged without approval", "merged_without_approval")]),
    ("4. Are merged changes stable?", [
        ("Reverted (minimum)", "reverted_minimum")]),
    ("5. Are PRs small enough to review well?", [
        ("Lines changed", "size_lines")]),
    ("6. Is unfinished work piling up?", [
        ("Open PR age at period end", "open_pr_age_days"),
        ("Closed without merging", "closed_without_merging")]),
]

CSS = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;color:#222;max-width:1100px;margin:24px auto;padding:0 16px}
h1{font-size:22px;font-weight:600;margin:0}h2{font-size:16px;margin:28px 0 6px}
.m{color:#666;font-size:13px}table{border-collapse:collapse;font-size:13px;width:100%}
.wrap{overflow-x:auto}td,th{padding:6px 8px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap}
th{color:#666;font-weight:500}td:first-child,th:first-child{text-align:left;white-space:normal;min-width:190px}
.ip{background:#fff4d6;color:#7a5200;font-size:11px;padding:1px 6px;border-radius:6px}
.better{color:#17803d}.worse{color:#c0392b}.same{color:#666}
.obs{border:1px solid #d6d6ff;background:#f6f6ff;border-radius:8px;padding:10px 16px}
select{font-size:13px;margin:0 16px 8px 6px}a{color:#1a5fb4}
"""

FILTER_JS = """
function f(){var c=document.getElementById('fc').value,a=document.getElementById('fa').value;
document.querySelectorAll('#prs tr[data-c]').forEach(function(r){
r.style.display=((c==='all'||r.dataset.c===c)&&(a==='all'||r.dataset.a===a))?'':'none';});}
"""


def stop(message):
    print(f"STOPPED: {message}", file=sys.stderr)
    sys.exit(2)


def e(text):
    return html.escape(str(text))


def local_time(iso, offset):
    sign = 1 if offset[0] == "+" else -1
    tz = timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))
    return datetime.fromisoformat(iso).astimezone(tz).strftime(f"%d %b %Y, %H:%M (UTC{offset})")


def cell(m):
    if isinstance(m, int):
        return str(m)
    if "median" in m:
        return "no PRs" if not m["count"] else f"{m['median']:g} · {m['p75']:g} ({m['count']})"
    return "none" if not m["of"] else f"{m['count']} of {m['of']} ({m['pct']}%)"


def marker(col, key):
    mark = col.get("markers", {}).get(key)
    sym = {"better": "▼", "worse": "▲", "same": "="}.get(mark)
    return f' <span class="{mark}" title="{mark} than the period before">{sym}</span>' if sym else ""


def observations(run_dir):
    path = run_dir / "insights.md"
    if not path.exists():
        return '<p class="m">No AI observations for this run.</p>'
    items = [ln.strip()[2:] for ln in path.read_text(encoding="utf-8").splitlines()
             if ln.strip().startswith(("- ", "* "))]
    if not items:
        return '<p class="m">No AI observations for this run.</p>'
    bullets = "".join(f"<li>{e(i)}</li>" for i in items)
    return (f'<div class="obs"><p class="m">AI-written observations. Check before acting.</p>'
            f"<ul>{bullets}</ul></div>")


def column_table(cols, rows, current_activity, extra_row=False):
    head = "".join(
        f"<th>{e(c['label'])}{' <span class=ip>in progress</span>' if c['in_progress'] else ''}"
        f"{' <span class=m>(part)</span>' if c['partial'] else ''}</th>" for c in cols)
    body = ""
    for label, key in rows:
        tds = "".join(f"<td>{cell(c[key])}{marker(c, key)}</td>" for c in cols)
        body += f"<tr><td>{e(label)}</td>{tds}</tr>"
    if extra_row:
        tds = "".join(f"<td>{cell(current_activity)}</td>" if c["in_progress"]
                      else '<td class="m">n/a</td>' for c in cols)
        body += f"<tr><td>Time since last activity (open PRs now)</td>{tds}</tr>"
    return f'<div class="wrap"><table><tr><th></th>{head}</tr>{body}</table></div>'


def pr_list(prs, cols):
    authors = sorted({r["author"] for r in prs}, key=str.lower)
    opt_c = "".join(f'<option value="{e(c["label"])}">{e(c["label"])}</option>' for c in reversed(cols))
    opt_a = "".join(f'<option value="{e(a)}">{e(a)}</option>' for a in authors)
    order = {c["label"]: i for i, c in enumerate(cols)}
    rows = ""
    for r in sorted(prs, key=lambda r: (order.get(r["column"], len(cols)), r["key"]), reverse=True):
        ttm = f"{r['time_to_merge_days']:.1f}" if r["time_to_merge_days"] is not None else ""
        col = r["column"] or "open"
        rows += (f'<tr data-c="{e(col)}" data-a="{e(r["author"])}">'
                 f'<td><a href="{e(r["url"])}">{e(r["key"].split("/", 1)[-1])} {e(r["title"])}</a></td>'
                 f'<td>{e(r["author"])}</td><td>{e(col)}</td>'
                 f'<td>{e(r["outcome"].replace("_", " "))}</td><td>{ttm}</td><td>{r["size_lines"]}</td>'
                 f'<td>{"yes" if r["approved"] else "no"}</td><td>{"yes" if r["reverted"] else "no"}</td></tr>')
    return (f'<div>Period<select id="fc" onchange="f()"><option value="all">All</option>'
            f'<option value="open">Open now</option>{opt_c}</select>Author<select id="fa" onchange="f()">'
            f'<option value="all">All authors</option>{opt_a}</select></div>'
            f'<div class="wrap"><table id="prs"><tr><th>PR</th><th>Author</th><th>Period</th><th>Outcome</th>'
            f'<th>Days to merge</th><th>Lines</th><th>Approved</th><th>Reverted</th></tr>{rows}</table></div>')


def main():
    if len(sys.argv) != 2:
        stop("give the run folder, e.g. python scripts/report.py output/20261116-083143")
    run_dir = Path(sys.argv[1])
    try:
        res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        stop(f"no results.json in {run_dir}. Run scripts/metrics.py first.")

    n, summ = res["notes"], res["summary"]
    cols = summ["columns"]
    people = n["authors"] if n["authors"] == "everyone" else f"{len(n['authors'])} listed"
    legend = "Each cell: median · p75 (PR count), or count of total (%). Times in calendar days."
    if n["compared"]:
        legend += (f" Lower is better. ▼ better, ▲ worse, = same: {n['compared'][0]} compared with "
                   f"{n['compared'][1]}. Read over several periods: one period alone is often noise.")
    parts = [
        "<h1>PR metrics report</h1>",
        f'<p class="m">{e(n["host"])} · {e(", ".join(n["repos"]))} · People: {e(people)} · '
        f'{e(n["scope"])} · Data as of {e(local_time(n["data_as_of"], n["utc_offset"]))} · '
        f'Run {e(run_dir.name)}</p>',
        f'<p class="m">{e(legend)}</p>',
        "<h2>Observations</h2>", observations(run_dir),
    ]
    for title, rows in SECTIONS:
        parts.append(f"<h2>{e(title)}</h2>")
        parts.append(column_table(cols, rows, summ["current_time_since_last_activity_days"],
                                  extra_row=title.startswith("6.")))
        if title.startswith("5."):
            links = "; ".join(f'<a href="{u}">{e(t)}</a>' for t, u in LINKS.items())
            parts.append(f'<p class="m">Benchmark: elite teams\' PRs are under '
                         f'{summ["elite_pr_lines"]} lines ({links}). A comparison, not a pass or fail.</p>')
    parts.append("<h2>Notes on the data</h2>"
                 + "".join(f"<p>{e(msg)}</p>" for msg in n["messages"]))
    parts.append("<h2>PRs counted</h2>" + pr_list(res["prs"], cols))
    parts.append('<p class="m">Definitions: METRICS.md in the gh-pr-metrics repo.</p>')

    page = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f"<title>PR metrics {e(run_dir.name)}</title><style>{CSS}</style></head>"
            f"<body>{''.join(parts)}<script>{FILTER_JS}</script></body></html>")
    out = run_dir / "report.html"
    out.write_text(page, encoding="utf-8")
    print(f"Report: {out.as_posix()}")


if __name__ == "__main__":
    main()
