---
applyTo: cases/**/*.md
description: Canonical structure and conventions for ServiceDesk Plus case markdown files in cases/{display_id}/
---

# SDP Case Documentation

`cases/{display_id}/{display_id} - {summary}.md` is the source of truth for every SDP request the operator works on. CI workflows reconcile it to SDP on every push to main.

## Header (top of file, immediately after H1)

```
# {display_id} - {Subject}

SDP_ID: {long_api_id}               ← required; 18+ digit internal API id
JIRA: <PROJECT>-XXX                     ← optional; only if cross-linked to a Jira issue
OWNER: sdp                          ← required; sdp | jira (decides WIP slot ownership)
Tags: way:fabric, env:prd           ← required; comma-separated; flow:* tags managed by sdp_set_flow
Urgency: 2                          ← required; 1-5 (1 = most urgent)
Importance: 3                       ← required; 1-5
Agentic: 4                          ← required; 1-5 (1 = full auto, 5 = constraint:technician)
Approvers: ryan@<ORG_DOMAIN>, ...      ← required; "—" if none
Summary: {one-line summary}         ← required
```

**Ownership rule.** `OWNER: sdp` means this case holds the SDP WIP slot. `OWNER: jira` means the linked <PROJECT>-XXX issue holds the slot — this case is a shadow that mirrors worklogs but does NOT count against any SDP lane cap.

## Required Sections (in order)

1. `## Description` — what was requested, by whom, when. Pulled from SDP on stub-create.
2. `## Investigation` — discovery findings from sdp-investigator. Newest dated entry on top.
3. `## Actions` — dated entries; each contains commands run (fenced bash) plus WORKLOG/COMMENT lines. Newest on top.
4. `## Tasks` — checkbox list reconciled to SDP native tasks. `- [x]` = done, `- [ ]` = open.
5. `## Web Links` — bullet list `- [label](url)` or bare URL. Reconciled to `[LINK]`-prefixed SDP notes (SDP has no native panel).
6. `## Linked Requests` — bullet list `- SDP-XXXXX — short note`. Reconciled to SDP linked_requests.
7. `## Approval` — level-by-level approver state. Reconciled to SDP approval_levels + approvals.
8. `## Follow-up` — **always last**. Status line + TODO checklist.

## Section Separators

Every `##` heading is followed by an empty line and then a separator line:
```
## Section Name

------------------------------------------------

(content)
```

## Action Entries

```markdown
### 2026-05-21 15:00

```bash
az role assignment create --assignee-object-id {oid} --role Reader --scope {scope}
```
→ Role assigned

- WORKLOG 15m: Granted Reader on rg-skpedm-prd-usw2-001 to rgill@<ORG_PARENT_DOMAIN>.
- COMMENT: First-try success; assignment ID captured. Closing after sending verification NUDGE.
- NUDGE: Your read-only access to rg-skpedm-prd-usw2-001 is in place. To verify, sign in to portal.azure.com and look under Resource Groups — the group should now appear. You can open it and view what is inside, but Azure will block any attempt to change something (that is expected for read-only). Nothing further needed on your end. If you do not see it within five minutes of refreshing, let me know and I will recheck.
```

**WORKLOG vs COMMENT vs NUDGE (voice wall — three channels):**

| Line | Posts as | Audience | Voice |
|------|----------|----------|-------|
| `WORKLOG <time>:` | SDP time entry (internal) | <YOUR_NAME> | Technical, terse |
| `COMMENT:` | SDP internal note (`show_to_requester: false`) | <YOUR_NAME>, future me | Internal investigative — same voice as Jira COMMENT |
| `NUDGE:` | SDP public note (`show_to_requester: true`) | The requester (visible in their SDP portal) | Plain end-user language, no jargon, 6–10 sentences |

