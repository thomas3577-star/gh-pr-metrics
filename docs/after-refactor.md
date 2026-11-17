# After the Maintainability Refactor: Before and After

Date: 2026-11-17. This compares the scripts after the refactor with the baselines in `docs/baseline-fetch.md`, `docs/baseline-metrics.md` and `docs/baseline-report.md`, which stay unchanged.

The plan came from `docs/maintainability-review-*.md`. Its goal was code that is easier for a person to understand and change, with identical results. Metrics are supporting evidence only.

## Summary

All the planned changes are done, and the results are unchanged:

- the same saved data;
- the same results files;
- the same HTML pages (apart from the deliberately reformatted script block);
- the same console lines.

The main improvements:

- Every metric rule a user might question now has a name and a docstring: `counted_reviews` and `open_at`.
- No function returns results by changing its inputs any more.
- The repo planning rules in `fetch.py` live in one place, `plan_repos`.
- Two page features no longer depend on question titles.

## What changed

| Step | Script | Change |
|---|---|---|
| 0 | new | `scripts/check_same.py`: runs `metrics.py` and `report.py` with a fixed clock for four report ranges, and compares every output with a saved reference |
| 1 | report.py | The time-since-last-activity row and the benchmark line are switched on by markers in `SECTIONS`, not by question titles |
| 2 | report.py | One `tz_from_offset` helper replaces two copies |
| 3 | report.py | The filter and CSV JavaScript is formatted readably, with comments |
| 4 | metrics.py | Comments listing the three shapes a measure can take, and pointing to the shared data file name |
| 5 | metrics.py | `assign_periods` sets each PR's period as its own step; `choose_columns` returns the "report covers less than asked" note instead of storing it on `args` |
| 6 | metrics.py | Named rules: `counted_reviews` and `open_at` (replacing a double negative) |
| 7 | metrics.py | `split_by_repo` moves PR sorting out of `main`, replacing a dict that mixed lists and counts |
| 8 | fetch.py | `plan_repos` holds the per-repo planning rules |
| 9 | fetch.py | A comment saying `metrics.py` builds the same data file name |

Deferred: defining each PR list column once in `report.py`. Do it the next time a column is added.

## How "same results" was checked

| Script | Check | Result |
|---|---|---|
| report.py, steps 1–2 | `check_same.py`: 16 pages byte for byte | Identical |
| report.py, step 3 | Everything outside the script block, on 16 pages; old and new scripts run in a simulated browser (jsdom) with 13 filter combinations on 3 pages, comparing visible rows and the full CSV text | Identical. A real browser test was asked of the owner. |
| metrics.py, steps 4–7 | `check_same.py` after each step: results files, pages and console lines for 4 ranges | Identical |
| metrics.py, step 6 | Old and new "open at period end" rule on 24 edge cases (created, merged or closed exactly at the period end) | Identical |
| metrics.py, step 7 | Old and new versions with an author list (2 real logins, 1 misspelled) | Identical, including the "Not counted" and "No PRs found" notes |
| fetch.py, steps 8–9 | Old and new versions offline, with the same fake GitHub answers and a fixed clock: incremental, missing file, damaged file, settings changed, full | Identical output, exit codes and saved files |
| fetch.py | One real incremental run against GitHub by the owner | Worked; saved file layout unchanged |

## Metrics: before and after

Same tools and settings as the baselines: radon 6.0.1 and mypy 2.3.1 (`--strict`). "Real mypy errors" means errors left after excluding those that only report missing annotations.

| Metric | fetch.py before → after | metrics.py before → after | report.py before → after |
|---|---|---|---|
| Physical lines | 247 → 257 | 498 → 533 | 220 → 246 |
| Logical lines | 154 → 158 | 334 → 351 | 106 → 105 |
| Functions | 12 → 13 | 25 → 29 | 11 → 12 |
| Highest complexity | 15 → 14 | 28 → 21 | 14 → 14 |
| Functions with complexity ≥10 | 3 → 2 | 7 → 7 | 1 → 1 |
| Longest function (logical lines) | 42 → 30 | 69 → 52 | 18 → 18 |
| Functions over 30 logical lines | 1 → 0 | 3 → 3 | 0 → 0 |
| Maintainability Index | 45.60 → 47.04 | 13.10 → 15.20 | 43.76 → 45.39 |
| Real mypy errors | 4 → 4 | 11 → 8 | 0 → 0 |

**Reading the numbers:**

- **`main` got smaller in both larger scripts.** In `fetch.py` it went from 42 to 30 logical lines (complexity 15 to 7). In `metrics.py` it went from 69 to 52 (complexity 28 to 20).
- **The scripts are slightly longer overall.** That's from the docstrings, comments and readable JavaScript, which were the point.
- **`metrics.py` still has 7 functions with complexity of 10 or more.** The maintainability reviews judged the remaining ones (`load_config`, `choose_columns`, `find_reverted`, `per_pr`, `per_column`, `summary_lines`, `main`) to be flat checks, formatting, or a single cohesive idea, so they were left on purpose.
- **The 4 real type errors that disappeared from `metrics.py`** came from the mixed list-and-count dict removed in step 7.
- **The remaining real type errors in both `fetch.py` and `metrics.py`** are almost all because `stop()` isn't marked as never returning. Not done: it helps tools, not readers.

## Still open (each changes results or needs a decision)

| Item | Effect |
|---|---|
| A saved data file with missing sections is treated as damaged | A full fetch instead of a crash |
| Tooltip "same than the period before" | Wording fix |
| `ready_at` in the PR list can differ from the ready time used in calculations when GitHub returns empty timeline entries | Confirm whether intended |

## Using `check_same.py` from now on

- **Re-save the reference** (`python scripts/check_same.py save`) whenever the data changes, for example after a fetch, or after a deliberate change to the output.
- **Run `compare` after any change** to `metrics.py` or `report.py` that shouldn't change the output.
- **It doesn't cover `fetch.py`,** which calls GitHub.
