# Human Maintainability Review: `scripts/metrics.py`

Review date: 2026-11-17. Source: `scripts/metrics.py` (498 lines, 25 functions). The source was not changed.
Quantitative baseline: `docs/baseline-metrics.md`. Its figures are referenced below, not recalculated.

## What the file does

It reads the saved PR files and, separately for each repo, calculates the figures behind the report's six questions. It writes `results-<owner>-<name>.json` per repo into a new `output/YYYYMMDD-HHMMSS` folder, and prints a text summary that the Copilot agent repeats word for word. It never contacts GitHub.

**Flow:**

1. Check the config.
2. Load all saved PRs into one dict keyed `owner/name#N`.
3. Turn the requested range into periods (`choose_columns`, `all_groups`).
4. Find reverted PRs within each repo (`find_reverted`).
5. Sort PRs by repo, leaving out bots and unlisted authors (and counting them).
6. Build one row of values per PR (`per_pr`, step 1).
7. For each repo:
   - calculate the median, p75 and percentages per period (`per_column`, step 2);
   - add the better, worse or same markers;
   - write the results and print the summary.

**Important rules**, documented in `METRICS.md`:

- reviews count only from non-authors, submitted by the merge time;
- the ready time is the first "ready for review" event, otherwise the creation time;
- a PR belongs to the period it was merged or closed in;
- "open at period end" means created before that moment and not merged or closed by then;
- values are rounded to 2 decimals before taking medians, so they match Excel.

**Side effects:** reads the config and data files, creates the run folder, writes the results files, reads the clock, and prints.

**What the source can't tell us:**

- whether `METRICS.md` and the code currently agree in every detail (only spot-checked here);
- whether automated tests are wanted.

## A. Overall assessment

**Maintainable, with three real obstacles.** The helpers, the period logic and the aggregation (`spread`, `share`) are clear and should stay. The obstacles:

1. **Two important results are produced by changing inputs,** not by being returned.
2. **Two metric definitions are written as dense expressions** that are hard to check against `METRICS.md`.
3. **`main` mixes PR sorting with per-repo output,** using one dict that holds values of different kinds.

The baseline's large numbers overstate the problem in places:

- **`per_column`** scores 28 with only 17 logical lines, mostly list comprehensions.
- **`load_config`** (18) and **`summary_lines`** (10) are flat checks and formatting.
- **`main`** (69 logical lines, complexity 28) does reflect a real problem.

## B. What should remain unchanged

| Item | Reason |
|---|---|
| `when`, `days`, `iso_or_none`, `prs`, `midnight`, `months_shift` | Small, well named, and `months_shift` is documented |
| `all_groups`, `label`, `choose_columns` (apart from C1) | The period logic is clear |
| `spread`, `share` | Exact, small, and they match Excel's MEDIAN and PERCENTILE.INC. This is where trust in the numbers comes from, so don't touch them. |
| `per_pr` as one function | It is long, but it's one cohesive idea: everything about one PR. Splitting it into many helpers would scatter it. Only the two dense rules need names (C2). |
| `find_reverted` | Complexity 17, but a documented two-pass algorithm |
| `load_config`, `summary_lines`, `plain_notes`, `cell`, `headline`, `add_markers` | Flat or formatting code, easy to change |
| `MARKED`, `ELITE_PR_LINES` | Clear constants with comments |
| One file in clear sections | Easier to navigate than a package of small modules |
| The three measure shapes (spread, share, count) | Changing the format would touch both scripts and the saved results. A comment listing the three is enough. |

## C. Meaningful improvement opportunities

### 1. Important results come from changing inputs (high benefit)

- **Current problem.**
  - `per_column` writes each PR's period into the row (line 301). `main` relies on it to decide which PRs appear in the report (line 457), and `report.py` shows it as the Period column.
  - `choose_columns` writes `args.short_note` (lines 197 and 201), which `main` reads back with `getattr` (line 473).
- **Practical impact.** Debugging "why is this PR missing from the report?" leads to `main` line 457. The cause is a side effect inside a function whose name says it calculates period figures. Calling `per_column` for a second purpose, or reordering the calls, silently changes which PRs appear.
- **Simpler alternative.**
  - Assign periods in a named step, `assign_periods(rows, columns)`, called before `per_column`. `per_column` then only reads them.
  - Have `choose_columns` return the note alongside the columns.
