# Python Maintainability Baseline Report: `scripts/report.py`

Baseline date: 2026-11-17. File measured: `scripts/report.py`, 11,240 bytes. Assessment only: no code was changed or run.

Threshold note: the complexity (<10) and function length (≤30) targets are conventions, not current research. Treat a fail as a pointer, not a defect.

## A. Metrics summary

| Metric | Current baseline | Target | Assessment | Status |
|---|---|---|---|---|
| Physical lines | 220 | Informational | n/a | Measured |
| Logical lines | 106 | Informational | n/a | Measured |
| Function count | 11 (plus 1 lambda) | Informational | n/a | Measured |
| Class count | 0 | Informational | n/a | Measured |
| Maximum complexity | 14 (`pr_list`) | <10 | Fails | Measured |
| Functions with complexity ≥10 | 1 | 0 | Fails | Measured |
| Longest function (logical lines) | 18 (`build_page`) | ≤30 | Meets | Measured |
| Functions over 30 logical lines | 0 | 0 | Meets | Measured |
| Maintainability Index | 43.76 (radon "A") | Improve from baseline | Baseline recorded | Measured |
| mypy strict errors | 48 | 0 | Fails | Measured |
| Automated tests | 0 | Establish baseline | None exist | Measured |
| External dependencies | Standard library only | No unnecessary additions | Meets | Measured |

What the 48 mypy errors are: all 48 are about missing annotations (11 functions with no annotations, and 37 calls to unannotated functions). There are no other type errors.

Measurement note: the logical line count understates this file. `pr_list` is 38 physical lines but only 15 logical lines, because most of it is long multi-line HTML strings. So "meets ≤30" here doesn't mean the functions are short to read.

## B. Function-level complexity

| Function | Lines | Logical lines | Complexity | Max nesting | Assessment |
|---|---|---|---|---|---|
| stop | 71–73 | 3 | 1 | 0 | OK |
| e | 76–77 | 2 | 1 | 0 | OK. The name is too short to be clear. |
| local_time | 80–83 | 5 | 2 | 0 | OK. Duplicates `fmt_time`'s offset parsing. |
| cell | 86–93 | 9 | 6 | 1 | OK. Chooses a format by which keys exist. |
| marker | 96–99 | 5 | 2 | 0 | OK |
| column_table | 102–114 | 10 | 9 | 1 | OK |
| fmt_time | 117–122 | 7 | 3 | 1 | OK. Duplicates `local_time`. |
| fmt_days | 125–126 | 3 | 2 | 0 | OK |
| pr_list | 134–171 | 15 | **14** | 1 | Fails complexity. 38 physical lines. |
| build_page | 174–202 | 18 | 7 | 2 | OK. Behaviour depends on question titles. |
| main | 205–216 | 12 | 4 | 1 | OK |

## C. Top five maintainability problems

1. **`pr_list` mixes five jobs in one long string build** (lines 134–171).
   - Evidence: complexity 14 and 38 physical lines. It sorts the PRs, builds each row, builds the header, builds the three filters and the CSV button, and writes the help text.
   - Impact: changing one column means editing the header and the row in two places that must stay in the same order. Nothing checks that they match.
   - Improvement: define the columns once, as a list of header and value pairs, and build both the header and the rows from it.

2. **Behaviour depends on question titles** (lines 191–192).
   - Evidence: `title.startswith("6.")` adds the time-since-last-activity row, and `title.startswith("5.")` adds the benchmark line.
   - Impact: renumbering or rewording a question silently drops that row or line, with no error.
   - Improvement: mark those extras as fields of the section in `SECTIONS`.

3. **Unchecked dependence on `metrics.py`'s output** (lines 86–93 and 213).
   - Evidence:
     - `cell()` picks a format by checking for the keys `value`, `median` or `of`, or whether the value is a plain number.
     - Every page reads around 20 key names from the results file.
     - `json.loads` at line 213 isn't guarded.
   - Impact: a renamed key in `metrics.py`, or a damaged results file, crashes with a raw traceback, not a STOPPED message.
   - Improvement: check the results file's version or required keys on load, and keep the key names in one place shared with `metrics.py`.

4. **Time zone parsing is duplicated** (lines 80–83 and 117–122, plus `metrics.py` lines 96–100).
   - Evidence: the same offset-to-timezone code appears twice in this file, and a third, regex-based version is in `metrics.py`.
   - Impact: a fix to one copy, for example offsets like `-03:30`, can miss the others.
   - Improvement: one function that parses the offset, used everywhere.

5. **Embedded minified CSS and JavaScript, with no tests** (lines 45–68).
   - Evidence: the styling and the filter and CSV code are compressed one-line strings inside Python. The CSV download hasn't been checked in a real browser.
   - Impact: hard to read or change, and a broken filter or download shows up only when a user tries it.
   - Improvement: keep it unminified and readable, and add one check that a generated page contains the expected table and controls.

Minor items, for information only:

- `stop()` takes only a message here, but a code and a message in the other two scripts.
- Line 99: the title text "better than the period before" is fixed wording, so "same" reads as "same than the period before".

## D. Prioritised refactoring opportunities

| Priority | Improvement | Benefit | Risk |
|---|---|---|---|
| 1 | Add one test: build a page from a small results file and check its tables, filters and PR rows | Protects the whole output | Low |
| 2 | Move the section extras out of title matching | Removes silent breakage | Very low |
| 3 | Merge `local_time` and `fmt_time` offset parsing, shared with `metrics.py` | One source of truth | Low |
| 4 | Define the PR list columns once | Header and rows can't drift apart | Low |
| 5 | Check the results file's shape on load | Clear message instead of a traceback | Low |
| 6 | Unminify the CSS and JavaScript | Readability | Very low |
| 7 | Fix the "same than" wording | Correct tooltip text | Very low |

## E. Behaviour and validation gaps

- **Public interface:**
  - the command line: one argument, the run folder;
  - exit codes 0 and 2;
  - the console lines `Report: <path>`, which the agent repeats;
  - the file name `report-<owner>-<name>.html`;
  - the page layout, filters, the "Show calculation details" option and the CSV download.
- **Side effects:** reads the results files and writes one HTML file per repo. The page itself creates a CSV file in the user's browser. No network access.
- **Tests:** none, so the execution status is not applicable.
- **Can't currently be verified automatically:**
  - that every number on the page matches the results file;
  - the filter combinations;
  - the CSV contents and encoding (BOM, quotes);
  - local time conversion;
  - the markers and tooltips;
  - HTML escaping of PR titles.
- **Highest refactoring risk:** `pr_list`. Its header and row order must match, and the CSV export and the Excel check both depend on that order.

## Appendix: tools and commands

- Python 3.13.18, radon 6.0.1 and mypy 2.3.1, default configuration.
- Commands, run against a copy of the file:
  - `radon raw report.py`
  - `radon cc -s -a report.py`
  - `radon mi -s report.py`
  - `mypy --strict report.py`
- Per-function logical lines: radon `analyze()` on each function's source, using Python's `ast`. Nesting counts `if`, `for`, `while`, `try` and `with`.
- The script was not executed, and nothing was changed.
