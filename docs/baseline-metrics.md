# Python Maintainability Baseline Report: `scripts/metrics.py`

Baseline date: 2026-11-17. File measured: `scripts/metrics.py`, 22,135 bytes. Assessment only: no code was changed or run.

Threshold note: the complexity (<10) and function length (≤30) targets are conventions, not current research. Treat a fail as a pointer, not a defect.

## A. Metrics summary

| Metric | Current baseline | Target | Assessment | Status |
|---|---|---|---|---|
| Physical lines | 498 | Informational | n/a | Measured |
| Logical lines | 334 | Informational | n/a | Measured |
| Function count | 25 (23 top-level, 2 nested) | Informational | n/a | Measured |
| Class count | 0 | Informational | n/a | Measured |
| Maximum complexity | 28 (`per_column`, `main`) | <10 | Fails | Measured |
| Functions with complexity ≥10 | 7 | 0 | Fails | Measured |
| Longest function (logical lines) | 69 (`main`) | ≤30 | Fails | Measured |
| Functions over 30 logical lines | 3 | 0 | Fails | Measured |
| Maintainability Index | 13.10 (radon "B") | Improve from baseline | Baseline recorded | Measured |
| mypy strict errors | 122 | 0 | Fails | Measured |
| Automated tests | 0 | Establish baseline | None exist | Measured |
| External dependencies | Standard library only | No unnecessary additions | Meets | Measured |

What the 122 mypy errors are:

- **111 are about missing annotations:** 25 functions with no annotations and 86 calls to unannotated functions.
- **The other 11 point at real code:**
  - 6 at lines 99, 100, 109, 193, 194 and 197 exist only because mypy doesn't know `stop()` never returns.
  - 4 at lines 443, 446, 456 and 457 come from `by_repo`, a dict that holds a list and two counts under different keys.
  - 1 at line 364 is a missing annotation for `marked`.

## B. Function-level complexity

| Function | Lines | Logical lines | Complexity | Max nesting | Assessment |
|---|---|---|---|---|---|
| stop | 48–50 | 3 | 1 | 0 | OK |
| when | 53–54 | 2 | 2 | 0 | OK |
| days | 57–58 | 2 | 1 | 0 | OK |
| iso_or_none | 61–62 | 2 | 2 | 0 | OK |
| prs | 65–66 | 2 | 2 | 0 | OK |
| load_config | 71–109 | **32** | **18** | 2 | Fails both. Flat validation checks. |
| load_config.a_date (nested) | 81–85 | 5 | 3 | 1 | OK |
| load_data | 112–125 | 14 | 4 | 2 | OK. Doesn't check the saved file's shape. |
| midnight | 130–131 | 2 | 1 | 0 | OK |
| months_shift | 134–138 | 5 | 1 | 0 | OK |
| all_groups | 141–157 | 17 | 5 | 2 | OK |
| label | 160–166 | 7 | 3 | 1 | OK |
| choose_columns | 169–202 | **34** | **17** | 3 | Fails both. Also changes `args`. |
| find_reverted | 211–230 | 20 | **17** | 3 | Fails complexity |
| per_pr | 233–276 | 26 | **25** | 2 | Fails complexity. Calculation core. |
| spread | 281–286 | 8 | 5 | 1 | OK. Calculation core. |
| share | 289–290 | 3 | 2 | 0 | OK |
| per_column | 293–325 | 17 | **28** | 3 | Fails complexity. Calculation core. Also changes its input rows. |
| headline | 328–332 | 5 | 3 | 1 | OK |
| add_markers | 335–346 | 12 | 9 | 2 | OK |
| cell | 351–360 | 11 | 4 | 1 | OK |
| summary_lines | 363–378 | 12 | **10** | 1 | Fails complexity, just |
| plain_notes | 381–398 | 12 | 5 | 1 | OK |
| main | 403–494 | **69** | **28** | 3 | Fails both. Most responsibilities. |
| main.in_range (nested) | 428–431 | 4 | 3 | 1 | OK |

Measurement note: radon adds 1 to complexity for each comprehension and each `and`/`or`. `per_column` scores 28 with only 17 logical lines because it is mostly list comprehensions, so its score overstates how many branches a reader has to follow.

## C. Top five maintainability problems

1. **Functions return results by changing their inputs** (lines 197, 201, 301, 457 and 473).
   - Evidence:
     - `per_column` writes each PR's period into the PR row (line 301). `main` then picks which PRs to show from that field (line 457).
     - `choose_columns` writes `args.short_note` (lines 197 and 201). `main` reads it back with `getattr` (line 473).
   - Impact: the PR list and the "report covers less than asked" note depend on calls a reader can't see from a function's signature. Reordering or reusing these functions silently changes the output.
   - Improvement: return the period assignment and the short note as explicit values.

