---
name: jira-dispatcher
description: 'Dispatch Jira tickets to calendar time blocks using the three-swimlane model. Use when the user says "this one''s done", "assign me work", "dispatch next ticket", "what should I work on", or wants to rotate active tickets. Maintains 3 WIP (one Urgent, one Manual, one Background), pulls next from the correct swimlane queue, and schedules a 1-hour focus block in the planner org file.'
argument-hint: 'Optionally specify which lane to rotate (urgent/manual/background) and what was completed'
---

# Jira Dispatcher Skill

You help the user maintain exactly 3 active work items — one from each swimlane — and schedule focused time blocks for them. When a ticket is completed, you pull the next highest-priority ticket from that lane's queue and assign it a 1-hour calendar block.

## When to Use

- User says "this one's done", "rotate", "assign me work", "dispatch", "next ticket"
- User asks "what should I work on next?"
- User wants to see their current 3 active tickets
- User wants to rebalance or swap a ticket across lanes

---

## Voice & Tone

When confirming dispatch actions, updating worklogs, or describing the current active set — write in <YOUR_NAME>'s voice.

- **Direct, past tense** — "Pulled <PROJECT>-360 into the 🔵 Manual slot. Scheduled for 09:00 tomorrow."
- **Name the actual ticket** — always lead with the Jira key and a clear summary. Not "the next ticket in the queue."
- **Short status confirms** — one or two sentences. What changed, what the lane looks like now.
- **Decision Points** — if there's a trade-off (e.g., no tickets qualify for a lane), say so plainly: "Nothing in the 🟢 Background queue right now — that slot stays open until one comes in."
- **No fluff** — never write "Great news!" or "I've gone ahead and..." — just state what happened.

---

| Lane | Emoji | Criteria | Pull From |
|------|-------|----------|-----------|
| 🔴 **Urgent** | Do First | Urgency 1–2 | Highest U+I score in queue with Urgency ≤ 2 |
| 🔵 **Manual** | Hands-on Focus | Agentic 4–5 AND Importance 1–3 | Highest U+I score in queue with Agentic ≥ 4 and Importance ≤ 3 |
| 🟢 **Background** | Delegate to Agents | Agentic 1–2 | Highest U+I score in queue with Agentic ≤ 2 |

### WIP Rule

- **Up to 3 active tickets** — one per lane ideally, but lanes are flexible
- **When urgent lane is empty**: open a **second manual lane** instead of a fallback. Run `start rounds manual2` in the third tab.
- **Maximum 2 manual tickets active simultaneously** — this is the cap; the empty urgent slot is how you get there
- **When urgent ticket arrives**: park the lower-priority manual ticket back to `flow:queue`, activate the urgent ticket in the 🔴 slot
- If no tickets qualify for any lane at all, the slot stays empty — don't force it

**3 active tickets = 3 In Progress in Jira.** Every label transition is paired with a Jira status transition:

| Flow label change | Jira status transition | Transition ID |
|---|---|---|
| `flow:queue` → `flow:active` | To Do → In Progress | `41` |
| `flow:active` → `flow:done` | In Progress → Done | `31` |
| `flow:active` → `flow:waiting` | In Progress → Code Review | `61` |
| `flow:waiting` → `flow:active` | Code Review → In Progress | `41` |
| `flow:active` → `flow:queue` | In Progress → To Do | `101` |

Always run the transition alongside the label update using `scripts/jira_set_flow.py --transition`:
```bash
# Activate a ticket (queue → active + In Progress)
python3 scripts/jira_set_flow.py --key {KEY} --flow active --transition

# Complete a ticket (active → done + Done)
python3 scripts/jira_set_flow.py --key {KEY} --flow done --transition

# Park for waiting (active → waiting + Code Review)
python3 scripts/jira_set_flow.py --key {KEY} --flow waiting --transition

# Return to queue (active → queue + To Do)
python3 scripts/jira_set_flow.py --key {KEY} --flow queue --transition
```

### Org File Preservation Rule

**Both `* Time Log` and `* Notes` are append-only. Dispatch must never delete or overwrite either.**

When rebuilding the daily org file, the order is always:
1. `#+title` / `#+date` headers
2. `* Time Log` — extracted verbatim from existing file, written back unchanged
3. `* Kanban Board` — rebuilt from Jira on every run
4. `* Notes` — extracted verbatim from existing file, written back unchanged

The `scripts/dispatch` script implements `extract_section()` to capture each preserved block up to the next `* ` heading. Do not bypass it by writing the org file directly. If you ever write to the daily org file, preserve both the Time Log and Notes lines exactly as found.


### Pull Priority (within a lane)

