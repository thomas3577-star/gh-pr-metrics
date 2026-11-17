# Python Maintainability Baseline Report: `scripts/fetch.py`

Baseline date: 2026-11-17. File measured: `scripts/fetch.py`, 9,698 bytes. Assessment only: no code was changed or run.

Threshold note: the complexity (<10) and function length (≤30) targets are conventions, not current research. Treat a fail as a pointer, not a defect.

## A. Metrics summary

| Metric | Current baseline | Target | Assessment | Status |
|---|---|---|---|---|
| Physical lines | 247 | Informational | n/a | Measured |
| Logical lines | 154 | Informational | n/a | Measured |
| Function count | 12 | Informational | n/a | Measured |
| Class count | 0 | Informational | n/a | Measured |
| Maximum complexity | 15 (`main`) | <10 | Fails | Measured |
| Functions with complexity ≥10 | 3 | 0 | Fails | Measured |
| Longest function (logical lines) | 42 (`main`) | ≤30 | Fails | Measured |
| Functions over 30 logical lines | 1 | 0 | Fails | Measured |
| Maintainability Index | 45.60 (radon "A") | Improve from baseline | Baseline recorded | Measured |
| mypy strict errors | 43 | 0 | Fails | Measured |
| Automated tests | 0 (no tests folder) | Establish baseline | None exist | Measured |
| External dependencies | Standard library only, plus the gh CLI | No unnecessary additions | Meets | Measured |

What the 43 mypy errors are:

- **31 are about missing annotations:** 12 functions with no annotations and 19 calls to unannotated functions.
- **The other 12 point at real code:** 8 calls to the unannotated `stop()`, and 4 type issues (lines 94, 99, 172, 178).
- **Three of those four type issues** (lines 94, 99, 172) exist only because mypy doesn't know `stop()` never returns.

## B. Function-level complexity

| Function | Lines | Logical lines | Complexity | Max nesting | Assessment |
|---|---|---|---|---|---|
| stop | 63–65 | 3 | 1 | 0 | OK |
| iso | 68–69 | 2 | 1 | 0 | OK |
| parse_time | 72–73 | 2 | 1 | 0 | OK |
| load_config | 78–99 | 21 | **13** | 2 | Fails complexity. Flat validation checks, easy to read. |
| repo_file | 104–105 | 2 | 1 | 0 | OK |
| load_saved | 108–115 | 8 | 3 | 1 | OK. Returns three different kinds of value. |
| save | 118–124 | 7 | 1 | 0 | OK |
| gh | 129–133 | 5 | 2 | 1 | OK |
| check_signed_in | 136–139 | 4 | 2 | 1 | OK |
| query_page | 145–172 | 25 | **14** | 2 | Fails complexity. Mixed responsibilities. |
| fetch_repo | 175–187 | 13 | 6 | 3 | OK |
| main | 192–243 | **42** | **15** | **4** | Fails complexity and length. Deepest nesting. |

## C. Top five maintainability problems

1. **`main` does six jobs** (lines 192–243).
   - Evidence: 42 logical lines, complexity 15, nesting depth 4. It parses arguments, plans each repo's mode, fetches, merges with saved data, keeps the run log, saves, and prints.
   - Impact: the planning rules (damaged file, new repo, settings changed) can't be tested without calling GitHub.
   - Improvement: split it into a planning function, a per-repo fetch-and-merge function, and a thin `main`.

2. **`query_page` mixes concerns and uses a global** (lines 142–172).
   - Evidence: it builds the gh arguments, runs gh, parses JSON, classifies the error, waits and retries, all in one function. The module-level `_size` changes across calls and across repos.
   - Impact: the retry behaviour depends on hidden state from earlier repos and can't be tested on its own.
   - Improvement: separate argument building, error classification and the retry loop, and pass the page size in explicitly.