2. **`main` does eight jobs** (lines 403–494).
   - Evidence: 69 logical lines and complexity 28. It:
     - parses arguments;
     - loads the config and data;
     - checks dates;
     - filters out bots and unlisted authors;
     - finds missing logins;
     - creates the run folder;
     - calculates each repo;
     - writes the results JSON and prints the summary.
   - Impact: the filtering rules (bots, unlisted authors, counting only PRs inside the range) can't be tested without the file system.
   - Improvement: separate the per-repo filtering, the per-repo result building, and the writing and printing.

3. **The calculation core is dense and untested** (lines 233–325).
   - Evidence:
     - `per_pr` has complexity 25 and `per_column` 28.
     - Line 307 decides whether a PR was open at period end with a double negative: `not (when(...) or age_at) < age_at`.
     - Every reported number comes from these two functions, plus `spread` and `share`.
   - Impact: a wrong edge case (a review exactly at merge time, a PR closed exactly at period end) would change reported numbers silently.
   - Improvement: name the open-at-period-end rule as its own small function, then add tests with known PRs and expected medians.

4. **Data contracts are implied and duplicated across files.**
   - Evidence:
     - The PR row is a dict with 22 keys (lines 249–260), and `report.py` reads it by key name.
     - The saved-file path is built again at line 116, separately from `fetch.py`'s `repo_file`.
     - `load_config` checks repos differently from `fetch.py`: `fetch.py` rejects the sample's `owner/...` placeholder, this file doesn't.
     - `load_data` assumes the `prs` and `meta` keys exist (lines 123–124).
   - Impact: renaming a key or changing the file naming in one script breaks another with a `KeyError` or "no saved data", not a clear message.
   - Improvement: keep the file path, config checks and row fields in one shared place, and check the saved file's shape on load.

5. **No types and no tests.**
   - Evidence: 0 of 25 functions annotated, 122 mypy strict errors, 0 tests.
   - Impact: the largest and most complex script has nothing to check a refactor against.
   - Improvement: add tests for the calculation core first, then annotations.

Minor items, for information only:

- Lines 96–100 and `report.py` both parse the time zone offset, in different ways.
- `stop()` exists in all three scripts with two different signatures.
- `per_column` parses the same timestamps again for every period: `when()` runs once per PR per column.

## D. Prioritised refactoring opportunities

| Priority | Improvement | Benefit | Risk |
|---|---|---|---|
| 1 | Add tests for `per_pr`, `per_column`, `spread`, `share` and `find_reverted` with known PRs and expected numbers | High: protects every reported number | Low |
| 2 | Return the period assignment and short note instead of changing inputs | Removes hidden coupling | Low with tests, medium without |
| 3 | Name the open-at-period-end rule (line 307) | Readability of a key definition | Low |
| 4 | Annotate `stop()` as never returning, give `by_repo` a proper type, and type the row | Clears all 11 real mypy errors | Very low |
| 5 | Split `main` into filtering, result building and output | Complexity and length back within target | Medium |
| 6 | Share the file path, config checks and offset parsing with the other scripts | One source of truth | Medium: touches all three scripts |
| 7 | Leave `load_config` and `summary_lines` alone | Their scores come from flat checks and formatting | n/a |

## E. Behaviour and validation gaps

- **Public interface:**
  - the command line: `--since-start`, `--last`, `--from` with `--to`, `--config`, `--data-dir` and `--out-dir`;
  - exit codes 0 and 2;
  - the console summary lines (the agent repeats them word for word);
  - the run folder name `output/YYYYMMDD-HHMMSS`;
  - `results-<owner>-<name>.json`, whose structure `report.py` reads.
- **Side effects:** reads the config and the saved data files, creates the run folder, writes the results files, and prints to stdout and stderr. It never calls GitHub.
- **Tests:** none, so the execution status is not applicable.
- **Can't currently be verified automatically:**
  - median and p75 values;
  - the stage times;
  - revert matching (by #number and SHA);
  - open-at-period-end counts;
  - period boundaries for weeks, two weeks and months;
  - `--last` handling across months;
  - the "report covers less than asked" note;
  - partial columns;
  - bot and unlisted counts scoped to the range.

  Manual evidence exists: real runs, plus the CSV and Excel check you can do from the report. But that isn't repeatable.
- **Highest refactoring risk:** `per_pr`, `per_column` and the hidden period assignment. A change there alters reported numbers with no error.

## Appendix: tools and commands

- Python 3.13.18, radon 6.0.1 and mypy 2.3.1, default configuration.
- Commands, run against a copy of the file:
  - `radon raw metrics.py`
  - `radon cc -s -a --show-closures metrics.py`
  - `radon mi -s metrics.py`
  - `mypy --strict metrics.py`
- Per-function logical lines: radon `analyze()` on each function's source, using Python's `ast`. Nesting counts `if`, `for`, `while`, `try` and `with`.
- The script was not executed, and nothing was changed.