1. **Due date override** — if a ticket has a due date within the next 2 days, it jumps to the front of its lane regardless of U+I score
2. Lowest Urgency + Importance sum wins (e.g., U1+I1=2 beats U2+I2=4)
3. Tie-break: prefer lower Jira key number (older = waited longer)

### Due Date Awareness

When querying the queue, always check for tickets with upcoming due dates:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels in ("flow:queue","flow:waiting") AND due <= 2d ORDER BY due ASC' \
  --fields key,summary,labels,duedate
```

**Due date rules:**
- Tickets due **today or tomorrow**: surface immediately to the user as a priority alert — "⚠️ <PROJECT>-XXX is due {date} — pull it active?"
- Tickets due **within 2 days**: jump to front of their lane queue, bypassing U+I sort
- `flow:waiting` tickets with a due date: remind the user even though they don't occupy a WIP slot — they may need to be re-activated to complete before the deadline
- When dispatching, always run the due-date check first before the standard U+I sort

**Alert format (due date reminder):**
```
⚠️  Due soon: <PROJECT>-341 — 1080 Fix Rollout Strategy
    Due: 2026-05-28 (Wed) | Status: flow:waiting
    Action: Pull active to confirm weekly fix ran, then close.
```



## Workflow

### Scenario A — "This One's Done"

User completes a ticket. You:

1. **Identify the lane** the completed ticket was in (Urgent/Manual/Background)
2. **Check approval status** before closing:
   ```bash
   cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
   python3 scripts/jira_approval.py --key {COMPLETED_KEY}
   ```
   - If approval is **pending**: warn the user — "🔏 {KEY} has pending approval from {names}. Mark done anyway, or wait?"
   - If approval is **declined**: flag it — "❌ {KEY} was declined by {name}. Resolve before closing?"
   - If **approved** or **no approvals configured**: proceed normally
3. **Mark done in Jira** — one script call handles label + status transition:
   ```bash
   python3 scripts/jira_set_flow.py --key {COMPLETED_KEY} --flow done --transition
   ```
3. **Update the issue file** — add a WORKLOG entry with completion note
4. **Stop the timer** for the completed ticket:
   ```bash
   /home/wweeks/git/projects/scripts/tl.py stop {COMPLETED_KEY}
   ```
   This fills in the End time and Duration in the `* Time Log` org table automatically. Use the Jira-format duration from the output in the WORKLOG line.
5. **Pull next ticket** from that lane's queue (see Pull Priority above)
6. **Activate in Jira** — one script call handles label + status transition:
   ```bash
   python3 scripts/jira_set_flow.py --key {NEW_KEY} --flow active --transition
   ```

   **WIP gate:** Never activate a 4th ticket to In Progress. The 3 active slots (one per lane) map directly to 3 In Progress tickets in Jira. If a slot is already occupied, park the incoming ticket at `flow:queue` / To Do.
7. **Start the timer** for the new ticket:
   ```bash
   /home/wweeks/git/projects/scripts/tl.py start {NEW_KEY}
   ```
   This adds a new `active` row to the `* Time Log` table automatically.
8. **Update `* Scheduled — Upcoming`** — add a future time block for the new ticket; do not touch past entries
9. **Rewrite `* Kanban Board`** with the updated active set
10. **Update the Confluence gemba board** — refresh the active items list
11. **Commit and push** all changes

### Scenario B — "What Should I Work On?"

Show the user their current 3 active tickets plus running timers, written in <YOUR_NAME>'s direct style:

```bash
# Get timer status first
/home/wweeks/git/projects/scripts/tl.py status

# Check approvals for all active tickets
python3 scripts/jira_approval.py --keys <PROJECT>-XXX,<PROJECT>-YYY,<PROJECT>-ZZZ
```

Then display:
```
Here's your current active set:

🔴 Urgent:     <PROJECT>-XXX — {summary}
               Next: {first open TODO from issue file}
               ⏱  {elapsed} (since {start_time})

🔵 Manual:     <PROJECT>-XXX — {summary}
               Next: {first open TODO from issue file}
               ⏱  {elapsed} (since {start_time})
               🔏  Needs approval: <USER_C> Bonney

🟢 Background: <PROJECT>-XXX — {summary}
               Next: {first open TODO from issue file}
               ⏱  {elapsed} (since {start_time})
```

Show the `🔏 Needs approval: {names}` line only for tickets with pending approvals. This tells the user who to chase.
```

If a slot is empty: "Nothing active in the 🟢 Background lane right now — that slot is open. Run `dispatch` to pull the next one."

### Scenario C — "Rebalance" or "Swap"

User wants to swap a ticket for another in the same lane:
1. Move current ticket back to `flow:queue`
2. Pull the specified (or next-priority) ticket to `flow:active`
3. Update org file and gemba board

## `dispatch` Command