3. **Library functions end the process** (12 calls to `stop()`).
   - Evidence: `load_config`, `gh`, `check_signed_in`, `query_page` and `main` all call `sys.exit` through `stop()`.
   - Impact: callers can't recover, tests have to catch `SystemExit`, and mypy can't see that `stop()` never returns. That causes 3 of the type errors.
   - Improvement: raise typed exceptions and turn them into exit codes only in `main`, or annotate `stop()` as never returning.

4. **The saved file's shape is assumed, never checked** (lines 108–115 and 213–226).
   - Evidence: `load_saved` returns a dict, `None`, or the text `"damaged"`. A file that is valid JSON but has no `meta` or `prs` key leads to a `KeyError` at line 213, 224 or 226.
   - Impact: a hand-edited or partly written file crashes with a raw traceback and exit code 1, instead of a STOPPED message.
   - Improvement: check the required keys inside `load_saved` and treat a wrong shape as damaged.

5. **No types and no tests.**
   - Evidence: 0 of 12 functions are annotated, there are 43 mypy strict errors, and there are 0 tests. Config, PRs and saved data are all passed around as plain dicts with unwritten contracts.
   - Impact: any refactor has nothing to check it against.
   - Improvement: annotate the data shapes first, then add tests around the planning and merging behaviour.

Minor items, for information only:

- Line 156: `json.loads` isn't guarded. If gh returns success with non-JSON output, you get a traceback.
- Lines 225 and 229: `fetch_repo(...)` is called identically in both branches.
- Lines 222 and 238: the "now, without microseconds" expression is repeated.

## D. Prioritised refactoring opportunities

| Priority | Improvement | Benefit | Risk |
|---|---|---|---|
| 1 | Add tests for repo planning and merging (mock `fetch_repo`) | High: makes everything below safe | Low |
| 2 | Annotate `stop()` as never returning, plus the data shapes | Clears most mypy errors and 3 false type errors | Very low |
| 3 | Check the saved-file shape in `load_saved` | Turns a crash into a clear message | Low |
| 4 | Split `main` into plan, fetch-merge-save and the entry point | Complexity and length back within target | Medium |
| 5 | Remove the `_size` global and split `query_page` | Testable retries, no hidden state | Medium: retry behaviour was confirmed in a real run |
| 6 | Leave `load_config` alone | Its complexity of 13 comes from flat checks | n/a |

## E. Behaviour and validation gaps

- **Public interface:** the command line `--mode full|incremental`, `--config` and `--data-dir`; exit codes 0, 2 and 4; the console output lines; the file name pattern `data/prs-<owner>-<name>.json`; the saved file's `meta` and `prs` structure, which `metrics.py` reads.
- **Side effects:**
  - runs the `gh` subprocess (auth status, GraphQL);
  - reads the config and saved files;
  - writes data files atomically, via a temporary file then a rename;
  - waits 10 seconds before each retry;
  - prints to stdout and stderr.
- **Tests:** none, so the execution status is not applicable.
- **Can't currently be verified automatically:**
  - incremental overlap handling;
  - deduplication of open PRs on a full fetch;
  - "settings changed" detection;
  - recovery from a damaged file;
  - shrinking page sizes on retry;
  - the 20-run log cap.

  Real runs showed the retry and full or incremental paths working, but that is manual evidence, not repeatable.
- **Highest refactoring risk:** the planning branch in `main` and the merge logic (lines 226–236). An unnoticed change there would silently alter the saved data that every report depends on.

## Appendix: tools and commands

- Python 3.13.18, radon 6.0.1 and mypy 2.3.1, default configuration.
- Commands, run against a copy of the file:
  - `radon raw fetch.py`
  - `radon cc -s -a fetch.py`
  - `radon mi -s fetch.py`
  - `mypy --strict fetch.py`
- Per-function logical lines: radon `analyze()` on each function's source, using Python's `ast`. Nesting counts `if`, `for`, `while`, `try` and `with`.
- The script was not executed, and nothing was changed.
