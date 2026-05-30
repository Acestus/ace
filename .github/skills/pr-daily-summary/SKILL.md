---
name: pr-daily-summary
description: 'Generate a daily pull request summary for standup. Fetches yesterday''s merged and opened PRs across the <GITHUB_ORG> org, formats a readable summary, and publishes to Notion. Use when the user says "PR summary", "yesterday''s PRs", "daily PR report", "standup PRs", or "what got merged yesterday?"'
argument-hint: 'Optionally specify a date (YYYY-MM-DD) or say "publish" to push to Notion'
---

# PR Daily Summary Skill

Generate a standup-ready summary of yesterday's pull requests across the <GITHUB_ORG> GitHub org. Publishes to a rolling Notion page for historical reference.

## When to Use

- User says "PR summary", "yesterday's PRs", "daily PR report", "standup PRs"
- User says "what got merged yesterday?" or "PR activity"
- Start of day when reviewing overnight team activity
- Posting standup updates to Notion

---

## Workflow

### Step 1 — Generate the Report

```bash
cd /home/wweeks/git/projects
python3 scripts/gh_pr_daily.py --report
```

This fetches from the `<GITHUB_ORG>` GitHub org:
- All PRs **merged** yesterday
- All PRs **opened** yesterday (still open)
- Skips PRs closed without merge

Output is a markdown table sorted most-recent-first, grouped by status.

To override the date:

```bash
python3 scripts/gh_pr_daily.py --report --date 2026-05-24
```

### Step 2 — Review with the User

Present the summary and confirm it looks right before publishing. Highlight:
- Total merged count and opened count
- Any repos with high activity
- Any notable authors or patterns

### Step 3 — Publish to Notion

Once the user confirms (or if they said "publish" up front):

```bash
cd /home/wweeks/git/projects
python3 scripts/gh_pr_daily.py --publish --page-id PAGE_ID
```

The page ID is stored in `.env` as `GH_PR_DAILY_PAGE_ID` so you can omit `--page-id`:

```bash
python3 scripts/gh_pr_daily.py --publish
```

The script **prepends** the new day's summary at the top of the page, so most recent is always first.

### Step 4 — Confirm

Tell the user:
- How many PRs were summarized
- The Notion page URL
- That the page is updated

---

## CLI Reference

```bash
python3 scripts/gh_pr_daily.py --report                          # stdout summary
python3 scripts/gh_pr_daily.py --report --date 2026-05-24        # specific date
python3 scripts/gh_pr_daily.py --publish                         # publish using env page ID
python3 scripts/gh_pr_daily.py --publish --page-id 1234567890    # publish to specific page
python3 scripts/gh_pr_daily.py --org other-org --report          # different org
```

---

## Output Format

The summary is designed to be read in 1–3 minutes at standup:

```markdown
## PR Summary — Monday, May 25, 2026

### ✅ Merged (4)

| Repo | PR | Author | Title |
|------|-----|--------|-------|
| iac-infra | #142 | wweeks | feat: Add monitoring dashboard |
| fabric-platform | #88 | jdoe | fix: Pipeline schedule drift |

### 🆕 Opened (2)

| Repo | PR | Author | Title |
|------|-----|--------|-------|
| projects | #56 | wweeks | chore: Add PR daily summary skill |

**Total activity:** 4 merged, 2 opened across the org.

---
```

---

## Setup

### First-Time Notion Page Creation

If no page exists yet, create one:

```bash
cd /home/wweeks/git/projects
python3 scripts/create-notion-page.py notion/PR-Daily-Summary.md \
  --space-key IPM \
  --parent-id <PAGE_ID> \
  --title "Daily Pull Request Summary — <GITHUB_ORG>"
```

Then add the page ID to `.env`:

```
GH_PR_DAILY_PAGE_ID=<page-id-from-above>
```

### Automation (Cron)

To run daily at 7:00 AM Central:

```cron
0 7 * * 1-5 cd /home/wweeks/git/projects && python3 scripts/gh_pr_daily.py --publish
```

Or via systemd timer for better reliability.

---

## Notes

- Uses `gh search prs` which requires the `gh` CLI to be authenticated
- Fetches from all non-archived, non-fork repos in the org
- Notion publish prepends (newest at top) — the page becomes a rolling history
- No PII or secrets in the output — just PR metadata
- Rate limits: GitHub search API allows ~30 requests/minute; one run uses 2 queries

---

## Composes

```
pr-daily-summary
├── notion-updater    (manual section updates if needed)
└── start-my-day          (can be called as part of morning routine)
```

**Called by:** user directly, or as part of `start-my-day` morning routine
