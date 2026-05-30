---
name: sdp-dispatcher
description: 'Dispatch the next highest-priority SDP case into an open lane using the Eisenhower matrix. SDP cases and Jira tickets share the same 5 interchangeable lanes and the same dispatch model. Use when the user says "dispatch sdp", "next sdp ticket", "sdp board", or "assign me sdp work".'
argument-hint: 'dispatch sdp [lane number] — pulls highest Eisenhower-priority SDP case from queue'
---

# SDP Dispatcher Skill

SDP cases use the **same dispatch model** as Jira tickets. Read `jira-dispatcher` first — this skill documents only the SDP-specific deltas.

All 5 lanes are interchangeable. Any lane can claim any SDP case. Priority is Eisenhower-only: urgency + importance quadrant.

---

## When to Use

- User says "dispatch sdp", "next sdp ticket", "what's next on sdp"
- User says "sdp board" — render the active SDP cases across lanes
- User says "this one's done" on an SDP case — close it and rotate the lane
- User wants to see SDP queue / WIP state

---

## SDP-Specific Dispatch Deltas

### Queue Query

```bash
python3 scripts/sdp_search.py --tag flow:queue
```

Parse `Urgency:` and `Importance:` from markdown headers (not API tags — they're tracked markdown-only). Sort by Eisenhower quadrant.

**Skip** any case with `OWNER: jira` — these are shadows of Jira tickets and do not occupy WIP slots.

### Activation

```bash
python3 scripts/sdp_set_flow.py --id {ID} --flow active --transition
```

### Completion

```bash
python3 scripts/sdp_set_flow.py --id {ID} --flow done --transition
```

### Starting Entries (on queue → active)

Every flow transition is a touch. Append both a `COMMENT` and a `NUDGE` to `## Actions`:

```markdown
### {YYYY-MM-DD HH:mm}

- WORKLOG 2m: Pulled SDP-{ID} into active work (Lane {N}).
- COMMENT: Picked up SDP-{ID}. Plan: confirm {one verification step} before making any changes.
- NUDGE: I have just picked up your request and will be working on it now. Based on the description, the goal is to {restate ask in plain language}. Before I make any changes I am going to confirm {one thing} so I do not have to back out anything later. Once that is verified I will {next step}. Expected first checkpoint: {timeframe}. There is nothing for you to do on your end right now — I will reach out if I need anything.
```

---

## SDP Board View

When the user asks for the SDP board:

```
SDP Active Cases:

Lane {N} — {display_id} — {Subject}
  Requester: {name} ({email})
  Urgency: {label} | Importance: {label}
  Next: {first open task or TODO}
  ⏱ {elapsed}

Lane {N} — (open — next Q1 candidate: {display_id})
```

---

## WIP & Cross-link Ownership

- WIP = one SDP case per lane (shared with Jira — only one ticket per lane total)
- `OWNER: jira` cases are shadows — skip them in dispatch
- `flow:waiting` cases don't count against WIP cap
- A case with `JIRA: <PROJECT>-XXX` and `OWNER: sdp` is the WIP owner; the Jira side is a shadow

---

## Decision-Command Mapping

| Operator says | Action |
|---|---|
| `done` | `sdp_set_flow.py --id {ID} --flow done --transition` → Resolved |
| `waiting` | `--flow waiting --transition` → On Hold |
| `approval` | Sets `flow:waiting`, ensures `## Approval` reflects pending levels |
| `blocked` | `flow:waiting` + blocker note |
| `park` | Releases lane claim, keeps `flow:active` |
| `next` | Closes current, claims next queue case |
