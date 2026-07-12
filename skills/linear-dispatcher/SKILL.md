---
name: linear-dispatcher
description: 'Dispatch the next unclaimed Linear issue into an open lane. Use when the user says "dispatch", "next ticket", "what should I work on", or a lane is empty and needs filling.'
argument-hint: 'Say "dispatch" or "next ticket" to pull the next Linear issue'
---

# Linear Dispatcher Skill

Pull the next unclaimed Linear issue and assign it to an open lane.

## Workflow

Run the dispatcher script and let Python choose the ticket:

```bash
cd /home/wweeks/github/ace
python3 scripts/linear_dispatch_next.py --activate
```

That script:
- skips already-claimed tickets
- resumes unclaimed `In Progress` tickets first
- otherwise pulls the next `flow:queue` ticket
- activates the chosen ticket and creates its stub

If you need the raw selection without activation, drop `--activate`.

## Report

```
✓ Dispatched {KEY}
  Source: active|queue
  Priority: {priority}
  State: In Progress
```
