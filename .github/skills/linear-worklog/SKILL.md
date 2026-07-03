---
name: linear-worklog
description: 'Log time and comments to Linear issues via markdown files. Use when the user says "log time", "update Linear", "document my time", "worklog", or wants to record work done on a Linear issue. Finds or creates the issue file, adds WORKLOG/COMMENT entries, and posts the comment to Linear.'
argument-hint: 'Specify the Linear issue key (e.g. ENG-123) and what to log'
---

# Linear Worklog Skill

Log work and comments to Linear issues. State lives in markdown files under `issues/`; comments are posted to Linear via API.

## When to Use

- User says "log time to ENG-123", "update Linear", "worklog", "add a comment"
- Rounds transitions that need a worklog entry
- End of a work block — capturing what was done

## Voice Convention

- **WORKLOG lines** — internal voice, first-person past tense. "Investigated the auth timeout. Found token expiry set to 15m instead of 60m."
- **COMMENT lines** — same for Linear (it's an engineering tool, internal voice throughout).

## Workflow

### Step 1 — Find or create the issue file

```bash
ls /home/acestus/git/ace/issues/ | grep {KEY}
```

If no file: create one.
```bash
cd /home/acestus/git/ace
dotnet run --project src/Ace.Tools.Cli -- linear create-stub --key {KEY}
```

### Step 2 — Gather what to log

Ask the user (or infer from context):
- What was done? (WORKLOG entry)
- Any comment to post publicly on the Linear issue? (COMMENT entry)
- Time spent? (record in WORKLOG line as `[Nh]`)
- Flow state change? (e.g. moving to waiting, done)

### Step 3 — Write the entry into the file

In the issue file's `## Actions` section, add at the top (newest first):

```markdown
### YYYY-MM-DD

WORKLOG [1.5h]: Investigated root cause of auth timeout. Token TTL was 15m, should be 60m. Fix deployed to dev.

COMMENT: Investigated auth timeout — root cause was token TTL set to 15m. Updated to 60m and deployed to dev. Ready for QA verification.
```

### Step 4 — Post the comment to Linear

If a COMMENT line was added:
```bash
dotnet run --project src/Ace.Tools.Cli -- linear comment --key {KEY} --comment "Investigated auth timeout..."
```

### Step 5 — Update flow state if changed

```bash
dotnet run --project src/Ace.Tools.Cli -- linear set-flow --key {KEY} --flow waiting
```

### Step 6 — Commit and push

```bash
cd /home/acestus/git/ace
git add issues/
git commit -m "worklog: {KEY} — {short description}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

## Issue File Format

```markdown
---
LINEAR: ENG-123
title: Fix auth token timeout
team: Engineering
state: In Progress
flow: active
urgency: 2
due: 2026-06-15
created: 2026-05-29
---

## Description

Short description of the issue.

## Actions

### 2026-05-29

WORKLOG [1.5h]: Investigated root cause. Found token TTL at 15m, should be 60m.

COMMENT: Investigated auth timeout — token TTL was 15m. Updated to 60m, deployed to dev. Ready for QA.

## Follow-up

Status: In Progress
TODO:
- [ ] QA verification in dev
- [ ] Deploy to prod after QA passes
```

## Notes

- `## Actions` entries are newest first (reverse chronological)
- `WORKLOG` = internal voice only (never shown to end users)
- `COMMENT` = posts to Linear as a comment on the issue
- Commit to main triggers CI sync (if configured)
