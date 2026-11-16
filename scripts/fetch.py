"""Fetch pull requests from GitHub with gh and save them to data/prs.json.

Usage (from the repo folder):
  python scripts/fetch.py --mode full
  python scripts/fetch.py --mode incremental

full         Fetch every PR updated since history_start (minus one day), plus
             every open PR.
             Replaces the saved data.
incremental  Fetch PRs updated since the last successful run started, minus
             one day. Each fetched PR replaces its saved copy.

Saves GitHub's answer for each PR as-is; all calculation happens in report.py.
The saved file is only replaced when every repo has been fetched, so a failed
run never damages saved data.

Exit codes: 0 ok, 2 setup or config problem, 4 GitHub problem.
"""

import argparse
import json
import os
import subprocess
import sys
import tomllib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PAGE_SIZE = 50
OVERLAP = timedelta(days=1)
RUNS_KEPT = 20

PR_FIELDS = """
  number title body url state isDraft baseRefName
  createdAt updatedAt mergedAt closedAt additions deletions
  author { login __typename }
  mergeCommit { oid }
  timelineItems(first: 20, itemTypes: [READY_FOR_REVIEW_EVENT]) {
    nodes { ... on ReadyForReviewEvent { createdAt } }
  }
  reviews(first: 100) {
    totalCount
    nodes { state submittedAt author { login } }
  }
"""

QUERY = """
query($owner: String!, $name: String!, $states: [PullRequestState!], $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: %d, after: $cursor, states: $states,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}
""" % (PAGE_SIZE, PR_FIELDS)


def stop(code, message):
    print(f"STOPPED: {message}", file=sys.stderr)
    sys.exit(code)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


# ---------- config ----------

def load_config(path):
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        stop(2, f"config file not found: {path}. Copy pr-metrics.config.sample.toml "
                f"to {path} and fill in your values.")
    except tomllib.TOMLDecodeError as e:
        stop(2, f"config file {path} is not valid: {e}")

    host = cfg.get("host")
    if not isinstance(host, str) or not host.strip():
        stop(2, "config 'host' must be set, e.g. host = \"github.com\"")
    repos = cfg.get("repos")
    if not isinstance(repos, list) or not repos:
        stop(2, "config 'repos' must list at least one repo, e.g. repos = [\"owner/name\"]")
    for r in repos:
        if not isinstance(r, str) or r.count("/") != 1 or r.startswith("owner/"):
            stop(2, f"config 'repos' entry '{r}' must be a real repo written as owner/name")
    if not isinstance(cfg.get("history_start"), date) or isinstance(cfg.get("history_start"), datetime):
        stop(2, "config 'history_start' must be a date, e.g. history_start = 2026-05-18")
    return {"host": host.strip(), "repos": repos, "history_start": cfg["history_start"].isoformat()}


# ---------- saved data ----------

def load_saved(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        stop(2, f"saved data {path} is damaged. Run a full fetch to rebuild it.")


def save(path, data):
    """Write to a temporary file, then swap it in with one rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ---------- GitHub via gh ----------

def gh(args):
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        stop(2, "gh is not installed or not on PATH. Install GitHub CLI: https://cli.github.com")


def check_signed_in(host):
    result = gh(["auth", "status", "--hostname", host])
    if result.returncode != 0:
        stop(2, f"gh is not signed in to {host}. Run: gh auth login --hostname {host}")


def query_page(host, owner, name, states, cursor):
    args = ["api", "graphql", "--hostname", host,
            "-f", f"query={QUERY}", "-f", f"owner={owner}", "-f", f"name={name}"]
    for s in states:
        args += ["-f", f"states[]={s}"]
    if cursor:
        args += ["-f", f"cursor={cursor}"]
    result = gh(args)
    if result.returncode != 0:
        stop(4, f"GitHub refused the request for {owner}/{name}: {result.stderr.strip()}")
    body = json.loads(result.stdout)
    if body.get("errors"):
        stop(4, f"GitHub error for {owner}/{name}: "
                + "; ".join(e.get("message", "?") for e in body["errors"]))
    repo = (body.get("data") or {}).get("repository")
    if repo is None:
        stop(4, f"repo {owner}/{name} not found, or this gh sign-in cannot see it")
    return repo["pullRequests"]


def fetch_repo(host, repo, since, states=()):
    """PRs in newest-updated order, stopping at the first one older than `since` (None = no limit)."""
    owner, name = repo.split("/")
    prs, cursor = [], None
    while True:
        page = query_page(host, owner, name, states, cursor)
        for pr in page["nodes"]:
            if since and parse_time(pr["updatedAt"]) < since:
                return prs
            prs.append(pr)
        if not page["pageInfo"]["hasNextPage"]:
            return prs
        cursor = page["pageInfo"]["endCursor"]


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Fetch PRs with gh into data/prs.json.")
    ap.add_argument("--mode", choices=["full", "incremental"], required=True)
    ap.add_argument("--config", default="pr-metrics.config.toml")
    ap.add_argument("--data", default="data/prs.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    saved = load_saved(args.data)
    started = datetime.now(timezone.utc).replace(microsecond=0)

    if args.mode == "incremental":
        if saved is None:
            stop(2, "no saved data yet. Run a full fetch first.")
        meta = saved["meta"]
        changed = [k for k in ("host", "repos", "history_start") if meta.get(k) != cfg[k]]
        if changed:
            stop(2, f"settings changed since the last full fetch ({', '.join(changed)}). "
                    "Run a full fetch.")
        since = parse_time(meta["last_success_started_at"]) - OVERLAP
        prs = dict(saved["prs"])
    else:
        # One extra day covers any time-zone offset from UTC.
        since = datetime.fromisoformat(cfg["history_start"]).replace(tzinfo=timezone.utc) - OVERLAP
        prs = {}

    check_signed_in(cfg["host"])
    print(f"{args.mode.capitalize()} fetch from {cfg['host']}, PRs updated since {iso(since)}.")

    fetched = 0
    for repo in cfg["repos"]:
        batch = fetch_repo(cfg["host"], repo, since)
        if args.mode == "full":
            # Open PRs untouched since history_start would otherwise be missed.
            seen = {pr["number"] for pr in batch}
            batch += [pr for pr in fetch_repo(cfg["host"], repo, None, ["OPEN"])
                      if pr["number"] not in seen]
        for pr in batch:
            prs[f"{repo}#{pr['number']}"] = pr
        fetched += len(batch)
        print(f"  {repo}: {len(batch)} PRs")

    runs = (saved or {}).get("meta", {}).get("runs", []) if args.mode == "incremental" else []
    runs.append({"mode": args.mode, "started": iso(started),
                 "finished": iso(datetime.now(timezone.utc).replace(microsecond=0)),
                 "status": "ok", "prs_fetched": fetched})
    data = {
        "meta": {**cfg, "last_success_started_at": iso(started), "runs": runs[-RUNS_KEPT:]},
        "prs": prs,
    }
    save(args.data, data)
    print(f"Saved {len(prs)} PRs in total to {args.data}.")


if __name__ == "__main__":
    main()
