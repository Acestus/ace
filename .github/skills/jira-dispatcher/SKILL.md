---
name: jira-dispatcher
description: 'Dispatch the next highest-priority Jira or SDP ticket into an open lane using the Eisenhower matrix (urgency + importance). Use when the user says "this one''s done", "assign me work", "dispatch next ticket", "what should I work on", or wants to rotate a lane. Pulls from the shared queue sorted by Q1→Q2→Q3→Q4 priority.'
argument-hint: 'Optionally specify which lane just opened up and what was completed'
---

# Dispatcher Skill

You help the operator keep lanes filled and moving. When a ticket is completed (or a lane opens), you pull the next highest-priority ticket from the shared queue and activate it. Both Jira and SDP tickets share the same queue.

## When to Use

- User says "this one's done", "rotate", "assign me work", "dispatch", "next ticket"
- User asks "what should I work on next?"
- User wants to see their current active set across all lanes
- User wants to rebalance or swap a ticket

---

## Voice & Tone

Write in <YOUR_NAME>'s voice.

- **Direct, past tense** — "Pulled <PROJECT>-360 into Lane 2. Ready."
- **Name the actual ticket** — always lead with the key and a clear summary.
- **Short status confirms** — one or two sentences. What changed, what the lane looks like now.
- **No fluff** — never write "Great news!" or "I've gone ahead and..." — just state what happened.

---

## Eisenhower Dispatch Model

All 5 lanes draw from a single shared pool of `flow:queue` tickets (Jira and SDP combined). Priority is determined by **Eisenhower quadrant** only — no lane types, no agentic scoring.

| Priority | Quadrant | urgency | importance | Label sum |
|----------|----------|---------|------------|-----------|
| 1st | Q1 — Do First | ≤ 2 | ≤ 2 | ≤ 4 |
| 2nd | Q2 — Schedule | ≥ 3 | ≤ 2 | any |
| 3rd | Q3 — Delegate | ≤ 2 | ≥ 3 | any |
| 4th | Q4 — Someday | ≥ 3 | ≥ 3 | ≥ 6 |

**Within each quadrant:** sort by `urgency + importance` sum (lower = higher priority). Tiebreak: oldest ticket first (lower Jira key or older SDP created date).

**Due date override:** a ticket with a due date within 2 days jumps to the front of its quadrant regardless of sum.

### Dispatch Query

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# All queued Jira tickets (sort client-side by Eisenhower quadrant)
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels = "flow:queue" ORDER BY created ASC' \
  --fields key,summary,labels,duedate

# All queued SDP cases
python3 scripts/sdp_search.py --tag flow:queue

# Due soon check (always run first)
python3 scripts/jira_search.py \
  --jql 'project = INFRA AND labels in ("flow:queue","flow:waiting") AND due <= 2d ORDER BY due ASC' \
  --fields key,summary,labels,duedate
```

Parse `urgency:N` and `importance:N` from labels, then sort by quadrant. Skip any SDP case with `OWNER: jira` (shadows don't occupy lanes).

### WIP Rule

- **5 lanes, 5 active slots max** — one ticket per lane
- `flow:waiting` does not count against WIP
- Cross-link shadows (`OWNER: jira` cases / `SDP:` issue headers) do not count
- Never activate a 6th ticket

---

## Workflow

### Scenario A — "This One's Done"

1. **Check approval status** before closing:
   ```bash
   python3 scripts/jira_approval.py --key {COMPLETED_KEY}
   ```
   - Pending approval → warn: "🔏 {KEY} has pending approval from {names}. Mark done anyway?"
   - Declined → flag: "❌ {KEY} was declined by {name}. Resolve before closing?"
   - Approved or none → proceed

2. **Mark done:**
   ```bash
   python3 scripts/jira_set_flow.py --key {COMPLETED_KEY} --flow done --transition
   ```
   For SDP: `python3 scripts/sdp_set_flow.py --id {ID} --flow done --transition`

3. **Stop the timer:**
   ```bash
   python3 scripts/tl.py stop {COMPLETED_KEY}
   ```

4. **Run Eisenhower sort** on all `flow:queue` tickets — identify the next Q1, then Q2, then Q3, then Q4 candidate.

5. **Activate the top candidate:**
   ```bash
   python3 scripts/jira_set_flow.py --key {NEW_KEY} --flow active --transition
   ```
   For SDP: `python3 scripts/sdp_set_flow.py --id {ID} --flow active --transition`

6. **Start the timer:**
   ```bash
   python3 scripts/tl.py start {NEW_KEY}
   ```

7. **Update the org file** — append Time Log row, update Kanban Board section.

8. **Commit and push.**

### Scenario B — "What Should I Work On?"

Show current active set with timers:

```bash
python3 scripts/tl.py status
```

Display:
```
Active lanes:

