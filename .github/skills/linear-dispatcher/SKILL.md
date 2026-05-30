---
name: linear-dispatcher
description: 'Dispatch the next highest-priority Linear issue into an open lane using the Eisenhower matrix. Use when the user says "dispatch", "next ticket", "what should I work on", or a lane is empty and needs filling.'
argument-hint: 'Say "dispatch" or "next ticket" to pull the highest-priority item from the queue'
---

# Linear Dispatcher Skill

Pull the next highest-priority `flow:queue` issue and assign it to an open lane.

## Eisenhower Priority Model

All issues are tagged `urgency:N` and `importance:N` (1=highest, 5=lowest).

| Quadrant | Urgency | Importance | Action |
|----------|---------|------------|--------|
| Q1 — Do Now | ≤2 | ≤2 | Dispatch immediately |
| Q2 — Schedule | ≥3 | ≤2 | Schedule next available |
| Q3 — Delegate | ≤2 | ≥3 | Low-effort; pull when Q1/Q2 empty |
| Q4 — Drop | ≥3 | ≥3 | Only if nothing else exists |

Within quadrant: sort by `urgency + importance` (lower sum = higher priority). Tiebreak by oldest `createdAt`. Due within 2 days overrides quadrant and jumps to front.

## Dispatch Workflow

### Step 1 — Check WIP

```bash
cat /tmp/rounds-claims.json 2>/dev/null || echo "{}"
```

Count occupied lanes (lanes 1–5). If all 5 are occupied, tell the user — no dispatch until a lane clears.

### Step 2 — Query the queue

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/linear_search.py --label flow:queue
```

Also check if any lanes have `flow:waiting` issues that freed up (waiting doesn't count against WIP).

### Step 3 — Score and rank

For each queue issue:
1. Read `urgency:N` and `importance:N` labels
2. Compute quadrant (Q1–Q4)
3. Check due date — override if within 2 days
4. Sort: Q1 → Q2 → Q3 → Q4, then by score sum ascending

Present top 3 as options; default dispatch is the top item.

### Step 4 — Activate

```bash
python3 scripts/linear_set_flow.py --key {KEY} --flow active
```

Update the claim file:
```bash
echo '{"lane1": "{KEY}", ...}' > /tmp/rounds-claims.json
```

### Step 5 — Create local stub if missing

```bash
ls /home/wweeks/git/projects/issues/ | grep {KEY}
# If missing:
python3 scripts/linear_create_stub.py --key {KEY}
```

### Step 6 — Report

```
✓ Dispatched {KEY} → Lane {N}

{KEY} — {title}
Quadrant: Q{N} | urgency:{U} importance:{I} | due: {due}
State: In Progress
```

## WIP Limit

Max 5 active issues (one per lane). `flow:waiting` does not count. Enforce strictly — do not dispatch if all 5 lanes are filled.
