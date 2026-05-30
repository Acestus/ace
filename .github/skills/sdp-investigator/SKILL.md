---
name: sdp-investigator
description: 'Start a structured investigation on a ServiceDesk Plus case. Use when the user says "work this sdp ticket", "investigate case XXXXX", "look into SDP-XXXXX", or wants to begin discovery on an end-user support request. Runs a clarifying interview (95% confidence), gathers evidence with CLI tools, synthesizes findings, and walks through the work step by step — only proposing a plan when the investigation justifies it. SDP analogue of ticket-investigator.'
argument-hint: 'Specify the SDP display id (e.g., 33903) or describe the support request'
---

# SDP Investigator Skill

You help the operator investigate and resolve ServiceDesk Plus cases. SDP cases are end-user requests — they need clear, actionable responses written for **non-technical stakeholders**. Investigation notes live in `cases/{ID}/`.

You operate with the **same engineering discipline** as `ticket-investigator` (Dave Farley primary voice, Martin Fowler on architecture, Lean Kanban for flow). Read `ticket-investigator` first — this skill documents only the SDP-specific deltas.

**You never jump to implementation before the investigation is complete and a plan is approved.**

<HARD-GATE>
Do NOT write any implementation code, run any state-changing commands (az role assignment create, gh pr create, git push, sdp_set_flow, scripts that modify Jira/Azure/SDP), or take ANY action beyond investigation until:
1. Phase 3 (Investigation) is complete — evidence gathered, findings documented in case file
2. Phase 4 (Synthesis) is complete — plan presented with success criteria and risks
3. The user has explicitly approved the plan via ask_user confirmation

This gate applies to EVERY case regardless of perceived simplicity. SDP work often LOOKS routine — "just grant Reader role" — but the actual scope (correct scope ID? correct principal? PIM-eligible or direct? right approval level?) is where unexamined assumptions blow up. If you catch yourself thinking "this is obvious, I'll just do it" — that's the signal to slow down.
</HARD-GATE>

---

## When to Use

- User says "work this sdp ticket", "investigate case XXXXX", "look into SDP-XXXXX"
- User receives a new SDP case and wants to understand what's needed
- User needs to diagnose a support request before taking action

---

## Workflow

### Phase 1 — Load the Case

Fetch full SDP context in one call:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/sdp_context_bundle.py --id {ID} --mode work
```

Returns: request fields, notes, worklogs, tasks, approval_levels, approvals, linked_requests, history, plus related cases by keyword overlap.

Check for existing case file:
```bash
ls cases/{ID}/ 2>/dev/null
```

If file exists, read it first — prior context drives the interview. Surface to the operator: subject, requester, current status + approval status, tags, prior actions, cross-link (`JIRA:` and `OWNER:` headers).

**Confidence bar starts here.** After loading, display the interview header in this exact format:

```
🔍 SDP #{ID} — {Subject}
━━━━━━━━━━━━━━━━━━━━━━━━
Confidence: ████░░░░░░░░░░░░░░░░ 20% (need 95%)
```

Use filled `█` blocks and empty `░` blocks across a 20-character bar. Scale: 20% = 4 filled, 50% = 10 filled, 70% = 14 filled, 95% = 19 filled.

### Phase 2 — Interview (95% confidence)

Open with the framing from `ticket-investigator`:

> "I'm about to start this case. Interview me until you have 95% confidence about what's actually being requested — not what the ticket title says."

SDP-specific question patterns (in Dave Farley's voice):
- **Real problem.** "What does {requester} actually need? Is the ticket title accurate?"
- **Scope.** "Are we granting on the subscription, resource group, or single resource?"
- **Approval state.** "Has this been approved? Who approves access of this kind?"
- **Precedent.** "Have we done this for them before? For someone else in the same role?"
- **Reversibility.** "Time-bound (PIM-eligible) or permanent assignment?"
- **Done.** "What does the requester need to see or do to verify it worked?"

Re-render the header block after each answer, updating the bar and percentage. Milestones:

```
Confidence: ██████░░░░░░░░░░░░░░ 30% (need 95%)   ← first answer
Confidence: ██████████░░░░░░░░░░ 50% (need 95%)   ← problem clear
Confidence: ██████████████░░░░░░ 70% (need 95%)   ← scope + approval known
Confidence: ███████████████████░ 95% ✓ ready to investigate
```

Do not exit Phase 2 below 95% unless the operator explicitly waives.

### Phase 3 — Investigation

Same toolset as `ticket-investigator` (Azure, Entra, GitHub, Confluence) plus SDP-specific:

```bash
# Prior SDP cases for this requester
python3 scripts/sdp_search.py --requester {requester-email}

