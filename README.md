# gh-pr-metrics

A GitHub Copilot agent that shows how your team's pull requests (PRs) move through review:
time to merge, where the time goes, skipped reviews, reverts, PR size and unfinished work.
Works with github.com and company GitHub servers. Every number is defined in [METRICS.md](METRICS.md).

## Flow Diagram

```mermaid
flowchart LR
    U([You]) -->|"Run PR metrics"| A[Copilot agent]
    A --> F[fetch.py]
    G[(GitHub)] -->|gh CLI| F
    F --> D[(data/<br/>one file per repo)]
    D --> M[metrics.py]
    M --> R[report.py]
    R --> H([report per repo<br/>.html])
```

## Start in 3 steps

1. **Install** VS Code with GitHub Copilot, [Python 3.11+](https://www.python.org/downloads/)
   and [GitHub CLI](https://cli.github.com), then sign in: `gh auth login --hostname <your GitHub server>`
2. **Copy** `pr-metrics.config.sample.toml` to `pr-metrics.config.toml` and fill it in.
   Each setting is explained in the file. It stays on your machine.
3. **In Copilot Chat,** pick the **gh-pr-metrics** agent and type a request below.
   It asks you to confirm once, then builds the report.

| Type                                          | You get                                              |
| --------------------------------------------- | ---------------------------------------------------- |
| Run PR metrics                                | The latest periods                                   |
| Run PR metrics since start                    | Every period since `history_start`                   |
| Run PR metrics for the last 3 months          | The last 3 months (or "6 weeks")                     |
| Run PR metrics from 2 Nov 2026 to 15 Nov 2026 | That range, beside the same number of days before it |
| Add "full refresh" to any of the above        | All data downloaded again                            |

## Read the report

Each repo gets its own report: open `output/<date-time>/report-<owner>-<name>.html` in any browser.

- One table per question; columns are periods, labelled by date.
- Each cell: typical PR (median) · slower end (p75) (PR count).
- ▼ better / ▲ worse / = same compares the latest complete period with the one before.
  One period alone is often noise: look across several.
- Notes flag anything that affects the numbers. The PR list at the end filters by period and author.

## Check the numbers

In a report's PR list, tick **Show calculation details** to see each PR's times and the
days worked out from them. To check a period's figures: pick the period, click
**Download shown rows as CSV**, open it in Excel and use `=MEDIAN()` and
`=PERCENTILE.INC(range,0.75)`. They match the report (rarely off by 0.1 from rounding).

## If it stops

| Message                                    | Do this                                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------------- |
| gh is not signed in                        | Run the `gh auth login` command shown                                        |
| config file not found                      | Do step 2                                                                    |
| settings changed since the last full fetch | Say yes when the agent offers a full fetch                                   |
| GitHub kept failing                        | GitHub is overloaded; try again later                                        |
| … is before history_start                  | Ask for later dates, or set an earlier `history_start` and do a full refresh |
| No PRs found for login(s)                  | Check those logins in the config                                             |

Never committed: `pr-metrics.config.toml`, `data/` (saved PRs) and `output/` (reports).

Built as a successor to [pr-metrics-agent](https://github.com/thomas3577-star/pr-metrics-agent): see [what's improved](COMPARISON.md).
