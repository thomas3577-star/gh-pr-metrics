# What the numbers mean

Version 1 · 2026-11-15

This file defines every number in the report. The scripts follow it exactly. To change what a number means, change it here first and add a line to the change log.

## Goal

Evaluate how well a team's pull requests (PRs) move through review, whether merged changes hold up without being reverted, whether PRs are small enough to review well, and whether unfinished work is building up, so leadership can act on facts.

## Who and what is counted

- **People:** only the GitHub logins listed under `authors` in the config; everyone if the list is empty. Bot accounts are never counted, as PR authors or as reviewers.
- **Repos:** only the repos listed under `repos`. Each repo is reported separately; numbers are never combined across repos.
- **Periods:** results are shown per period (1 week, 2 weeks or a calendar month, set in the config), labelled by date; the latest may be in progress.
- **Which period a PR counts in:** the period it was merged in (or closed, if closed without merging). Questions 1 to 5 use PRs merged in the period.
- **Clock:** period boundaries use the `utc_offset` time zone (India: +05:30). Durations are calendar time, including weekends.
- **How results are shown:** median (typical PR) · p75 (75 in 100 PRs are at or below this) [2] · PR count. With few PRs, read p75 with the count.

## The six questions

| Question | What is measured |
|---|---|
| 1. How long does a PR take to merge? | Time from PR opened to merged |
| 2. Where do PRs spend the most time? | Time in each stage (below) |
| 3. Are reviews skipped? | % merged without approval |
| 4. Are merged changes stable? | % of merged PRs later reverted |
| 5. Are PRs small enough to review well? | Lines changed per PR, beside an industry benchmark |
| 6. Is unfinished work piling up? | Open PRs at period end; age of open PRs; time since last activity on open PRs; % closed without merging |

### 2. Time per stage

| Stage | From | To |
|---|---|---|
| Draft | PR opened | Marked ready for review (zero if never a draft) |
| Waiting for first review | Ready for review | First review by a person other than the author (reviews by bots, such as Copilot, don't count) |
| In review | First review | Last approval |
| Waiting to merge | Last approval | Merged |

- A PR with no review or no approval is left out of the stages it never reached. The report shows how many.
- Stage medians do not add up to the time-to-merge median. Each is a typical value on its own.

### 3. Skipped reviews
- **Merged without approval:** merged PRs with no approval from anyone other than the author.
- We don't measure whether reviews were rushed. No up-to-date research gives a fair way to tell a rushed review from a quick, good one [3].

### 4. Stability (minimum)
- **Reverted:** a merged PR from the period that a later merged PR titled "Revert…" points to, by PR number or merge commit. Revert PRs by anyone count, not only the listed authors.
- Shown as reverted PRs ÷ merged PRs, as a %.
- Always labelled "minimum": the true rate is at least this. It misses problems fixed without a revert, and PRs merged in recent periods have had less time to be reverted.

### 5. PR size
- Lines added plus lines deleted.
- Shown beside the benchmark: elite teams' PRs are under 100 lines [1][2][7]. A comparison, not a pass or fail.
- Includes generated files and lockfiles, so some PRs look bigger than the work behind them.

### 6. Unfinished work
- **Open PRs:** the number of PRs still open at the end of the period. For the period in progress, open now.
- **Open PR age:** for PRs still open at the end of the period, time from opened to the period's end. For the period in progress, to now.
- **Time since last activity:** for PRs open now, time since the last update. Shown for the period in progress only, because past activity dates are not kept. No "idle" cut-off is applied [4][5][6].
- **Closed without merging:** PRs closed unmerged in the period ÷ all PRs closed or merged in the period, as a %.

## References

1. [LinearB, 2026 Software Engineering Benchmarks Report](https://linearb.io/library/engineering-benchmarks-and-research). 8,109,244 PRs from 4,813 teams in 42 countries. Elite PR size is under 100 lines. Findings are correlational.
2. [LinearB, engineering metrics](https://linearb.io/library/engineering-metrics) and [LinearB, metrics glossary](https://linearb.helpdocs.io/article/1s38stsugw-glossary-metrics). "Elite" is the top 10% of LinearB's customer teams. Benchmarks are calculated at p75. PR size counts added, deleted and modified lines, so it runs slightly higher than this report's added plus deleted.
3. [Does Order Matter? An Empirical Investigation into the Impact of File Ordering on Code Review Effectiveness (2026)](https://arxiv.org/pdf/2609.22610). 330K PRs from 182 GitHub projects: review attention falls as PR size grows, and visible comments are a misleading sign of review effort.
4. [Code Climate, Abandoned Pull Requests](https://codeclimate.com/blog/abandoned-pull-requests). Treats more than three days without activity as abandoned, based on its own data.
5. [Wessel et al., Should I Stale or Should I Close? (2019)](https://www.ime.usp.br/~gerosa/papers/BotSE2019.pdf). The stale bot's default is 60 days without activity: a tool setting, not evidence.
6. [Rahman et al., Why Do Pull Requests Go Silent? (2026)](https://arxiv.org/pdf/2609.22625). 14,234 stalled PRs from 19 GitHub repos. Inactivity is often caused by failing checks or dependencies, not neglect.
7. [Google, Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html). "100 lines is usually a reasonable size for a CL, and 1000 lines is usually too large", left to the reviewer's judgement; file count also matters. Guidance, not a study.

## Change log

| Date | Version | Change | Why |
|---|---|---|---|
| 2026-11-16 | 1 | First version: six questions, results per period, listed authors (or everyone), bots never counted. Thresholds only where a current, referenced study exists | New product: evaluate a named team across repos |
| 2026-11-17 | 2 | Reviews and approvals by bots (such as Copilot) no longer count | Matches the original intent; automated reviews made human review look instant |
