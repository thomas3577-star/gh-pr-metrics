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

## Read and check the report

Each repo gets its own report. Open `output/<date-time>/report-<owner>-<name>.html` in any browser.

- Each table answers one question. Each column is a period, shown by its dates.
- Each cell shows a typical PR, a slow PR, and how many PRs: `median · p75 (count)`.
- ▼ means better than the period before, ▲ means worse, = means the same.
  Look at several periods, not just one.
- Notes at the bottom explain anything that affects the numbers.
- The PR list shows every PR behind the numbers. Filter it by period, status or author.

**To check a number:** tick **Show calculation details** to see each PR's times.
Pick a period, click **Download shown rows as CSV**, and open it in Excel.

## Ask about a number

```mermaid
flowchart LR
    U([You]) -->|"Why is PR #123 …?"| A[Copilot agent]
    A --> E[explain.py]
    O[(report results<br/>output/)] --> E
    M[metrics.py] -.->|rule text| E
    E --> P([plain-English answer])
```

Ask the agent in Copilot Chat, for example:

- "Why is owner/repo #123's waiting for first review 1.97 days?"
- "Why isn't #456 counted?"
- "Did it consider CI results for #123?"

It answers from the report itself: each PR's times, every review and why it did or
didn't count, why a PR was left out, and the rule behind each value. Nothing is
recalculated or fetched, so the answer always matches the report you're looking at.

No Copilot? Get the same explanation in a terminal:
`python scripts/explain.py --repo owner/repo --pr 123`.
It explains the newest report; add `--run output/<folder>` for an older one.
If you disagree with a rule itself, the rules are in [METRICS.md](METRICS.md): raise it with the tool's owner.

## If it stops

| Message                                    | Do this                                                                      |
| ------------------------------------------ | ---------------------------------------------------------------------------- |
| gh is not signed in                        | Run the `gh auth login` command shown                                        |
| config file not found                      | Do step 2                                                                    |
| settings changed since the last full fetch | Say yes when the agent offers a full fetch                                   |
| GitHub kept failing                        | GitHub is overloaded; try again later                                        |
| … is before history_start                  | Ask for later dates, or set an earlier `history_start` and do a full refresh |
| No PRs found for login(s)                  | Check those logins in the config                                             |

## Changing the scripts

Only needed if you edit the Python files in `scripts/`. If you just run reports, skip this.

**Why:** a small code change can quietly change a number in the report, with no error.
`check_same.py` catches that.

**How it works:** it keeps a copy of the current results, called the reference. After
you change the code, it produces the results again from the same saved data and tells
you whether anything differs.

**Steps:**
1. Before you edit any script, save the current results as the reference:
   `python scripts/check_same.py save`
2. Make your change.
3. Check what changed:
   `python scripts/check_same.py compare`
   - `SAME` means every number, report and message is unchanged. Safe to commit.
   - `DIFFERENT` lists the files your change altered. If you didn't mean to change
     results, undo your change.
4. If you meant to change results (for example, a new rule), or you've fetched new
   data, run `save` again so later checks compare against the new results.

It checks `metrics.py` and `report.py`. It can't check `fetch.py`, which downloads from
GitHub, where the data is different every time.

## Project structure

```
gh-pr-metrics/
├── .github/agents/gh-pr-metrics.agent.md   the Copilot agent
├── scripts/
│   ├── fetch.py      gets PRs from GitHub (gh CLI)
│   ├── metrics.py    calculates every number in METRICS.md
│   ├── report.py     builds one HTML report per repo
│   ├── explain.py    explains one PR's numbers in plain English
│   └── check_same.py for whoever changes the scripts (see Changing the scripts)
├── METRICS.md        what every number means, with sources
├── COMPARISON.md     what's improved over pr-metrics-agent
├── pr-metrics.config.sample.toml   settings template
├── pr-metrics.config.toml   your settings      (never committed)
├── data/                    saved PRs per repo (never committed)
└── output/                  reports per run    (never committed)
```

Built as a successor to [pr-metrics-agent](https://github.com/thomas3577-star/pr-metrics-agent): see [what's improved](COMPARISON.md).
