---
name: linear-backlog
description: 'Create new Linear issues with native priority and local stub files. Use when the user says "add a work item", "create a Linear issue", "new backlog item", or wants to file new work. Handles priority selection, issue creation, label application, and local stub creation.'
argument-hint: 'Describe the work item to create'
---

# Linear Backlog Skill

Create a new Linear issue with a native Linear priority and a local stub file.

## When to Use

- User says "add a work item", "create a Linear issue", "new backlog item", "add to backlog"
- User wants to file new work with proper prioritization

## Priority Selection

Set Linear's native `priority` field directly — this is the sole dispatch ranking
mechanism (see `LinearRanking.cs`). Ask the user if unclear.

| Priority | Value | Meaning |
|----------|-------|---------|
| Urgent   | 1     | Due today or actively blocking something |
| High     | 2     | Due this week or causing real slowdown |
| Medium   | 3     | Due this month or moderate friction |
| Low      | 4     | Vague future / nice to have |
| No priority | 0  | No real deadline; ranked last for dispatch |

## Workflow

### Step 1 — Gather information

Ask the user for:
- Title (required)
- Description (recommended)
- Team key (required — e.g. ENG)
- Priority (1–4, or 0 for none)
- Due date (optional)
- Any additional labels

### Step 2 — Confirm

Present the ticket before creating:
```
Title:      Fix auth token timeout
Team:       ENG
Priority:   2 (High — due this week)
Labels:     flow:queue
```

### Step 3 — Create the issue

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/linear_create_issue.py \
    --team ENG \
    --title "Fix auth token timeout" \
    --description "Token TTL set to 15m causing user logouts. Should be 60m." \
    --priority 2 \
    --label "flow:queue"
```

### Step 4 — Create local stub

```bash
python3 scripts/linear_create_stub.py --key {KEY}
```

### Step 5 — Commit

```bash
cd /home/wweeks/git/projects
git add issues/
git commit -m "backlog: add {KEY} — {title}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

### Step 6 — Report

```
✓ Created ENG-124 — Fix auth token timeout
  Priority: High (2)
  State: Backlog (flow:queue)
  Stub: issues/ENG-124 - Fix auth token timeout/
```

## Notes

- Always create both the Linear issue AND the local stub in the same operation
- Linear's native `priority` field is the sole dispatch ranking mechanism — do not apply
  separate `urgency:N`/`importance:N` labels; they are not read by any dispatcher
- `flow:queue` is the default initial state for all new backlog items