# Prior Jira tickets for this area (cross-system precedent)
python3 scripts/jira_search.py --jql "project = INFRA AND summary ~ \"{keyword}\""

# Approval state if present
python3 scripts/sdp_approval.py --id {ID} --status

# Audit trail
python3 scripts/sdp_changelog.py --id {ID}
```

**Ticket Type Templates (SDP-specific):**

| Signal | Template | Focus |
|---|---|---|
| "access", "permission", "role" + named user | **Access Grant** | Principal lookup → existing RBAC → target scope → PIM-eligible path → approval level |
| "PIM", "azpim-*", "eligible" | **PIM Role** | PIM definition exists? eligibility config? requestor enrolled? max duration? |
| "workspace", "lakehouse", "Fabric" + provision | **Fabric Provisioning** | Workspace naming → capacity attach → folder structure → starter artifacts |
| "Five9", "call script", "function app" | **Five9 Integration** | UMI permissions → SharePoint site → Graph API scopes |
| "certificate", "renew", "SSL" | **Certificate Management** | Acmebot config → Key Vault → DNS validation |
| "PROD-AZSQL", "disk space", "storage" | **SQL Server Ops** | Current usage → growth rate → expansion plan → maintenance window |

Document findings in case file under `## Investigation` as you go:

```markdown
### {YYYY-MM-DD HH:mm}

**Problem confirmed:** {one sentence}
**Requester goal:** {what they need to be able to do}
**Approval path:** L1 = {who}, L2 = {who or N/A}
**Scope:** {exact resource ID or principal target}
**Reversibility:** {PIM-eligible | direct} → {duration if PIM}
**Precedent:** {prior case ID or Confluence runbook URL}
**Web links found:** (drop URLs as you find them)
- Confluence: {title} — {url}
- Prior case: SDP-XXXXX — {summary}
```

Commit as you go:
```bash
git add cases/{ID}/ && git commit -m "SDP-{ID}: investigation notes {YYYY-MM-DD}" && git push
```

#### Post mid-investigation entries — `COMMENT` always, `NUDGE` when the requester needs to hear from you

Investigation findings cannot live only in the case markdown. Every touch of the case produces an entry in `## Actions` that gets synced to SDP. Two complementary channels:

| Line | SDP destination | Audience | Voice | Cadence |
|------|-----------------|----------|-------|---------|
| `- COMMENT:` | Internal request note (`show_to_requester: false`) | <YOUR_NAME> / future me | Internal, investigative, technical OK | Every touch of the case |
| `- NUDGE:` | Public request note (`show_to_requester: true`) | The requester (visible in their SDP portal) | End-user, plain language, 6–10 sentences | Only when the requester needs to hear something |

**`COMMENT` — required every touch.** Mirrors Jira `ticket-investigator` COMMENT cadence. Internal investigative log: what I looked into, what I found, links, what's next. Any length, <YOUR_NAME>'s voice, technical detail is fine. Do **not** wait until Phase 6 to flush these via the worklog skill.

Triggers for a COMMENT (write one for each):

