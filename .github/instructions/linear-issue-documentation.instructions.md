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
urgency: 2
importance: 3
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

## Urgency / Importance (Eisenhower Matrix)
| Value | Meaning |
|-------|---------|
| 1     | Highest |
| 2     | High    |
| 3     | Medium  |
| 4     | Low     |
| 5     | Lowest  |

## Dispatch Priority
Tickets are ranked for dispatch using: `urgency` first, then `importance`.
Labels `urgency:N` and `importance:N` must exist in the Linear team to be applied via API.