Running `dispatch` in the terminal is the fastest way to refresh the calendar. It:

1. Queries Jira for all `flow:active` tickets
2. Classifies each into a lane using urgency/agentic/importance labels
3. Pulls the first open `- [ ]` TODO from each issue file as `:NEXT:`
4. **Appends** a new row to `* Time Log` for any newly activated ticket (Start = now)
5. **Rewrites** `* Scheduled — Upcoming` — but ONLY entries with future start times; past entries are preserved
6. **Rewrites** `* Kanban Board` entirely (it is a status board, not a calendar)
7. Never touches `* Notes`

```bash
dispatch
```

Source: `scripts/dispatch` — added to `~/.bashrc` as an alias.

## Calendar Integration — Org-Mode

The daily note lives at `planner/$(date +%m-%d).org` and has three distinct sections with different ownership rules:

### Section Ownership Rules (CRITICAL)

| Section | Owner | Rule |
|---------|-------|------|
| `* Time Log` | Append-only | **NEVER overwrite or delete rows.** Dispatcher and worklog skill only append new rows. This is the historical record. |
| `* Scheduled — Upcoming` | Dispatcher | **Only add or update entries whose scheduled time is in the future.** If a scheduled block's start time has already passed, leave it alone — it becomes part of the historical record. |
| `* Kanban Board` | Dispatcher | Always rewrite entirely — it is a live status board, not a calendar. |
| `* Notes` | Human | Never touch. |

### Time Log Format

The `* Time Log` table tracks every ticket touched during the day. One row per work session.

```org
* Time Log — {YYYY-MM-DD}
# Append-only. Dispatcher and worklog skill add rows here. Never overwrite past entries.

| Start | End   | Key       | Summary                                        | Duration | Worklog |
|-------|-------|-----------|------------------------------------------------|----------|---------|
| 08:21 | 08:33 | <PROJECT>-395 | Azure AI - Resource Access - Grant Read Access | ~15m     | 0.25h   |
| 08:45 |       | <PROJECT>-341 | 1080 Fix - Rollout Strategy                    | active   |         |
```

**When to append a Time Log row:**
- Dispatcher pulls a new ticket → append a row with Start = now, End = blank, Duration = `active`
- jira-worklog logs time → fill in the End time and Duration/Worklog for the matching row (or append a new row if none exists)
- Ticket moves to `flow:waiting` or `flow:done` → fill in End time

**Duration conventions:**
- `active` — currently in progress (End is blank)
- `~15m`, `~1h`, `~2h30m` — approximation matching the Jira worklog
- Worklog column = exact value logged to Jira (e.g., `0.25h`, `1h`)

### Scheduled — Upcoming Format

```org
* Scheduled — Upcoming
# Dispatcher writes here. Only future time slots are added or updated — past rows are never touched.

*** TODO [[https://<YOUR_ATLASSIAN>.atlassian.net/browse/{KEY}][{KEY}]] — {Summary}
    SCHEDULED: <{YYYY-MM-DD} {Day} {HH:MM}-{HH:MM}>
    :NEXT: {Next action from issue file}
```

**Past-entry protection rule:** Before writing to `* Scheduled — Upcoming`, check the current time. Any entry whose `SCHEDULED` start time is earlier than now must not be modified or removed. Only add new entries or update entries with future start times.

### Slot Preferences by Lane

| Lane | Time Block | Rationale |
|------|-----------|-----------|
| 🔴 Urgent | 07:00–08:00 | Tackle blockers first thing |
| 🔵 Manual | 09:00–10:00 | Deep focus for hands-on work |
| 🟢 Background | 13:00–14:00 | Kick off and monitor in afternoon |

If the preferred slot has already passed, use the next available 1-hour block after the current time (round up to the next half-hour).

### Jira API Note

Use `jira_search.py` for all queue reads — it calls `POST /rest/api/3/search/jql` internally:

```bash
python3 scripts/jira_search.py --jql 'project = INFRA AND labels = "flow:active"'
```

## Stakeholder Escalation — "Prioritize This for [Person]"

When the user says a ticket is from a stakeholder (manager, director, executive) and needs to be prioritized above the current queue:

1. **Find the Jira ticket** matching the SDP case or description
2. **Set urgency:1 and importance:1** on the ticket — this gives it U1+I1=2, the lowest possible sum, ensuring it wins the next urgent pull
3. **If the stakeholder has multiple tickets**, set all of them to urgency:1, importance:1
4. **If displacing a current active ticket** (e.g., bumping <PROJECT>-356 to make room):
   - Move the displaced ticket back to `flow:queue`
   - Pull the stakeholder ticket to `flow:active`
   - Update the Time Log: close the displaced ticket row (fill in End), open a new row for the incoming ticket