- **COMMENT** is required on every touch — internal investigative log, same habit as Jira COMMENT lines.
- **NUDGE** is required only when the requester needs to hear something (starting work, blocking on them, milestone, close-out). 6–10 sentences end-user voice. Cover: what is now true → how to verify → useful links → what's next → what you need from them. See `sdp-worklog` skill for examples.
- A `NUDGE` that reads like a WORKLOG ("created RBAC assignment via az CLI") is wrong — rewrite for the requester. A `COMMENT` written in marketing voice is also wrong — that belongs in a NUDGE.

Time format: `15m`, `2h`, `2h30m`.

## Tasks Section

```markdown
## Tasks

------------------------------------------------

- [x] Create RBAC assignment
- [x] Verify with az role assignment list
- [ ] Email requester confirming
```

Reconciled bidirectionally by `sync_sdp_fields.py`: status toggles in markdown sync to SDP. New markdown items create SDP tasks. SDP tasks not in markdown are NOT auto-deleted (safety).

## Web Links Section

```markdown
## Web Links

------------------------------------------------

- [Azure portal — resource group](https://portal.azure.com/...)
- [Confluence runbook — Fabric access](https://...)
- https://<org_short>.atlassian.net/browse/<PROJECT>-368
```

Additive sync only — items removed from markdown are NOT auto-deleted from SDP (notes don't have stable URL identity).

## Linked Requests Section

```markdown
## Linked Requests

------------------------------------------------

- SDP-33920 — same requester, prior workspace grant
- SDP-33982 — depends on this PIM role landing first
```

Additive sync — never deletes existing links.

## Approval Section

```markdown
## Approval

------------------------------------------------

### L1
- ryan@<ORG_DOMAIN> — approved
- rajan@<ORG_DOMAIN> — pending

### L2
- vp-it@<ORG_DOMAIN> — pending
```

`sync_sdp_fields.py` will create missing levels and add missing approvers. It does NOT remove approvers (out-of-band approval removal must be done through SDP UI).

## Follow-up Section (always last)

```markdown
## Follow-up

------------------------------------------------
Status: Waiting on L2 approval from VP IT
TODO:
- [ ] Ping VP IT if not approved by Friday
- [ ] On approval, run sdp_set_flow.py --flow active --transition
```

## Cross-link Conventions

- A case with `OWNER: jira` is a **shadow** of its `JIRA:` issue. Worklogs may be mirrored manually; CI does not auto-mirror.
- A case with `OWNER: sdp` and `JIRA: <PROJECT>-XXX` is the WIP owner; the Jira side is the shadow.
- Cross-skill renderers (`start-my-day`, `weekly-summary`, `outbox-refresh`, `waiting-ticket-followup`) MUST dedupe shadows by the cross-link header so the operator isn't counted twice.

## CI Reconciliation

On push to `main`, two scripts run for changed files under `cases/`:

1. `scripts/sync_sdp_worklog.py` — newly added `WORKLOG`/`COMMENT` lines → SDP worklogs / notes
2. `scripts/sync_sdp_fields.py` — `Tags:` header + `## Tasks` + `## Web Links` + `## Linked Requests` + `## Approval` → reconciled to SDP

Both run in the `sdp-worklog-sync.yaml` workflow. A separate `sdp-transition-on-merge.yaml` workflow transitions SDP flow on PR merge when the title/branch contains an SDP ID. `sdp-approval-poll.yaml` polls pending approvals 4×/day and reports them in the workflow summary.

## SDP Status Reference (<ORG_NAME> instance)

Verified status list: **Open, On Hold, Resolved, Closed, Canceled, Waiting for Review, Waiting on End User, Waiting on Vendor, Waiting on budget, Waiting parts, Leave of Absence, Legal Hold**.

There is **no "In Progress" status** on this instance. Default flow → status mapping:

| flow tag | SDP status | Notes |
|---|---|---|
| `flow:queue` | Open | new requests |
| `flow:active` | Open | flow tag is the signal; status doesn't change |
| `flow:waiting` | On Hold | override with a Waiting * subtype for clarity |
| `flow:done` | Resolved | use Closed only after requester acceptance |

To pick a specific waiting subtype: `sdp_set_flow.py --id 33903 --flow waiting --status "Waiting on End User"`.