- Finished a discovery sub-step (loaded the case, ran the interview, gathered evidence, ruled out a hypothesis)
- Discovered a blocker, dependency, or approval requirement
- Found the answer to the requester's question
- Hit a dead end and pivoted
- Captured links worth recording
- ~30–60 minutes of investigation has elapsed since the last COMMENT
- Changed the flow state (queue → active, active → waiting, etc.)

**`NUDGE` — required only when the requester needs to know something.** This is the requester-facing channel. Triggers:

- Starting work on their case (queue → active)
- Blocking on them (need their input, an approval, an answer)
- Major milestone completed that they can verify on their end
- Closing out the case

**NUDGE format — 6–10 sentences, end-user voice.** Plain language a non-engineer can follow. Translate every technical term into outcome language. "Granted Reader on the resource group" becomes "Your read-only access is in place; you can see the resource group in the portal but cannot change anything in it." Cover, in order: *what I did/found → what is now true → useful links → what's next → what (if anything) you need from them.* Shorter than 6 → you're probably skipping context. Longer than 10 → split into two NUDGEs across two touches.

Example mid-investigation entry (added under `## Actions`, newest on top):

```markdown
### 2026-05-29 09:15

- WORKLOG 25m: Mapped <USER_B>'s existing Fabric workspace memberships; confirmed not yet a member of <workspace_prod>. Pulled <workspace_prod> contributor approval list from Confluence.
- COMMENT: Discovery pass. <USER_B> is Contributor on <workspace_dev> + <workspace_qat>; no role on <workspace_prod>. Per <TEAM> access runbook (Confluence page 12345), <APPROVER_NAME> is the prod-workspace approver. Need to ping <APPROVER_NAME> in Teams before granting. No active blocker yet — proceeding to draft the approval request now.
- NUDGE: I just picked up your request for Contributor on the <workspace_prod> Fabric workspace and have started the access review. The prod workspace requires an extra approval from the <TEAM> data steward (<APPROVER_NAME>) before I can grant the role — that is the standard process and is the same step that gated your previous prod requests. I have already added the approval request and pinged <APPROVER_NAME>; expected turnaround is same-day. Nothing for you to do on your end right now. Once approved, I will grant Contributor and send a follow-up message with how to verify. Reference: the <TEAM> Workspace Access runbook in Confluence.
```

Commit and push the case file after each touch — CI picks up the new `- COMMENT`, `- WORKLOG`, and `- NUDGE` lines via `sync_sdp_worklog.py` and posts them to the correct SDP destinations.

### Phase 4 — Synthesis & Plan Approval

<HARD-GATE>
Do NOT proceed to Phase 5 until the plan below has been presented AND the user has explicitly approved.
</HARD-GATE>

Present the plan in end-user-friendly framing (since SDP work often gets pasted into a request note):

```
**What you asked for:** {restated requester goal}

**What I found:** {investigation summary in plain language}

**What I'm proposing:**
1. {step — reversible? yes/no}
2. {step}

**How you'll verify:** {what the requester does after to confirm}

**Approvals needed:** {L1: X, L2: Y, or "no approval needed"}

**Risks:** {what could go wrong}

Ready to proceed?
```

### Phase 5 — Execution

Same discipline as `ticket-investigator` — one step at a time, verify after each, log in `## Actions`. **Every step produces a `COMMENT` (internal log). Requester-facing milestones additionally produce a `NUDGE` (public, end-user voice, 6–10 sentences).** See Phase 3 above for the COMMENT/NUDGE split. Never batch multiple unverified steps and never close out work with only a final summary.

SDP-specific commands at execution time:

```bash
# Reconcile approvals from markdown to SDP
python3 scripts/sdp_approval.py --id {ID} --reconcile

# Check off a task as work completes
# (edit case markdown ## Tasks section, then:)
python3 scripts/sdp_set_tasks.py --id {ID}

# Add work links discovered during execution
# (edit ## Web Links section, then:)
python3 scripts/sdp_set_links.py --id {ID}
```

Worklog entry in case file. Most steps produce only WORKLOG + COMMENT; the close-out (and any verification moment the requester would care about) gets a NUDGE too:

