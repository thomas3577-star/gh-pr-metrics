"""Turn each results-<owner>-<name>.json in a run folder into report-<owner>-<name>.html.

Usage (from the repo folder):
  python scripts/report.py output/20261116-083143

One report per repo. Does no calculations: every number comes from the results
files written by metrics.py. Each page is a single self-contained file that
works offline.

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

# Each section: question, its rows (label, measure key), and any extras:
# "benchmark" adds the PR size benchmark line; "activity_row" adds the
# time-since-last-activity row for open PRs.
SECTIONS = [
    ("1. How long does a PR take to merge?", [
        ("Time to merge", "time_to_merge_days")], set()),
    ("2. Where do PRs spend the most time?", [
        ("Draft", "stage_draft_days"),
        ("Waiting for first review", "stage_wait_first_review_days"),
        ("In review", "stage_in_review_days"),
        ("Waiting to merge", "stage_wait_to_merge_days"),
        ("Never formally reviewed", "never_reviewed")], set()),
    ("3. Are reviews skipped?", [
        ("Merged without approval", "merged_without_approval")], set()),
    ("4. Are merged changes stable?", [
        ("Reverted (minimum)", "reverted_minimum")], set()),
    ("5. Are PRs small enough to review well?", [
        ("Lines changed", "size_lines")], {"benchmark"}),
    ("6. Is unfinished work piling up?", [
        ("Open PRs at period end", "open_prs_at_end"),
        ("Open PR age at period end", "open_pr_age_days"),
        ("Closed without merging", "closed_without_merging")], {"activity_row"}),
]

CSS = """
body{font-family:system-ui,Segoe UI,Arial,sans-serif;color:#222;max-width:1100px;margin:24px auto;padding:0 16px}
h1{font-size:22px;font-weight:600;margin:0}h2{font-size:16px;margin:28px 0 6px}
.m{color:#666;font-size:13px}table{border-collapse:collapse;font-size:13px;width:100%}
.wrap{overflow-x:auto}td,th{padding:6px 8px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap}
th{color:#666;font-weight:500}td:first-child,th:first-child{text-align:left;white-space:normal;min-width:190px}
.ip{background:#fff4d6;color:#7a5200;font-size:11px;padding:1px 6px;border-radius:6px}
.better{color:#17803d}.worse{color:#c0392b}.same{color:#666}
select{font-size:13px;margin:0 16px 8px 6px}a{color:#1a5fb4}
.d{display:none}#prs.show .d{display:table-cell}button{font-size:13px;margin-left:12px}
"""

FILTER_JS = """
function f(){var c=document.getElementById('fc').value,a=document.getElementById('fa').value,
s=document.getElementById('fs').value;
document.querySelectorAll('#prs tr[data-c]').forEach(function(r){
r.style.display=((c==='all'||r.dataset.c===c)&&(a==='all'||r.dataset.a===a)
&&(s==='all'||r.dataset.s===s))?'':'none';});}
function csv(){var out=[];document.querySelectorAll('#prs tr').forEach(function(r){
if(r.style.display==='none')return;var cells=[];r.querySelectorAll('th,td').forEach(function(c){
cells.push('"'+c.textContent.replace(/"/g,'""')+'"');});out.push(cells.join(','));});
var b=new Blob(['\\ufeff'+out.join('\\r\\n')],{type:'text/csv'}),l=document.createElement('a');
l.href=URL.createObjectURL(b);l.download=document.title.replace(/[^\\w-]+/g,'-')+'.csv';l.click();}
"""


def stop(message):
    print(f"STOPPED: {message}", file=sys.stderr)
    sys.exit(2)


def e(text):
    return html.escape(str(text))


def tz_from_offset(offset):
    """Time zone for an offset written like "+05:30"."""
    sign = 1 if offset[0] == "+" else -1
    return timezone(sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6])))


def local_time(iso, offset):
    return datetime.fromisoformat(iso).astimezone(tz_from_offset(offset)).strftime(
        f"%d %b %Y, %H:%M (UTC{offset})")


def cell(m):
    if isinstance(m, int):
        return str(m)
    if "value" in m:
        return str(m["value"])
    if "median" in m:
        return "no PRs" if not m["count"] else f"{m['median']:g} · {m['p75']:g} ({m['count']})"
    return "none" if not m["of"] else f"{m['count']} of {m['of']} ({m['pct']}%)"


def marker(col, key):
    mark = col.get("markers", {}).get(key)
    sym = {"better": "▼", "worse": "▲", "same": "="}.get(mark)
    return f' <span class="{mark}" title="{mark} than the period before">{sym}</span>' if sym else ""


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


def fmt_time(iso, offset):
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone(tz_from_offset(offset)).strftime("%Y-%m-%d %H:%M")


def fmt_days(v):
    return "" if v is None else f"{v:.2f}"


TIME_HEAD = ["Opened", "Ready for review", "First review", "Last approval", "Merged or closed"]
DAYS_HEAD = ["Draft (d)", "Waiting for first review (d)", "In review (d)", "Waiting to merge (d)"]
STATUS = {"open": "Open", "merged": "Merged", "closed_unmerged": "Closed without merging"}


def pr_list(prs, cols, offset):
    authors = sorted({r["author"] for r in prs}, key=str.lower)
    opt_c = "".join(f'<option value="{e(c["label"])}">{e(c["label"])}</option>' for c in reversed(cols))
    opt_a = "".join(f'<option value="{e(a)}">{e(a)}</option>' for a in authors)
    order = {c["label"]: i for i, c in enumerate(cols)}
    rows = ""
    for r in sorted(prs, key=lambda r: (order.get(r["column"], len(cols)), r["key"]), reverse=True):
        col = r["column"] or "Still open"
        status = STATUS[r["outcome"]]
        detail = [fmt_time(r["created"], offset), fmt_time(r["ready_at"], offset),
                  fmt_time(r["first_review_at"], offset), fmt_time(r["last_approval_at"], offset),
                  fmt_time(r["merged"] or r["closed"], offset),
                  fmt_days(r["draft_days"]), fmt_days(r["wait_first_review_days"]),
                  fmt_days(r["in_review_days"]), fmt_days(r["wait_to_merge_days"])]
        rows += (f'<tr data-c="{e(col)}" data-a="{e(r["author"])}" data-s="{e(status)}">'
                 f'<td><a href="{e(r["url"])}">{e(r["key"].split("/", 1)[-1])} {e(r["title"])}</a></td>'
                 f'<td>{e(r["author"])}</td><td>{e(col)}</td>'
                 f'<td>{e(status)}</td><td>{fmt_days(r["time_to_merge_days"])}</td>'
                 f'<td>{r["size_lines"]}</td><td>{"yes" if r["approved"] else "no"}</td>'
                 f'<td>{"yes" if r["reverted"] else "no"}</td>'
                 + "".join(f'<td class="d">{e(v)}</td>' for v in detail) + "</tr>")
    head = ("<th>PR</th><th>Author</th><th>Period</th><th>Status</th><th>Time to merge (d)</th>"
            "<th>Lines</th><th>Approved</th><th>Reverted</th>"
            + "".join(f'<th class="d">{e(h)} (UTC{e(offset)})</th>' for h in TIME_HEAD)
            + "".join(f'<th class="d">{e(h)}</th>' for h in DAYS_HEAD))
    opt_s = "".join(f'<option value="{e(v)}">{e(v)}</option>' for v in STATUS.values())
    return (f'<div>Period<select id="fc" onchange="f()"><option value="all">All</option>'
            f'<option value="Still open">Still open</option>{opt_c}</select>'
            f'Status<select id="fs" onchange="f()"><option value="all">All</option>{opt_s}</select>'
            f'Author<select id="fa" onchange="f()"><option value="all">All authors</option>{opt_a}</select>'
            f'<label><input type="checkbox" onchange="document.getElementById(\'prs\').classList'
            f'.toggle(\'show\',this.checked)"> Show calculation details</label> '
            f'<button onclick="csv()">Download shown rows as CSV</button></div>'
            f'<p class="m">Period: the period the PR was merged or closed in; still-open PRs have no '
            f'period yet. Status: Open (not merged or closed yet), Merged, or Closed without merging.</p>'
            f'<p class="m">Times are local (UTC{e(offset)}). Each period\'s median and p75 can be checked in '
            f'Excel: filter to the period, download, then use =MEDIAN() and =PERCENTILE.INC(range,0.75).</p>'
            f'<div class="wrap"><table id="prs"><tr>{head}</tr>{rows}</table></div>')


def build_page(res, run_dir):
    n, summ = res["notes"], res["summary"]
    cols = summ["columns"]
    people = n["authors"] if n["authors"] == "everyone" else f"{len(n['authors'])} listed"
    legend = "Each cell: median · p75 (PR count), or count of total (%). Times in calendar days."
    if n["compared"]:
        legend += (f" Lower is better. ▼ better, ▲ worse, = same: {n['compared'][0]} compared with "
                   f"{n['compared'][1]}. Read over several periods: one period alone is often noise.")
    parts = [
        f"<h1>PR metrics: {e(n['repo'])}</h1>",
        f'<p class="m">{e(n["host"])} · People: {e(people)} · {e(n["scope"])} · '
        f'Data as of {e(local_time(n["data_as_of"], n["utc_offset"]))} · Run {e(run_dir.name)}</p>',
        f'<p class="m">{e(legend)}</p>',
    ]
    for title, rows, extras in SECTIONS:
        parts.append(f"<h2>{e(title)}</h2>")
        parts.append(column_table(cols, rows, summ["current_time_since_last_activity_days"],
                                  extra_row="activity_row" in extras))
        if "benchmark" in extras:
            links = "; ".join(f'<a href="{u}">{e(t)}</a>' for t, u in LINKS.items())
            parts.append(f'<p class="m">Benchmark: elite teams\' PRs are under '
                         f'{summ["elite_pr_lines"]} lines ({links}). A comparison, not a pass or fail.</p>')
    parts.append("<h2>Notes on the data</h2>"
                 + "".join(f"<p>{e(msg)}</p>" for msg in n["messages"]))
    parts.append("<h2>PRs counted</h2>" + pr_list(res["prs"], cols, n["utc_offset"]))
    parts.append('<p class="m">Definitions: METRICS.md in the gh-pr-metrics repo.</p>')
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f"<title>PR metrics {e(n['repo'])} {e(run_dir.name)}</title><style>{CSS}</style></head>"
            f"<body>{''.join(parts)}<script>{FILTER_JS}</script></body></html>")


def main():
    if len(sys.argv) != 2:
        stop("give the run folder, e.g. python scripts/report.py output/20261116-083143")
    run_dir = Path(sys.argv[1])
    files = sorted(run_dir.glob("results-*.json"))
    if not files:
        stop(f"no results files in {run_dir}. Run scripts/metrics.py first.")
    for f in files:
        res = json.loads(f.read_text(encoding="utf-8"))
        out = run_dir / f.name.replace("results-", "report-", 1).replace(".json", ".html")
        out.write_text(build_page(res, run_dir), encoding="utf-8")
        print(f"Report: {out.as_posix()}")


if __name__ == "__main__":
    main()
