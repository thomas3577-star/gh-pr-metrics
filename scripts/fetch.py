"""Fetch pull requests from GitHub with gh and save one file per repo in data/.

Usage (from the repo folder):
  python scripts/fetch.py --mode full
  python scripts/fetch.py --mode incremental

full         For every repo, fetch every PR updated since history_start (minus one
             day), plus every open PR, and replace that repo's saved file.
incremental  For each repo, fetch PRs updated since that repo's last successful
             fetch started, minus one day. A repo with no saved file yet (newly
             added) gets a full fetch automatically.

Saved files: data/prs-<owner>-<name>.json, GitHub's answer for each PR as-is.
Each repo's file is replaced only when that repo has been fetched completely,
so a failed run never damages saved data, and repos already done are kept.

Exit codes: 0 ok, 2 setup or config problem, 4 GitHub problem.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PAGE_SIZES = (50, 25, 12)  # smaller pages are tried when GitHub times out
RETRY_WAIT = 10            # seconds before each retry
TEMPORARY = ("502", "503", "504", "timeout", "timed out", "something went wrong")
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
    nodes { state submittedAt author { login __typename } }
  }
"""

QUERY = """
query($owner: String!, $name: String!, $states: [PullRequestState!], $cursor: String, $size: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $size, after: $cursor, states: $states,
                 orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { %s }
    }
  }
}
""" % PR_FIELDS


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

def repo_file(data_dir, repo):
    # metrics.py's load_data() builds the same file name: change both together.
    return Path(data_dir) / f"prs-{repo.replace('/', '-')}.json"


def load_saved(path):
    """Saved data for one repo, None if there is none, or "damaged"."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return "damaged"


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


_size = 0  # index into PAGE_SIZES; once GitHub needs smaller pages, keep using them


def query_page(host, owner, name, states, cursor):
    """One page of PRs. On GitHub's temporary errors, retries with smaller pages."""
    global _size
    while True:
        args = ["api", "graphql", "--hostname", host, "-f", f"query={QUERY}",
                "-f", f"owner={owner}", "-f", f"name={name}", "-F", f"size={PAGE_SIZES[_size]}"]
        for s in states:
            args += ["-f", f"states[]={s}"]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        result = gh(args)
        body = json.loads(result.stdout) if result.returncode == 0 else {}
        if result.returncode == 0 and not body.get("errors"):
            break
        error = (result.stderr.strip() if result.returncode != 0 else
                 "; ".join(e.get("message", "?") for e in body["errors"]))
        if not any(t in error.lower() for t in TEMPORARY):
            stop(4, f"GitHub refused the request for {owner}/{name}: {error}")
        if _size == len(PAGE_SIZES) - 1:
            stop(4, f"GitHub kept failing for {owner}/{name}: {error}. Try again later.")
        _size += 1
        print(f"  GitHub busy on {owner}/{name}, retrying with {PAGE_SIZES[_size]} PRs "
              f"per request in {RETRY_WAIT} s...", flush=True)
        time.sleep(RETRY_WAIT)
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


# ---------- plan ----------

def plan_repos(cfg, mode, data_dir):
    """How to fetch each repo, as a list of (repo, path, saved, description).
    saved is the repo's saved data for an incremental fetch, or None for a full fetch.
    Full mode: every repo in full. Incremental mode: a repo with no saved file, or a
    damaged one, is fetched in full; stops if host or history_start has changed."""
    plan = []
    for repo in cfg["repos"]:
        path = repo_file(data_dir, repo)
        saved = load_saved(path) if mode == "incremental" else None
        if saved == "damaged":
            plan.append((repo, path, None, "full (saved file was damaged)"))
        elif saved is None:
            plan.append((repo, path, None, "full" if mode == "full" else "full (new repo)"))
        else:
            changed = [k for k in ("host", "history_start") if saved["meta"].get(k) != cfg[k]]
            if changed:
                stop(2, f"settings changed since the last full fetch ({', '.join(changed)}). "
                        "Run a full fetch.")
            plan.append((repo, path, saved, "incremental"))
    return plan


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Fetch PRs with gh into data/, one file per repo.")
    ap.add_argument("--mode", choices=["full", "incremental"], required=True)
    ap.add_argument("--config", default="pr-metrics.config.toml")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    cfg = load_config(args.config)
    start_of_history = (datetime.fromisoformat(cfg["history_start"]).replace(tzinfo=timezone.utc)
                        - OVERLAP)  # one extra day covers any time-zone offset

    plan = plan_repos(cfg, args.mode, args.data_dir)  # decided before fetching anything
    check_signed_in(cfg["host"])
    print(f"Fetching from {cfg['host']}.")
    for repo, path, saved, how in plan:
        started = datetime.now(timezone.utc).replace(microsecond=0)
        if saved:
            since = parse_time(saved["meta"]["last_success_started_at"]) - OVERLAP
            batch = fetch_repo(cfg["host"], repo, since)
            prs, runs = dict(saved["prs"]), saved["meta"].get("runs", [])
        else:
            since = start_of_history
            batch = fetch_repo(cfg["host"], repo, since)
            # Open PRs untouched since history_start would otherwise be missed.
            seen = {pr["number"] for pr in batch}
            batch += [pr for pr in fetch_repo(cfg["host"], repo, None, ["OPEN"])
                      if pr["number"] not in seen]
            prs, runs = {}, []
        for pr in batch:
            prs[f"{repo}#{pr['number']}"] = pr
        runs.append({"mode": how, "started": iso(started),
                     "finished": iso(datetime.now(timezone.utc).replace(microsecond=0)),
                     "prs_fetched": len(batch)})
        save(path, {"meta": {"host": cfg["host"], "repo": repo, "history_start": cfg["history_start"],
                             "last_success_started_at": iso(started), "runs": runs[-RUNS_KEPT:]},
                    "prs": prs})
        print(f"  {repo}: {how}, {len(batch)} PRs fetched, {len(prs)} saved")


if __name__ == "__main__":
    main()
