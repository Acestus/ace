---
name: waiting-ticket-followup
description: 'Scan flow:waiting Linear tickets, group by stakeholder, show stale time, and draft follow-up messages. Use when the user says "follow up on waiting tickets", "who am I waiting on", "check stale tickets", or "draft follow-ups".'
argument-hint: 'Optionally specify a stakeholder name or stale-days threshold'
---

# Waiting Ticket Follow-up Skill

Use this when the job is simple: figure out who owns the next move on `flow:waiting` tickets, see how stale they are, and draft the nudge.

## When to Use

- User says "follow up on waiting tickets"
- User asks "who am I waiting on?"
- User wants stale waiting tickets grouped by person or team
- User wants ready-to-send Teams or email follow-ups

## Workflow

1. Run the report first. That shows the current waiting queue grouped by stakeholder.
2. Ask the user which stakeholder groups need a follow-up. Do not guess if they only want part of the list.
3. Run draft mode. Use `--stakeholder` if they only want one person.
4. Present the draft messages exactly as copy-paste text for Teams or email.
5. If the user wants the repo updated, add `Follow-up sent {date}` in the issue file `## Follow-up` section.

## Standard Commands

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

python3 scripts/waiting_followup.py --report
python3 scripts/waiting_followup.py --draft
python3 scripts/waiting_followup.py --stale-days 5
python3 scripts/waiting_followup.py --stakeholder "<USER_C> Bonney"
python3 scripts/waiting_followup.py --draft --stakeholder "<USER_C> Bonney"
```

## What the Script Does

- Queries Linear with:
  ```jql
# Linear: query issues in 'In Review' state, ordered by updatedAt
  ```
- Pulls the Linear identifier, title, labels, `updatedAt`, and due date
- Reads the matching `issues/{KEY} - */` markdown file
- Looks in `## Follow-up` and `## Notes` for lines like:
  - `waiting on <USER_C> Bonney`
  - `pending <USER_D> confirmation`
  - `blocked by Global Admin`
  - `- [ ] <USER_C> Bonney: Re-activate PIM assignment`
- Groups tickets by stakeholder
- Shows stale days from Linear `updated`
- Drafts one follow-up message per stakeholder

## Example Report Output

```text
✓ 4 waiting ticket follow-up items across 3 stakeholder groups

<USER_C> Bonney
KEY        STALE  DUE  SCORES     SUMMARY
---------  -----  ---  ---------  ---------------------------------------------
<TICKET-ID>  3d     —    U?/I?/A?   Fabric - Entra Group - Configure Last Modifi…
  → <TICKET-ID>: Re-activate PIM ACTIVE assignment for <RBAC_GROUP_NAME> (<USER_A>, <USER_B>, <USER_C>)
```

## Example Draft Output

```text
Hey <USER_C> Bonney —

Quick follow-up on a few tickets waiting on your side:

• <TICKET-ID> — Fabric - Entra Group - Configure Last Modified Contributor Workaround (waiting 3 days)
  → Re-activate PIM ACTIVE assignment for <RBAC_GROUP_NAME> (<USER_A>, <USER_B>, <USER_C>)

Let me know if anything's blocked or if priorities shifted.

— <YOUR_NAME>
```

## CLI Reference

```bash
python3 scripts/waiting_followup.py --report
python3 scripts/waiting_followup.py --draft
python3 scripts/waiting_followup.py --stale-days 5
python3 scripts/waiting_followup.py --stakeholder "<USER_C> Bonney"
python3 scripts/waiting_followup.py --draft --stakeholder "<USER_C> Bonney"
```

## Rules

- Always run `--report` first unless the user already told you exactly who to target.
- Keep the drafts short. One message per stakeholder.
- Use the action from `## Follow-up` when it exists. That is the ask.
- If the issue file has no clear stakeholder, say that plainly instead of inventing one.
- If the user wants repo state updated, record the follow-up in the issue file after the message is sent.

---

## Escalation Ladder

Waiting tickets follow a timed escalation path. The skill surfaces escalation status in every report and adjusts the follow-up tone accordingly.

