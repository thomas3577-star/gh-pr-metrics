# Human Maintainability Review: `scripts/fetch.py`

Review date: 2026-11-17. Source: `scripts/fetch.py` (247 lines, 12 functions). The source was not changed.
Quantitative baseline: `docs/baseline-fetch.md`. Its figures are referenced below, not recalculated.

## What the file does

It downloads pull requests from GitHub using the `gh` command-line tool and saves one JSON file per repo (`data/prs-<owner>-<name>.json`). The other scripts read only these files.

**Flow:**

1. Read and check the config.
2. Plan each repo:
   - **Full mode:** a full fetch.
   - **Incremental mode:**
     - a missing file means a full fetch;
     - an unreadable file means a full fetch;
     - otherwise, fetch PRs updated since the last successful run, minus one day.
   - If `host` or `history_start` differs from what the saved file was built with, stop.
3. Check that `gh` is signed in.
4. For each repo:
   - **Full fetch:** fetch PRs from `history_start` onwards, plus every currently open PR.
   - **Incremental fetch:** merge the new PRs into the saved ones.
5. Then, for every repo:
   - append a run record, keeping the last 20;
   - save atomically (a temporary file, then a rename);
   - print one line.

**Side effects:** runs the `gh` subprocess, waits 10 seconds before retrying temporary GitHub errors (with smaller pages each time), reads and writes files, and prints to stdout and stderr. Exit codes: 2 for setup problems, 4 for GitHub problems.

**What the source can't tell us:**

- whether these scripts will get automated tests (the project has none, by choice);
- how often the saved files are edited by hand;
- whether other tools read `data/`.

## A. Overall assessment

**Maintainable today.** The file reads in execution order, the important rules are named constants (`OVERLAP`, `RUNS_KEPT`, `PAGE_SIZES`, `TEMPORARY`), most functions do one thing, and the docstring matches the behaviour.

There is one real obstacle: the per-repo planning rules are mixed into `main`. There is also one real risk: the saved-file shape is assumed and never checked.

On the baseline:

- **`main`** (42 logical lines, complexity 15): matches the obstacle above.
- **`load_config`** (complexity 13), **the 12 calls to `stop()`** and **the 43 mypy errors:** mostly metric findings with little effect on a human reader.

## B. What should remain unchanged

| Item | Reason |
|---|---|
| Constants at the top | The rules a maintainer tunes are easy to find |
| `save` | A correct atomic write in four lines. It's what guarantees a failed run never damages saved data. |
| `fetch_repo` | A clear paging loop with one stopping rule |
| `load_config` | A flat list of independent checks, each with its own message. Its complexity is a counting effect. |
| `stop()` and the exit-code style | For a command-line script, "print a message and exit" is the simplest correct design. Exceptions would add a handler and change nothing a user sees. |
| `query_page`'s module-level `_size` | Intentional and commented ("once GitHub needs smaller pages, keep using them"). Passing it through `fetch_repo` instead would add a parameter to two functions to remove one documented variable: complexity moved, not removed. |
| `gh`, `check_signed_in`, `iso`, `parse_time`, `repo_file`, `PR_FIELDS`/`QUERY` | Already as simple as they can be |

## C. Meaningful improvement opportunities

### 1. Planning rules are mixed into `main` (moderate benefit)

- **Current problem.** Lines 204–217 build a 4-tuple per repo, where `saved is None` quietly means "full fetch". Lines 223–234 then decide what to fetch again from the same value. The rules most likely to change ("when is a fetch full?", "what does a full fetch include?") are split across two loops.
- **Practical impact.** Take a plausible change: "do a full fetch if the saved file is older than 30 days". An engineer has to work out the tuple convention, change the tuple building, and check that the `if saved:` branch still does the right thing.
- **Simpler alternative.** Move lines 204–217 into `plan_repos(cfg, mode, data_dir)`, which returns the plan list. Optionally add a comment naming the tuple fields. Leave the fetch loop in `main`.
- **Trade-off.** Mostly a move, but it puts every planning rule in one named function that can be read alone. Small cost: one extra function.
- **Recommendation.** Change it. It's a small, low-risk move that groups the rules most likely to be edited.

### 2. The saved-file shape is assumed (risk, small change)

- **Current problem.** `load_saved` (lines 108–115) catches a missing file and invalid JSON. But a file that is valid JSON without `meta` or `prs` crashes at lines 213, 224 or 226 with a Python traceback (exit code 1).
- **Practical impact.** Someone debugging a half-edited or truncated file gets a traceback instead of the documented behaviour ("damaged file, so full fetch").
- **Simpler alternative.** In `load_saved`, return `"damaged"` when `meta` or `prs` is missing (about 2 lines).
- **Trade-off.** Removes a failure mode and adds nothing. It is a **behaviour change**: a crash becomes an automatic full fetch.
- **Recommendation.** Change it, once the behaviour change is approved.

### Considered and not recommended

- **Splitting `query_page`** (complexity 14). Its loop is one readable unit: build the command, run it, succeed or classify the error, wait and retry. Pulling out small helpers would give names to two lines each and spread one idea across three places.
- **A shared module for the file path** used by `fetch.py` and `metrics.py`. The duplication is one line, and a change is unlikely. A comment cross-referencing the two is enough. A new module would add an import between two independent scripts.
- **Type annotations for the mypy findings.** They help tools more than readers here. The data is GitHub's JSON passed through.

## D. Refactoring recommendation

- **Worth changing:** move the planning rules into `plan_repos` (C1); check the saved-file shape (C2, after approval).
- **Not worth changing:** `stop()`, `_size`, `query_page`, `load_config`, `save`, `fetch_repo`, the constants. No classes, exceptions, retry libraries or new modules.
- **Missing information or decisions:**
  - approval of the C2 behaviour change;
  - whether automated tests are wanted. Without them, the change has to be checked by hand.
- **How to check the result:**
  - **Behaviour:** after the change, run the three paths once against a test repo and compare with today's output lines and saved-file shape:
    - a full fetch;
    - an incremental fetch;
    - an incremental fetch after deleting one repo's file.

    For C2, also run once with a file whose `meta` key has been removed.
  - **Maintainability:** apply the "full fetch if older than 30 days" example as a paper exercise before and after. The improvement is real if it needs one function instead of reading two loops.

Overall: **small, targeted changes only.** This file doesn't need a refactor.
