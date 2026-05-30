---
name: sdp-router
description: 'Fuzzy intent router for ServiceDesk Plus-adjacent requests. Catches natural language about SDP cases, tickets, requests, and dispatches to the correct SDP specialist skill. Use when the user mentions an SDP ID (numeric 5–8 digits or "SDP-XXXXX") or anything about SDP cases/requests — and the intent does not exactly match another skill trigger phrase.'
argument-hint: 'Natural language — "case 33903", "what is SDP-33982", "log time on sdp 27007", "do sdp rounds", "next sdp ticket"'
---

# SDP Router Skill

You disambiguate SDP-related intent. The operator speaks naturally — "case 33903", "what's the status on that PIM request", "do sdp rounds", "any waiting sdp tickets". You route to the right specialist skill.

Companion to `jira-router`. Together they form the **ticket-router** behavior across both systems.

---

## When to Use

- User mentions a numeric ID 5–8 digits in length (likely an SDP display id)
- User mentions `SDP-XXXXX` or `case XXXXX`
- User uses SDP vocabulary: "service desk", "sdp", "approval", "requester", "end-user request"
- User says "start rounds 4/5/6" — route to `rounds`
- Intent is ambiguous between Jira and SDP

---

## Routing Table

| Trigger | Route to |
|---|---|
| `case XXXXX`, `SDP-XXXXX`, bare 5-8 digit number | `sdp-investigator` (load context) |
| "log time on sdp X", "worklog sdp" | `sdp-worklog` |
| "investigate case X", "work this sdp ticket" | `sdp-investigator` |
| "new sdp request", "add to sdp backlog", "create sdp ticket" | `sdp-backlog` |
| "dispatch sdp", "next sdp ticket", "sdp board" | `sdp-dispatcher` |
| "start rounds 4/5/6", "start sdp rounds" | `rounds` |
| "follow up on sdp", "stale sdp cases" | `waiting-ticket-followup` (it now unions both systems) |
| "sdp summary", "what got done in sdp this week" | `weekly-summary` |
| "approval status on SDP-X" | `sdp_approval.py --id X --status` (direct script) |

---

## Ambiguity Handling

When the operator says "this ticket" or "the ticket" without specifying system:

1. Check git context — most recently edited file under `issues/` vs `cases/` wins
2. Check open rounds claims (`/tmp/rounds-claims.json`) — if exactly one lane is claimed, use that ticket
3. Otherwise `ask_user` with a binary choice:
   ```
   Which one?
   - <PROJECT>-368 (most recent Jira active)
   - SDP-33903 (most recent SDP active)
   ```

For a bare 5-8 digit number, check:
- `cases/{number}/` exists → SDP case
- `<PROJECT>-{number}` matches an issue → Jira issue
- Both or neither → ask

---

## Cross-system Patterns

When the user asks something that touches both:
- "what am I working on" → render full board (Lanes 1-6) via `start-my-day`
- "follow up on stuck stuff" → `waiting-ticket-followup` (unioned)
- "weekly status" → `weekly-summary` (unioned by closed-this-week from both)

---

## Important Notes

- 5-8 digit numbers are almost always SDP display IDs. INFRA project keys always have the `INFRA-` prefix in this org.
- Long SDP ids (18+ digits like `110247000036725698`) are internal API ids — they appear in `**Long ID:**` markdown headers. If the operator pastes one, look it up via `sdp_lib.fetch_request()` to get the display id.
- The router never executes side-effecting work itself — it always hands off to the named specialist skill.

---

## Composes

```
sdp-router
├── sdp-investigator
├── sdp-worklog
├── sdp-backlog
├── sdp-dispatcher
├── rounds          (unified: SDP cases work in lanes 1–5 alongside Jira tickets)
├── waiting-ticket-followup   (cross-system)
├── weekly-summary            (cross-system)
└── start-my-day              (cross-system board)
```

**Called by:** operator naturally; `jira-router` (as fallback when intent doesn't match Jira keys).