Lane 1 🟣  <PROJECT>-XXX — {summary}
           Next: {first open TODO}
           ⏱ {elapsed}

Lane 2 🔵  <PROJECT>-XXX — {summary}
           Next: {first open TODO}
           🔏 Needs approval: {name}

Lane 3 🟡  (open — next Q1 candidate: <PROJECT>-XXX)

Lane 4 🟠  {SDP-XXXXX} — {summary}
           Next: {first open TODO}

Lane 5 🔴  (open)
```

Show `🔏 Needs approval: {names}` only when pending approvals exist.

### Scenario C — "Rebalance" or "Swap"

1. Move current ticket back to `flow:queue`
2. Pull the specified (or next-priority) ticket to `flow:active`
3. Update org file Kanban Board

---

## Priority Alerts

Always run the due date check before presenting the dispatch result:

```
⚠️  Due soon: <PROJECT>-341 — 1080 Fix Rollout Strategy
    Due: 2026-05-28 (Wed) | Status: flow:waiting
    Action: Pull active to confirm weekly fix ran, then close.
```

Tickets due **today or tomorrow** → surface as a priority alert before any other dispatch action.

---

## Stakeholder Escalation — "Prioritize This for [Person]"

When a stakeholder needs a ticket pulled to the front:

1. Set `urgency:1` and `importance:1` on the ticket (Q1 — it wins the next pull)
2. If displacing a current active ticket, park it back to `flow:queue`
3. Activate the stakeholder ticket
4. Note the requestor in the issue file and planner `:REQUESTOR:` field

```bash
python3 scripts/jira_set_labels.py --key {KEY} \
  --remove "urgency:2" --remove "urgency:3" --remove "urgency:4" \
  --remove "importance:2" --remove "importance:3" --remove "importance:4" \
  --add "urgency:1" --add "importance:1"

python3 scripts/jira_set_flow.py --key {DISPLACED_KEY} --flow queue --transition
python3 scripts/jira_set_flow.py --key {KEY} --flow active --transition
```

---

## Org File Rules

**`* Time Log` and `* Notes` are append-only — never delete or overwrite either.**

Section ownership:

| Section | Owner | Rule |
|---------|-------|------|
| `* Time Log` | Append-only | Never overwrite rows — it is the historical record |
| `* Scheduled — Upcoming` | Dispatcher | Only add/update entries with future start times |
| `* Kanban Board` | Dispatcher | Always rewrite entirely |
| `* Notes` | Human | Never touch |

### Time Log Format

```org
* Time Log — {YYYY-MM-DD}

| Start | End   | Key       | Summary                  | Duration | Worklog |
|-------|-------|-----------|--------------------------|----------|---------|
| 08:21 | 08:33 | <PROJECT>-395 | {summary}            | ~15m     | 0.25h   |
| 08:45 |       | <PROJECT>-341 | {summary}            | active   |         |
```

### Scheduled — Upcoming Format

```org
* Scheduled — Upcoming

*** TODO [[https://<YOUR_ATLASSIAN>.atlassian.net/browse/{KEY}][{KEY}]] — {Summary}
    SCHEDULED: <{YYYY-MM-DD} {Day} {HH:MM}-{HH:MM}>
    :NEXT: {Next action from issue file}
```

---

## Commit Pattern

```bash
git add -A && git commit -m "feat: dispatch {KEY} to Lane {N}

Completed: {COMPLETED_KEY}
New active: {KEY}
Scheduled: {date} {time}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" && git push
```

---

## Important Notes

- `.env` at `~/git/projects/.env` — load with `export $(grep -v '^#' .env | xargs)`
- Jira API: `https://<YOUR_ATLASSIAN>.atlassian.net`
- Org files: `planner/MM-DD.org`
- WIP cap: 5 active — finish or park before pulling new
