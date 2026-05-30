---
name: sdp-dispatcher
description: 'Dispatch ServiceDesk Plus cases to Lanes 4-6 (SDP swimlanes). Reads cases/ markdown, scores by urgency/importance/agentic, advances the highest-priority queue case to flow:active. Mirror of jira-dispatcher for SDP. Use when the user says "dispatch sdp", "next sdp ticket", "sdp board", or "assign me sdp work".'
argument-hint: 'dispatch sdp [4|5|6|urgent|approval|background] — rotates the named lane (or fills any open lane).'
---

# SDP Dispatcher Skill

You are the dispatcher for the SDP side of the kanban board. Same model as `jira-dispatcher` — but you operate on `cases/` markdown and SDP tags/statuses, and you respect cross-link ownership.

**Read `jira-dispatcher` first.** This skill documents only the SDP-specific deltas.

---

## When to Use

- User says "dispatch sdp", "next sdp ticket", "what's next on sdp"
- User says "sdp board" — render the 3-lane SDP swimlane snapshot
- User says "this one's done" on an SDP case — close it and rotate the lane
- User wants to see SDP queue / WIP state

---

## The Three SDP Lanes

| # | Lane | Pull rule | Default scoring |
|---|---|---|---|
| 4 | 🔴 **SDP-Urgent** | `flow:queue` + (`urgency:1` or `urgency:2`) | urgency:2 importance:1 agentic:3 |
| 5 | 🟠 **SDP-Approval** | `flow:queue` + (`agentic:4` or `agentic:5`) + approvers required | urgency:3 importance:2 agentic:4 |
| 6 | 🟢 **SDP-Background** | `flow:queue` + (`agentic:1` or `agentic:2`) | urgency:4 importance:3 agentic:2 |

Cases are scored by the header lines (`Urgency:`, `Importance:`, `Agentic:`). The dispatcher reads markdown — it does not push scoring labels to SDP tags (they stay markdown-only).

---

## WIP & Cross-link Ownership

- WIP = 1 per lane (4, 5, 6). Total possible across both systems = 6 active tickets at once.
- Cases tagged `OWNER: jira` are **shadows** — they do NOT count toward WIP and the dispatcher skips them.
- A case with `JIRA: <PROJECT>-XXX` and `OWNER: sdp` is the WIP owner; the Jira side is a shadow.

`flow:waiting` cases don't count against WIP cap (same rule as Jira).

---

## Dispatch Algorithm

1. **Read queue.** `python3 scripts/sdp_search.py --tag flow:queue --json` → all queued cases. Also walk `cases/*/` markdown to merge headers (scoring lives in markdown).
2. **Filter to lane.** For lane 4: urgency ≤ 2. For lane 5: agentic ≥ 4. For lane 6: agentic ≤ 2.
3. **Drop shadows.** Skip any case whose markdown header has `OWNER: jira`.
4. **Score.** Lower urgency wins; tiebreaker = importance, then age (created time).
5. **Advance one.** Highest-scored case → `python3 scripts/sdp_set_flow.py --id {ID} --flow active --transition`. Updates markdown header too if needed (rare — most edits happen via sdp-worklog).
6. **Post starting entries.** Every flow transition is a "touch" — append both a `COMMENT` (internal log) and a `NUDGE` (requester-facing, 6–10 sentences, end-user voice) to `## Actions`. The COMMENT records that you picked the case up; the NUDGE tells the requester their case is now being worked. Format mirrors `sdp-worklog`. Example for queue → active:

   ```markdown
   ### {YYYY-MM-DD HH:mm}

   - WORKLOG 2m: Pulled SDP-{ID} into active work (Lane {4|5|6}).
   - COMMENT: Picked up SDP-{ID}. Plan: confirm {one verification step} before making any changes. Reading the {runbook | precedent case} now.
   - NUDGE: I have just picked up your request and will be working on it now. Based on the description, the goal is to {restate ask in plain language}. Before I make any changes I am going to confirm {one thing — e.g. approver, current state, scope} so I do not have to back out anything later. Once that is verified I will {next step}. Expected first checkpoint back to you: {timeframe}. There is nothing for you to do on your end right now — I will reach out if I need anything from you. Reference: {link to relevant runbook or prior case if any}.
   ```

   Other transitions follow the same pattern: `waiting → active` ("I am back on this") and `active → waiting` ("I am waiting on X from you") both warrant a NUDGE; `active → done` is covered by `sdp-worklog` close-out. A pure investigative checkpoint that the requester does not need to see → COMMENT only, no NUDGE.

7. **Report.** Show the operator: lane, ID, subject, why this one won, link to case file.

---

## Board Render — "sdp board"

```
🔴 SDP Lane 4 — Urgent
  WIP : SDP-33903  Individual Fabric Workspaces Per Developer for EDM        (active 2d)
  Q   : SDP-34104  Add Space to PROD-AZSQL-03                                (urgency:2)

🟠 SDP Lane 5 — Approval
  WIP : SDP-33982  New PIM Role azpim-prd-edm-contributor                    (waiting L1 approval)
  Q   : SDP-33920  ai-skpana-dev-usw2-001 Read Access                        (agentic:4)
  Q   : SDP-33388  Access to Fabric ws_ds_prd Workspace                      (agentic:5)

🟢 SDP Lane 6 — Background
  WIP : (empty)
  Q   : SDP-33961  Update Five9 Call Scripts UMI Sharepoint Graph perms      (agentic:2)
```

Render style mirrors `jira-dispatcher`. Add ⚠ next to stale-waiting cases (>3d in `flow:waiting`).

---

## "This One's Done" — Close + Rotate

When the operator says "this one's done" on an SDP case:

1. **Worklog handoff** — invoke `sdp-worklog` for the final close-out entry. Required: a 6–10 sentence end-user-voice `NUDGE` confirming the work is complete, what the requester should see/do to verify, any follow-up they should expect, and a note that the case is being closed. Plus a brief internal `COMMENT` for the record. Time logged + tasks all `[x]`.
2. **Flow** — `python3 scripts/sdp_set_flow.py --id {ID} --flow done --transition` → status Resolved
3. **Lane release** — clear the lane from `/tmp/rounds-claims.json` if present (rounds may have claimed it)
4. **Rotate** — run the dispatch algorithm for the same lane → advance next queue case to `flow:active` (which itself produces a starting COMMENT + NUDGE per step 6 above)
5. **Report** — "Closed SDP-XXXXX. Lane 4 next: SDP-YYYYY (urgency:2, agentic:3, <USER_B>, Fabric workspace access)."

---

## Important Notes

- Scoring labels stay in markdown only — do not push `urgency:2` etc. as SDP tags
- The SDP "queue" status is **Open**; "active" = In Progress; "waiting" = On Hold; "done" = Resolved (see `FLOW_STATUS_MAP` in `sdp_lib.py`)
- If `flow:` tag and SDP status disagree, the tag wins (markdown source of truth) — `sdp_set_flow.py --transition` always syncs both
- For cross-system context use `start-my-day` (it unions Jira lanes 1-3 + SDP lanes 4-6 with shadow dedupe)

---

## Composes

```
sdp-dispatcher
├── sdp_search.py           (queue read)
├── sdp_set_flow.py         (flow + status transition)
├── sdp-worklog             (close-out worklog)
└── /tmp/rounds-claims.json (shared across all rounds tabs)
```

**Called by:** operator, `rounds` (Station 1 to claim next lane ticket), `start-my-day` (board render).