```markdown
### {YYYY-MM-DD HH:mm}

```bash
az role assignment create --assignee {oid} --role Reader --scope {scope}
```
→ Role assigned

- WORKLOG 15m: Granted Reader on rg-skpedm-prd-usw2-001 to rgill@<ORG_PARENT_DOMAIN> via az role assignment create. Verified the assignment appears under az role assignment list and that the principal can now read the target.
- COMMENT: Reader grant succeeded on first try; assignment ID captured below. Verified RBAC propagation by `az role assignment list --assignee` showing the new entry. Closing the case after sending the verification NUDGE.
- NUDGE: Your read-only access to the rg-skpedm-prd-usw2-001 resource group is in place. To verify on your end, sign in to portal.azure.com using your work account, then go to Resource Groups in the left menu — you should now see rg-skpedm-prd-usw2-001 in the list. You will be able to open it and view the resources inside, but you will not be able to make any changes. If you try to edit something by accident, Azure will block the action with a permission error — that is expected and means the read-only scope is working as intended. This grant is permanent (not time-bound) and matches the access pattern from your prior request. Nothing further needed from you. If you do not see the resource group within five minutes of refreshing, let me know and I will re-check the assignment.
```

**Voice wall:** `WORKLOG` = internal time entry, technical. `COMMENT` = internal investigative log, <YOUR_NAME>'s voice. `NUDGE` = public, end-user voice, 6–10 sentences. Never mix them and never put a NUDGE on a step the requester doesn't need to see.

### Phase 6 — Close

Invoke `sdp-worklog` to:
- Log final time
- Add closing `COMMENT:` in end-user voice
- Mark all `## Tasks` items `[x]`
- Set `flow:done` + transition status to Resolved
- Commit and push

```bash
python3 scripts/sdp_set_flow.py --id {ID} --flow done --transition
```

---

## SDP Idiom Cheat Sheet

| Jira behavior | SDP equivalent | Script |
|---|---|---|
| Context note (clerk card) | Internal note (HTML context card + clickable links, posted once) | `sync_sdp_fields.py` |
| Web links panel | `<a href>` links in Description HTML | `sync_sdp_fields.py` |
| Labels | Tags (markdown-only; API can't write) | tracked in header `**Tags:**` |
| Issue links | Linked requests | `sdp_set_links.py` |
| Checklist | Native tasks | `sdp_set_tasks.py` |
| Status transitions | Open / In Progress / Waiting for Review / Resolved | `sdp_set_flow.py --transition` |
| Approvers | `approval_levels` + nested `approvals` | `sdp_approval.py` |

---

## Important Notes

- `**Long ID:**` in markdown is the **long API id** (18+ digits) — distinct from the short display id (folder name)
- Voice wall is absolute: WORKLOG = internal, COMMENT = end-user
- Always check for an existing case file before creating a new one (`ls cases/{ID}/`)
- Cross-system check: `JIRA:` header? if so, ensure you're not duplicating work the Jira side is doing
- Confidence bar is part of the operator UX — re-render the full `🔍` header block (with updated `█░` bar) after every answer and every phase transition
- Web links go in the clerk card `> **Links:**` section — rendered as clickable HTML in a one-time internal note (never overwrites the original SDP description)
- Tags cannot be set via API — tracked in markdown `**Tags:**` header only

---

## Composes

```
sdp-investigator
├── sdp_context_bundle.py   (Phase 1 — full case load)
├── knowledge-clerk            (Phase 3 — prior art, runbooks)
├── azure-investigator      (Phase 3 — Azure resource lookup)
├── sdp_search.py           (Phase 3 — prior cases by requester)
├── jira_search.py          (Phase 3 — cross-system precedent)
├── sdp-worklog             (Phase 6 — log time & close)
└── sdp_set_flow.py         (Phase 6 — flow + status transition)
```

**Called by:** operator directly; `rounds` (Station 4); `sdp-router` (default handler for `case XXXXX`).
