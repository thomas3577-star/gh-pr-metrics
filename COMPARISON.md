# What's improved over pr-metrics-agent

gh-pr-metrics is the successor to [pr-metrics-agent](https://github.com/thomas3577-star/pr-metrics-agent):
from a repo health check to a team performance tool.

| # | Differentiator | Old Version | Newer Version |
|---|---|---|---|
| 1 | **Ready in minutes** | A virtual environment, 5 packages to install, and a GitHub token pasted into a file before the first run | Python and the GitHub CLI you already sign in to. Copy one settings file, type *"Run PR metrics"* in Copilot Chat, and you get a report. Nothing to install, no tokens to paste |
| 2 | **All six questions, answered** | 2 of the 6 questions a team asks about its PRs | How long does a PR take to merge? Where does the time go: waiting for review, in review, or waiting to merge? Are reviews skipped? Do merged changes get reverted? Are PRs small enough? Is unfinished work piling up? One table each |
| 3 | **Your team, your repos, your server** | One public repo at a time, on github.com only | Point it at every repo your team works in, on github.com or your company's GitHub server. List your people and everyone else drops out. Each repo gets its own report, never blended into one number |
| 4 | **Speaks in your sprints** | A rolling 30-day window, whatever your sprint | Columns that line up with your sprints: 1 week, 2 weeks or a month, starting on your sprint day. Then just ask: *"since start"*, *"last 3 months"* or *"from 2 Nov to 15 Nov"* |
| 5 | **Question any number, get a straight answer** | Size labels (10, 100, 400 and 1,000 lines) with no source, and nothing to compare against. A PR list with no dates and no export, so doubting a number meant going back to GitHub | Ask the agent *"Why did #14815 wait 2 days for review?"* and hear: Copilot reviewed in 4 minutes, but bots don't count; a person approved 2 days later. Doubt a median? Download the PRs behind it and check it in Excel in a minute. PR sizes sit beside what elite teams ship (under 100 lines), with the research linked. Copilot and Dependabot never inflate your numbers |

*Faster to start, wider in reach, and it shows its working for every number it gives you.*
