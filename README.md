# gh-pr-metrics

A GitHub Copilot agent that reports how a team's pull requests (PRs) move through review:
how long they take to merge, where the time goes, whether reviews are skipped, whether
merged changes hold up, whether PRs are small enough, and whether unfinished work is
building up. Works with github.com and company-hosted GitHub Enterprise Server.

Every number is defined in [METRICS.md](METRICS.md).

## Set up once

1. **Install** VS Code with GitHub Copilot, [Python 3.11 or later](https://www.python.org/downloads/)
   and [GitHub CLI](https://cli.github.com). Nothing else is needed.
2. **Sign in to GitHub** in a terminal:
   `gh auth login --hostname <your GitHub server>` (for public GitHub: `github.com`).
3. **Create your settings:** copy `pr-metrics.config.sample.toml` to
   `pr-metrics.config.toml` and fill it in. Each setting is explained in the file.
   This file stays on your machine and is never committed.

| Setting | What to put |
|---|---|
| `host` | Your GitHub server, e.g. `github.yourcompany.com` |
| `repos` | The repos to include, as `owner/name` |
| `authors` | GitHub logins of the people to include, or `[]` for everyone. Bots are never counted. The agent can find logins from names |
| `history_start` | The earliest date you will ever want in a report |
| `group_by` | How the report splits time: `"1 week"`, `"2 weeks"` or `"month"` |
| `group_starts_on` | Any day a sprint started, so columns match your sprints (not used for months) |
| `show_last` | How many columns a normal report shows |
| `utc_offset` | Your time zone, e.g. `"+05:30"` for India |

## Run it

Open this folder in VS Code, open Copilot Chat, pick the **gh-pr-metrics** agent and type
one of these:

| Type | You get |
|---|---|
| Run PR metrics | The latest columns (as many as `show_last`) |
| Run PR metrics since start | Every column since `history_start` |
| Run PR metrics for the last 3 months | Columns in the last 3 months (or "6 weeks") |
| Run PR metrics from 2 Nov 2026 to 15 Nov 2026 | That range, beside the same number of days before it |
| Add "full refresh" to any of the above | All data downloaded again |

The agent asks you to confirm once, then fetches, calculates, writes a few observations
and builds the report. VS Code may also ask you to allow the commands it runs.
The first run downloads everything since `history_start`; later runs fetch only changes.

## Read the report

Each run gets its own folder, `output/YYYYMMDD-HHMMSS`, containing `report.html`.
Open it in any browser; it works offline.

- **Observations** at the top are written by AI from the numbers. Check before acting.
- **Six questions** follow, one table each. Columns are periods, labelled by date.
  Each cell shows the typical PR (median), the slower end (p75: 75 in 100 PRs are at or
  below this) and the PR count.
- **▼ better / ▲ worse / = same** compares the latest complete period with the one before.
  Lower is better. One period alone is often noise: look across several.
- **Notes on the data** flag anything that affects the numbers, such as a misspelt login.
- **PRs counted** lists every PR behind the numbers, with filters by period and author.

## If something goes wrong

The agent tells you what the script said. The common ones:

| Message | What to do |
|---|---|
| gh is not signed in to … | Run the `gh auth login` command it shows |
| config file not found | Copy the sample config, as in set-up step 3 |
| settings changed since the last full fetch | Let the agent run a full fetch |
| … is before history_start | Ask for later dates, or set an earlier `history_start` and do a full refresh |
| No PRs found for login(s) … | Check the spelling of those logins in the config |

## Files

| Path | What it is | Committed |
|---|---|---|
| `METRICS.md` | What every number means, with references | Yes |
| `pr-metrics.config.sample.toml` | Settings template | Yes |
| `pr-metrics.config.toml` | Your settings | **No** |
| `.github/agents/gh-pr-metrics.agent.md` | The agent's instructions | Yes |
| `scripts/` | `fetch.py` (gets PRs), `metrics.py` (calculates), `report.py` (builds the page) | Yes |
| `data/` | Saved PR data | **No** |
| `output/` | One folder per run | **No** |
