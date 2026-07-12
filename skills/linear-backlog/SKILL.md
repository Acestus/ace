---
name: linear-backlog
description: 'Create new Linear issues with Eisenhower scoring and local stub files. Use when the user says "add a work item", "create a Linear issue", "new backlog item", or wants to file new work. Handles scoring, issue creation, label application, and local stub creation.'
argument-hint: 'Describe the work item to create'
---

# Linear Backlog Skill

Create a new Linear issue with Eisenhower scoring and a local stub file.

## When to Use

- User says "add a work item", "create a Linear issue", "new backlog item", "add to backlog"
- User wants to file new work with proper scoring

## Eisenhower Scoring Heuristics

Score the issue before creating it. Ask the user if unclear.

**Urgency (u) — time pressure:**
| Score | Meaning |
|-------|---------|
| 1 | Due today or actively blocking something |
| 2 | Due this week or causing real slowdown |
| 3 | Due this month or moderate friction |
| 4 | Vague future / nice to have |
| 5 | No real deadline |

**Importance (i) — business/mission impact:**
| Score | Meaning |
|-------|---------|
| 1 | Mission-critical; failure has major consequences |
| 2 | High impact; affects key workflows |
| 3 | Moderate impact; improves things meaningfully |
| 4 | Low impact; minor improvement |
| 5 | Negligible impact |

**Quadrant assignment:**
- Q1 (u≤2, i≤2) → Priority: Urgent or High
- Q2 (u≥3, i≤2) → Priority: Medium
- Q3 (u≤2, i≥3) → Priority: Medium or High
- Q4 (u≥3, i≥3) → Priority: Low

## Workflow

### Step 1 — Gather information

Ask the user for:
- Title (required)
- Description (recommended)
- Team key (required — e.g. ENG)
- Urgency score (1–5)
- Importance score (1–5)
- Due date (optional)
- Any additional labels

### Step 2 — Score and confirm

Present the scoring before creating:
```
Title:      Fix auth token timeout
Team:       ENG
Urgency:    2 (due this week)
Importance: 2 (affects key workflows)
Quadrant:   Q1 — Do Now
Priority:   High
Labels:     flow:queue, urgency:2, importance:2
```

### Step 3 — Create the issue

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/linear_create_issue.py \
    --team ENG \
    --title "Fix auth token timeout" \
    --description "Token TTL set to 15m causing user logouts. Should be 60m." \
    --priority 2 \
    --label "flow:queue" \
    --label "urgency:2" \
    --label "importance:2"
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
  Quadrant: Q1 | urgency:2 importance:2
  State: Backlog (flow:queue)
  Stub: issues/ENG-124 - Fix auth token timeout/
```

## Notes

- Always create both the Linear issue AND the local stub in the same operation
- Labels `urgency:N` and `importance:N` are the sole dispatch ranking mechanism
- `flow:queue` is the default initial state for all new backlog items
- If the team doesn't have urgency/importance labels yet, create them first in Linear settings
