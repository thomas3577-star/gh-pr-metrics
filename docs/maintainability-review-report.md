# Human Maintainability Review: `scripts/report.py`

Review date: 2026-11-17. Source: `scripts/report.py` (220 lines, 11 functions). The source was not changed.
Quantitative baseline: `docs/baseline-report.md`. Its figures are referenced below, not recalculated.

## What the file does

For each `results-<owner>-<name>.json` in a run folder, it writes `report-<owner>-<name>.html`. That's a self-contained page that works offline, with:

- one table per question;
- notes;
- a PR list with Period, Status and Author filters;
- a "Show calculation details" option;
- a CSV download for checking the numbers in Excel.

It does no calculations.

**Flow:**

1. `main` finds the results files.
2. `build_page` assembles the header, the legend, one table per entry in the `SECTIONS` list (`column_table`, `cell`, `marker`), the notes and the PR list (`pr_list`).
3. Write each file and print `Report: <path>`.

**Side effects:** reads the results files and writes the HTML files. In the browser, the page's JavaScript builds the CSV file.

**What the source can't tell us:**

- whether the CSV download works in the browsers people use (not yet tried in a real browser);
- how often the page layout changes.

## A. Overall assessment

**Maintainable today, and the simplest of the three scripts.** It has no state, every function apart from `main` is pure, and the `SECTIONS` list makes the layout data-driven.

The obstacles are small:

- Two page features are switched on by question titles.
- `pr_list` keeps the column headers and the row cells in separate places that must match.
- The time zone code is duplicated.
- The JavaScript is compressed onto a few dense lines.

The baseline agrees: only `pr_list` exceeds a threshold (complexity 14). Note that its "15 logical lines" understates it, because it is 38 physical lines of dense HTML.

## B. What should remain unchanged

| Item | Reason |
|---|---|
| `SECTIONS` | Layout as data: the best design choice in the file |
| `main`, `build_page`, `column_table`, `marker`, `cell`, `fmt_days` | Short and single-purpose. `build_page` reads in the same order as the page. |
| Building HTML with f-strings | Pages this size don't justify a template engine, which would add a dependency |
| A single self-contained page with embedded CSS and JS | Required for offline use and easy sharing |
| `e()` as the escape helper | A common convention. Renaming it means 34 edits for no real gain. |
| Reading the results file without checks | It's written by `metrics.py` moments earlier in the same run. Adding checks would guard against a rare case at the cost of more code. |

## C. Meaningful improvement opportunities

### 1. Two page features depend on question titles (high benefit, trivial change)

- **Current problem.** Line 191 has `extra_row=title.startswith("6.")` and line 192 has `if title.startswith("5."):`.
- **Practical impact.** Renumbering or rewording a question silently removes the "time since last activity" row or the benchmark line. Nothing fails, so it may go unnoticed.
- **Simpler alternative.** Mark those two features on the matching entries in `SECTIONS`, and check the mark instead of the title.
- **Trade-off.** Removes a hidden dependency. About 4 lines change, and nothing new is added.
- **Recommendation.** Change it.

### 2. PR list headers and cells are kept separately (moderate benefit)

- **Current problem.**
  - The 8 visible headers (line 155) and their cells (lines 148–153) are written separately.
  - The 9 detail headers (`TIME_HEAD`, `DAYS_HEAD`) and their values (lines 143–147) are also separate lists that must stay in the same order.
- **Practical impact.** Adding a column, say "Reviewers", means two matching edits. A mismatch shifts values under the wrong headings, on screen and in the CSV that Product Owners use to check the numbers in Excel. Nothing catches it.
- **Simpler alternative.** The smallest step is to put each column's header next to its value in one list, so one edit adds both. Keep the filter controls and help text where they are.
- **Trade-off.** Each column becomes a small header-and-value pair, a mild abstraction. It only pays off if the PR list keeps changing, which it has during this project.
- **Recommendation.** Change it the next time a PR list column is added, not before.

### 3. Time zone conversion is written twice (low benefit, trivial change)

- **Current problem.** `local_time` (lines 80–83) and `fmt_time` (lines 117–122) both rebuild a time zone from the offset text.
- **Practical impact.** A fix to offset handling has to be made twice.
- **Simpler alternative.** One `tz_from_offset(offset)` function, used by both.
- **Trade-off.** Removes the duplication with no new concepts.
- **Recommendation.** Change it.

### 4. The JavaScript is compressed onto a few lines (moderate benefit when debugging)

- **Current problem.** `FILTER_JS` (lines 57–68) fits the filter and the CSV export into 11 dense lines, with escaped quotes.
- **Practical impact.** The CSV download is the least tested feature. Debugging a quoting or encoding problem in its current form is slow.
- **Simpler alternative.** The same code, formatted normally across multiple lines. Leave the CSS as it is: it's short and rarely changes.
- **Trade-off.** About 25 more lines. No behaviour change.
- **Recommendation.** Change it, then test the filters and CSV download once in a browser.

### Note: wording defect

Line 99 shows the tooltip "same than the period before" when a period scores the same. This is a text bug, not a maintainability issue. Fix it separately, since the change is visible to users.

### Considered and not recommended

- **A template engine, separate CSS or JS files, a JavaScript framework, or HTML builder classes.** Each adds a dependency, breaks the single offline page, or adds more code than it replaces.
- **Splitting `pr_list` further to lower its complexity score.** Beyond item 2, splitting would only move code around.

## D. Refactoring recommendation

- **Worth changing:**
  - the title-based features (C1);
  - the duplicated time zone code (C3);
  - the compressed JavaScript (C4);
  - the PR list columns, when one is next added (C2).

  Fix the tooltip wording separately.
- **Not worth changing:** `SECTIONS`, the f-string HTML, the single offline page, `e()`, the other helpers, and adding checks on the results file.
- **Missing information or verification:** the CSV download hasn't been tried in a real browser. Do that before and after C4.
- **How to check the result:**
  - **Behaviour:** run `report.py` on an existing run folder (for example `output/20261116-154415`) before and after each change, and compare the HTML files. They must be byte-for-byte identical for C1 to C3. For C4, only the script block should differ.
  - **Maintainability:** before and after C2, count the edits needed to add one PR list column. The change is justified if it drops from two matching edits to one.
