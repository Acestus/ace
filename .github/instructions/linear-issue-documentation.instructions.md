---
applyTo: "issues/**/*.md"
---

# Linear Issue Documentation Format

## File Location
Issues live at: `issues/{IDENTIFIER} - {title}/{IDENTIFIER} - {title}.md`

Example: `issues/ENG-42 - Fix auth timeout/ENG-42 - Fix auth timeout.md`

## Header (YAML front matter)
```yaml
---
LINEAR: ENG-42
title: Fix auth timeout on token refresh
team: ENG
state: In Progress
flow: active
due: 2026-06-15
created: 2026-05-30
---
```

## Sections

### Required
- `## Description` — what the ticket is about (mirrors Linear description)
- `## Actions` — dated entries in **reverse chronological order** (newest first)

### Optional (add when relevant)
- `## Investigation` — discovery notes, findings, hypotheses
- `## Follow-up` — always last; status + TODO checklist

## Actions Entry Format
```
### 2026-05-30
WORKLOG: 1h | Investigated token refresh race condition. Found that the expiry window is 0s.
COMMENT: Opened an issue on the auth-service repo pointing to the race condition in token_refresh.py.
```

- `WORKLOG:` = internal investigative voice (first person, past tense)
- `COMMENT:` = posted to Linear as a comment (also internal voice)
- Time format: `1h`, `30m`, `1h 30m`

## Flow States
| `flow:` value | Linear State | Meaning |
|---------------|-------------|---------|
| `queue`       | Backlog     | Not yet started |
| `active`      | In Progress | Currently being worked |
| `waiting`     | In Review   | Blocked / waiting on external |
| `done`        | Done        | Completed |

## Dispatch Priority
Tickets are ranked for dispatch using Linear's native `priority` field: Urgent (1) first,
then High (2), Medium (3), Low (4), with No Priority (0) ranked last. Issue number is the
tie-break when priority is equal. This is the sole ranking mechanism — see
`LinearRanking.cs`, used by both the live `linear dispatch-next` command and the local
SQLite `workflow dispatch` command, so the two never diverge.

Set priority directly on the Linear issue (`--priority N` at creation, or via the Linear
UI) — no separate urgency/importance labels are needed or read by dispatch.