- **Trade-off.** Removes hidden behaviour, and the output stays identical. One extra function and one changed return value.
- **Recommendation.** Change it.

### 2. Two metric definitions are hard to read and check (high benefit)

- **Current problem.**
  - Line 307 decides "open at period end" with a double negative: `not (when(r["merged"] or r["closed"]) or age_at) < age_at`.
  - Lines 242–244 apply three review conditions in one comprehension: has a submit time, isn't the author, and submitted by the merge time.
- **Practical impact.** A Product Owner asks "why does this PR count as open on 15 Nov?" or "why wasn't this review counted?". Answering takes careful decoding, and it's hard to confirm the code matches `METRICS.md`.
- **Simpler alternative.** Two small named functions whose names and one-line docstrings match `METRICS.md`:
  - `open_at(row, moment)`;
  - `counted_reviews(pr, author, merged)`.

  No other change.
- **Trade-off.** About 10 lines added. The rules become searchable and readable. A boundary mistake (`<` versus `<=`) would change the numbers silently, so compare outputs (see D).
- **Recommendation.** Change it.

### 3. `main` mixes PR sorting with per-repo output (moderate benefit)

- **Current problem.**
  - Lines 425 and 433–443 keep each repo's rows, bot count and unlisted count in one dict whose values are of different kinds (`by_repo`). mypy reports 4 errors from this.
  - Lines 452–493 build the scope text, notes, results file and printed summary for each repo in one loop.
- **Practical impact.** Changing a counting rule (for example, counting bots outside the range too) means editing inside `main` among unrelated output code. Reading the per-repo output means scrolling past the sorting code.
- **Simpler alternative.** Pull out the sorting (lines 433–443) into `split_by_repo(...)`, returning each repo's rows and its counts as separate values. Leave the per-repo output loop in `main`.
- **Trade-off.** Separating the output loop as well would need about nine parameters. That moves complexity rather than removing it, so it isn't recommended.
- **Recommendation.** Change the sorting part only.

### 4. Small, undocumented assumptions (low benefit, documentation only)

- **The three measure shapes** (`{median, p75, count}`, `{count, of, pct}` and `{value}`) are told apart by which keys exist (`headline`, `cell` here, and `cell` in `report.py`). **Recommendation:** add one comment near `spread` and `share`.
- **`ready_at`** (line 253) is recorded only when the timeline list is non-empty, while the calculation falls back to the creation time. Whether this difference is intended can't be established from the source. **Recommendation:** confirm, then add a comment or align the two.
- **The data path is rebuilt** at line 116, separately from `fetch.py`'s `repo_file`. **Recommendation:** add a comment cross-referencing the two. A shared module isn't justified for one line.

### Considered and not recommended

- **Classes for rows or measures, a metrics framework, pandas, or splitting into a package.** None would remove complexity, and pandas adds a dependency.
- **Splitting `per_column` or `load_config` to lower their scores.** Their scores come from comprehensions and flat checks, not hard-to-follow logic.
- **Changing the format of the results file.** It's a contract with `report.py`, and there's no demonstrated benefit.

## D. Refactoring recommendation

- **Worth changing:**
  - remove the hidden outputs (C1);
  - name the two metric rules (C2);
  - pull out the PR sorting (C3);
  - add the comments (C4).

  Do them in that order.
- **Not worth changing:** the period logic, `spread`/`share`, `per_pr` as one function, `find_reverted`, `load_config`, the formatting code, the results format and the single-file layout.
- **Missing information or decisions:**
  - whether the `ready_at` difference is intended;
  - whether automated tests are wanted.

  These are the riskiest changes in the project, because a mistake silently changes reported numbers.
- **How to check the result:**
  - **Behaviour:** before changing anything, run `metrics.py` on the current `data/` folder with a fixed `--from`/`--to` range and keep the results files. After each change, run it again within the same minute and compare.
    - Everything should be identical except `generated_at`, open PR ages and time since last activity, which depend on the clock.
    - Any difference in medians, p75s, counts or the PR list means the change altered behaviour.
  - **Maintainability:** before and after, time how long it takes to answer "why is PR X open at the end of period Y?" and "why is PR Z missing from the list?". The changes are justified if both can be answered from a named function.