5. **Note the requestor** in the issue file and planner `:REQUESTOR:` field so the escalation is visible
6. **Commit with clear message** referencing the stakeholder and both tickets

### Label update commands for escalation

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Elevate to urgency:1, importance:1 (replace whatever scores are currently set)
python3 scripts/jira_set_labels.py --key {KEY} \
  --remove "urgency:2" --remove "urgency:3" --remove "urgency:4" \
  --remove "importance:2" --remove "importance:3" --remove "importance:4" \
  --add "urgency:1" --add "importance:1"

# Return displaced ticket to queue
python3 scripts/jira_set_flow.py --key {DISPLACED_KEY} --flow queue --transition

# Activate escalated ticket
python3 scripts/jira_set_flow.py --key {KEY} --flow active --transition
```

---



When Graph API credentials are available (`GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_TENANT_ID` in `.env`), the skill will:

1. **Query free/busy**: `GET /me/calendarView?startDateTime=...&endDateTime=...`
2. **Find open slots**: Filter for 1-hour blocks not occupied by existing events
3. **Create event**: `POST /me/events` with subject `[{LANE}] {KEY} — {Summary}`
4. **Set reminder**: 5 minutes before

### Graph API Auth Setup (Future)

Requires an Entra app registration with:
- `Calendars.ReadWrite` delegated permission
- OAuth2 authorization code flow or device code flow
- Token cached in `.env` or keyring

Reference: <PROJECT>-371 (AI - Graph Teams - Build Production Auth for QA) established the auth pattern.

## Determining Lane Membership

To classify a ticket into a lane, use `scripts/jira_fetch_ticket.py`:

```bash
python3 scripts/jira_fetch_ticket.py --key {KEY}
# Labels line shows: urgency:N importance:N agentic:N flow:*
```

Parse the scores from labels:
- `urgency:N` → Urgency score
- `importance:N` → Importance score
- `agentic:N` → Agentic score

Classification logic:
```
if urgency <= 2:
    lane = "urgent"
elif agentic >= 4 and importance <= 3:
    lane = "manual"
elif agentic <= 2:
    lane = "background"
else:
    lane = "manual"  # default fallback
```

## Querying the Queue

To find the next ticket for a lane, use `jira_search.py`:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Next Urgent ticket
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels = "flow:queue" AND labels in ("urgency:1","urgency:2") ORDER BY created ASC'

# Next Manual ticket
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels = "flow:queue" AND labels in ("agentic:4","agentic:5") ORDER BY created ASC'

# Next Background ticket
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels = "flow:queue" AND labels in ("agentic:1","agentic:2") ORDER BY created ASC'

# Full board state (active + waiting)
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels in ("flow:active","flow:waiting") ORDER BY updated DESC'
```

## Updating the Gemba Board

After any dispatch action, update `confluence/<PAGE_ID>-Infrastructure-Backlog-Meeting-Prep.md`:

1. Update the WIP Status line: `### WIP Status: 🟢 3 Active / 3 Limit`
2. Update the Flow Lanes table with new Active items
3. Publish:
   ```bash
   python3 scripts/publish-markdown-to-confluence.py <PAGE_ID> \
     confluence/<PAGE_ID>-Infrastructure-Backlog-Meeting-Prep.md
   ```

## Commit Pattern

```bash
git add -A && git commit -m "feat: dispatch {KEY} to {lane} lane

Completed: {COMPLETED_KEY}
New active: {KEY} ({lane})
Scheduled: {date} {time}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" && git push
```

## Current Active Set

As of 2026-05-21:

| Lane | Key | Summary |
|------|-----|---------|
| 🔴 Urgent | <PROJECT>-358 | Fabric - Java POC - Build UMI Microservice for Base64 Offload (SDP #<SDP_ID> — <USER_NEW>) |
| 🔵 Manual | (open — <PROJECT>-357 next at U1+I1=2) | Entra - Security Groups - Create App Dev Fabric Access Groups |
| 🟢 Background | <PROJECT>-390 | Web Platform - Minimal SSR - Spike Zero-Dependency Server-Rendered Rewrite |

## Important Notes

- The `.env` file at `~/git/projects/.env` contains `CONFLUENCE_EMAIL` and `WWEEKS_CONFLUENCE_API_TOKEN`
- Jira API base: `https://<YOUR_ATLASSIAN>.atlassian.net`
- Auth: Basic auth with `${CONFLUENCE_EMAIL}:${WWEEKS_CONFLUENCE_API_TOKEN}`
- Org files live in `planner/` with format `MM-DD.org`
- The backlog page ID is `<PAGE_ID>`
- Always update both the org file AND the Confluence gemba board on dispatch
- Never exceed 3 active — finish or park before pulling