| Stale Days | Level | Action | Tone |
|-----------|-------|--------|------|
| 1-2 | ⬜ Normal | No follow-up needed — within expected window | — |
| 3-4 | 🟡 Nudge | Draft friendly reminder | "Quick follow-up..." |
| 5-6 | 🟠 Escalate | Draft firmer message + CC manager if known | "Following up again — this is blocking..." |
| 7+ | 🔴 Flag | Surface in standup as blocked + suggest re-prioritization | "This has been waiting 7+ days. Recommend: escalate or park." |

### Report with escalation markers

When `--report` runs, add the escalation level to each ticket:

```text
<USER_C> Bonney
KEY        STALE  LEVEL       SUMMARY
---------  -----  ----------  -----------------------------------------
<TICKET-ID>  3d     🟡 Nudge    Fabric - Entra Group - Configure...
<PROJECT>-349  8d     🔴 Flag     PIM - Eligible Role Assignment...
```

### Escalation actions by level

**🟡 Nudge (3-4 days):**
- Standard follow-up draft (same as current behavior)
- Record: `Follow-up sent {date} — nudge` in issue file

**🟠 Escalate (5-6 days):**
- Draft includes urgency signal: "This is blocking {downstream ticket or lane}"
- If the stakeholder's manager is known (from Entra org lookup), CC them in the draft
- Record: `Follow-up sent {date} — escalation` in issue file
- Suggest: "Consider adding `constraint:vendor` or `constraint:stakeholder` label"

**🔴 Flag (7+ days):**
- Do NOT auto-send. Surface to the operator for a decision:
  ```
  🔴 <PROJECT>-349 has been waiting 8 days on <USER_C> Bonney.
     Options:
     1. Send final escalation (include manager)
     2. Park the ticket (flow:waiting → flow:queue) and move on
     3. Do nothing — leave it waiting
  ```
- If flagged tickets exist, add them to end-of-day standup under a `⚠️ Escalations` section

### Auto-escalation in rounds

During `Phase 5 — Close Rounds`, if any `flow:waiting` tickets have crossed an escalation threshold since the last check, surface them:

```
📬 Escalation check:
   🟡 <TICKET-ID> → 3 days waiting (nudge due)
   🔴 <PROJECT>-349 → 8 days waiting (flag — decision needed)
```

---

## Composes

```
waiting-ticket-followup
└── (standalone — reads Linear + issue files, drafts messages)
```

**Called by:** `rounds` (Phase 5), `end-my-day` (Step 5), or directly by user

**Companion skill:** `outbox-refresh` rebuilds `planner/outbox/*.md` with full newspaper-lede cards for every `flow:waiting` ticket. Run `outbox-refresh` to see the full backlog routed by stakeholder; run `waiting-ticket-followup` to draft the actual messages.


---

##  Awareness (Lanes 4–6)

ServiceDesk Plus work runs as a parallel set of three swimlanes (Lane 4 🔴 -Urgent, Lane 5 🟠 -Approval, Lane 6 🟢 -Background).  case files live under `cases/{display_id}/`. The header `OWNER: jira | sdp` decides which side holds the WIP slot:

- `OWNER: sdp` (default) — the  case is the WIP owner; counts against the  lane cap
- `OWNER: jira` — the  case is a **shadow** of a linked <PROJECT>-XXX issue; does NOT count against any  lane cap

When this skill needs to enumerate or render the operator's work, it MUST union both sources (`issues/` + `cases/`) and dedupe by cross-link (`JIRA:` header in cases, `:` header in issues). Shadows are surfaced as "(shadow of <PROJECT>-XXX)" annotations, not as independent slots.

For lane-routing and rounds claims, see `rounds` and `sdp-dispatcher`. The shared `/tmp/rounds-claims.json` uses keys `lane1`–`lane5` shared across Linear and  tickets (single ticket per lane, regardless of system).

Voice wall:  `COMMENT:` lines are **end-user voice** (plain language). Linear COMMENT lines are internal investigative voice. This skill must preserve that distinction wherever it emits or summarizes comments.

For -specific dispatch, render, or close-out, hand off to: `rounds`, `sdp-dispatcher`, `sdp-investigator`, `sdp-worklog`, `sdp-router`.
