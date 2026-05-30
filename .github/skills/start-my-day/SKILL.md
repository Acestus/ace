---
name: start-my-day
description: 'Create today''s daily planning note, load active tickets from Linear, and present the day''s board. Use when the user says "start my day", "morning setup", "create today''s note", or "what am I working on today?"'
argument-hint: 'Say "start my day" to create the daily note and load the board'
---

# Start My Day Skill

Create today's daily planning note, load active tickets from Linear, and present the day's board.

## When to Use

- User says "start my day", "morning setup", "create today's note", "what am I working on today?"
- Beginning of a work session when no daily note exists yet

---

## Workflow

### Step 1 — Create the daily note

```bash
cd /home/wweeks/git/projects
python3 scripts/daily_note.py --start
```

This creates `planner/MM-DD.org` with:
- Empty Time Log table (ready for `tl start KEY`)
- Kanban Board (lane status with `:NEXT:` steps, from Linear `flow:active` state)
- Standup section (skeleton for end-of-day fill)
- Notes section

If the note already exists with content, the script says so and exits cleanly.

### Step 2 — Report what was loaded

After the script runs, tell the user:
- The note path
- How many active tickets were loaded and their lane assignments
- Any lane with no active ticket (they may want to dispatch one)

Example:
> "Daily note created for May 23. Loaded 3 active tickets:
> 🔴 <PROJECT>-363 — Five9 call script engine (Urgent)
> 🔵 <PROJECT>-357 — Entra Security Groups (Manual)
> 🟢 <PROJECT>-390 — Web Platform SSR spike (Background)
>
> Timer is ready — `tl start <PROJECT>-363` to begin tracking."

### Step 3 — Check for empty lanes

If fewer than 3 active tickets loaded, offer to dispatch:
> "The Urgent lane is empty. Want me to pull the next ticket from the queue?"

If the user says yes, invoke the `linear-dispatcher` skill.

### Step 4 — Morning Forecast

After loading the board, provide a brief forecast for today based on ticket state and history:

```
🔮 Forecast:
   🔴 <PROJECT>-363 — Day 2 active, 3 TODOs remaining. ~2h to close if scoping goes well.
   🔵 <PROJECT>-357 — Day 5 active, 1 TODO left. Should close today with 30m effort.
   🟢 <PROJECT>-390 — Day 7 active, stuck on same TODO 3 rounds. May need breakdown or park.
```

**How to calculate:**
1. Count days since `flow:active` was set (from changelog or context bundle)
2. Count remaining `- [ ]` items in the issue file's Follow-up section
3. Look at average time per TODO from prior completed tickets in the same lane
4. Flag tickets that are past their lane's expected cycle time:
   - 🔴 Urgent: expected 1-3 days
   - 🔵 Manual: expected 3-5 days
   - 🟢 Background: expected 5-10 days

**If a ticket is overdue or at risk:**
```
⚠  <PROJECT>-390 (🟢) is on day 7 — past expected 5d cycle for Background.
   Consider: breakdown, timebox 1h today, or park and pull fresh work.
```

---

## Notes

- Daily note path: `planner/MM-DD.org` (e.g., `planner/05-23.org`)
- Active tickets: queried from Linear `flow:active AND assignee = currentUser()`
- `:NEXT:` steps: pulled from `issues/{KEY}/` markdown files (first `- [ ]` item)
- If no issue file exists for a ticket, `:NEXT:` shows "No next step defined"
- The note is created locally only — no git push needed at start of day

---

## Constraint Summary (Morning)

After the forecast, provide a one-line constraint load summary:

```
🏭 Constraint load: 2/3 technician | 1/3 vendor | 0/3 dependency
```

**If all 3 active tickets are `constraint:technician`:**
```
🛑 Stop the Line: All 3 active slots are technician-only.
   You are the bottleneck. Before starting, consider:
   • Park one and pull a non-technician item
   • Spend first 30min documenting one (elevate the constraint)
   • Delegate one to a team member with access
```

**If 2/3 are `constraint:vendor`:**
```
⚠ Vendor-heavy load: 2/3 tickets waiting on external parties.
   Consider: pull a Background item you can make autonomous progress on.
```

This surfaces at start-of-day before the user commits to the plan — giving them a chance to rebalance.

---

## Composes

```
start-my-day
├── linear-dispatcher     (Step 3 — fill empty lane slots)
└── rounds                (implicitly — user typically starts rounds after)
```

**Called by:** user directly


---
