---
name: sdp-worklog
description: 'Log time, comments, nudges, tasks, and flow transitions on ServiceDesk Plus cases via markdown files. Use when the user says "log time to sdp", "update sdp", "worklog sdp", or wants to record/close work on an SDP case. Field-aware: handles WORKLOG, COMMENT (internal), NUDGE (requester-visible), ## Tasks, ## Web Links, ## Linked Requests, ## Approval, and flow:* transitions in one pass. Commits and pushes to main; CI reconciles to SDP.'
argument-hint: 'Specify the SDP display id (e.g., 33903), time spent (e.g., 2h, 30m), and a description. Optional: a new flow state.'
---

# SDP Worklog Skill

You help the operator log time, post internal investigative comments, push requester-facing nudges, check off tasks, manage links, update approval state, and transition flow on SDP cases — all by editing the case markdown under `cases/{ID}/`.

When the file is committed and pushed to `main`, two workflows run:
- `sdp-worklog-sync.yaml` runs `sync_sdp_worklog.py` (WORKLOG → SDP worklog, COMMENT → SDP internal note, NUDGE → SDP public note visible to the requester) AND `sync_sdp_fields.py` (Tags, Tasks, Web Links, Linked Requests, Approval reconciled to SDP)

---

## When to Use

- User wants to log time on an SDP case
- User says "log time to sdp", "update sdp", "worklog sdp", "track time on sdp"
- User wants to close an SDP case
- User wants to check off a task, add a link, add an approver, or transition flow
- User wants to push a requester-visible nudge on an SDP case

---

## Workflow

### Step 1 — Gather Information

Use `ask_user` (one question at a time) for any missing values:

1. **SDP display id** — 5-8 digit number, e.g. `33903`. If unsure, list `cases/` and let them pick.
2. **Time spent** — `15m`, `2h`, `2h30m`. Required for WORKLOG entries.
3. **What was done** — internal-voice description (goes in WORKLOG).
4. **What to log internally + tell the requester** — internal investigative COMMENT (required, every touch) and, if the requester needs to hear something, a public NUDGE (6–10 sentences, end-user voice).
5. **New flow state** — `active`, `waiting`, `done`, or "no change".
6. **Tasks to check off / add / reopen** — optional.
7. **Links to add** — optional.

If the operator already supplied a complete request, skip the questions.

### Step 2 — Locate the Case File

```
cases/{display_id}/{display_id} - {summary}.md
```

If the folder is missing, scaffold it via `sdp_create_stub.py --id {display_id}` — that pulls subject + description from SDP and writes the canonical template.

### Step 2.5 — Confirm `Long ID` (long API id)

The header `**Long ID:**` is the **long** API id (18+ digits). The folder is the short display id. They must both be correct, or the sync posts to the wrong ticket.

- If `**Long ID:**` is missing → fetch it: `python3 scripts/sdp_context_bundle.py --id {display_id} --mode brief` (the bundle prints the long id).
- If present → trust it (the migration + investigator already verified).

### Step 3 — Add the Action Entry

Insert above `## Follow-up`, above any existing dated entries (newest on top):

```markdown
### {YYYY-MM-DD HH:mm}

```bash
{command run, if any}
```
→ {result}

- WORKLOG {time}: {internal-voice description}
- COMMENT: {internal investigative log — REQUIRED, every touch, <YOUR_NAME>'s voice, any length}
- NUDGE: {public end-user-voice update — REQUIRED only when the requester needs to hear something, 6–10 sentences}
```

**Voice wall (mandatory) — three channels, three audiences:**

| Line | Posts as | Audience | Voice | When |
|------|----------|----------|-------|------|
| `WORKLOG` | SDP time entry (internal) | <YOUR_NAME>, future me | Technical, terse | Every touch (time always logged) |
| `COMMENT` | SDP internal note (`show_to_requester: false`) | <YOUR_NAME>, future me | Internal investigative — same voice as Jira COMMENT | Every touch |
| `NUDGE` | SDP public note (`show_to_requester: true`) | The requester, in their SDP portal | Plain end-user language, no jargon | Only when they need to know something |

A `NUDGE` that reads like a WORKLOG ("created RBAC assignment via az CLI") is wrong — rewrite for the requester. A `COMMENT` written in marketing-friendly end-user voice is also wrong — that's a NUDGE; the COMMENT should be the investigative log behind the curtain.

**COMMENT cadence — every touch produces a COMMENT.** This is the internal narrative that keeps the SDP case in sync with what is actually happening in the repo. No length target — match Jira COMMENT habits (a sentence or a paragraph, whatever the touch warrants).

**NUDGE cadence — only when the requester needs to hear something.** Triggers:

- Starting work on their case (queue → active)
- Blocking on them (need their input, an approval, a confirmation)
- A milestone they can verify on their end
- Closing out the case

Target **6–10 sentences** per NUDGE. Cover, in order:

1. *What I did or what is now true on your case*
2. *How to verify on your end (or "nothing for you to do")*
3. *Any links the requester might want (runbook, portal URL)*
4. *What is next on my side and the expected timeframe*
5. *What (if anything) I need from them*

Good NUDGE examples (the right length and voice):

- "I have granted you read-only access to the rg-skpedm-prd-usw2-001 resource group as requested. To verify, sign in to portal.azure.com with your work account and look under Resource Groups — rg-skpedm-prd-usw2-001 should now appear in the list. You will be able to open it and view what is inside, but any attempt to change something will be blocked by a permission error, which is the expected behavior for read-only. This grant is permanent (not time-bound) and matches what you have on the dev and qat resource groups. There is nothing for you to do on your end. If you do not see the resource group within five minutes of refreshing the portal, let me know and I will recheck. The change is also recorded in the audit log against your account."

- "Your new Fabric workspace ws_fivenine_prd is provisioned and attached to the F64 capacity. To connect it to your Git repo, open the workspace, go to Workspace settings → Git integration, and authenticate with your personal access token (the same one you use for the dev workspace). I have already added you as a Contributor and <APPROVER_NAME> as Admin per the <TEAM> access runbook. The starter Lakehouse lh_fivenine_prd_brz is in the workspace root — you can begin loading bronze data immediately. Next on my side: I will set up the scheduled refresh for the silver pipeline once you confirm the bronze ingest is running. There is no SLA on that next step; reply on this ticket when you are ready."

- "Storage on PROD-AZSQL-03 has been expanded by 100 GiB and the database is back to roughly 30% free space. No action needed on your end and no downtime occurred during the expansion — the operation is online. I have also opened a follow-up ticket to investigate why the growth rate spiked over the last week so we can decide whether to re-tier the database. You should see normal performance immediately. The change shows up in the audit log against the maintenance window."

Good COMMENT examples (internal, <YOUR_NAME>'s voice — any length):

- "Confirmed <USER_B> is not yet on <workspace_prod>. Pinged <APPROVER_NAME> in Teams for the <TEAM> approval; expect same-day."
- "Tried az role assignment create against the subscription scope first — got 409 because the assignment already existed at a higher scope. Reduced to the RG scope and it took. Noted for the runbook."

### Step 4 — Update Structured Sections (if needed)

Edit these sections of the case markdown — CI reconciles them on push:

**Check off tasks:**
```markdown
## Tasks

- [x] Create RBAC assignment
- [x] Verify with az role assignment list
- [ ] Email requester confirming
```

**Add a web link:**
```markdown
## Web Links

- [Azure portal — resource group](https://portal.azure.com/#@.../rg-...)
- [Confluence runbook — Fabric access grants](https://...)
```

**Link a related request:**
```markdown
## Linked Requests

- SDP-33920 — same requester, prior workspace grant
```

**Update approval state:**
```markdown
## Approval

### L1
- ryan@<ORG_DOMAIN> — approved
- rajan@<ORG_DOMAIN> — pending
```

### Step 5 — Flow Transition (if asked)

If the operator said done/waiting/active, ALSO update the header tag and run the transition script:

1. Edit the `Tags:` header line to swap the `flow:*` entry (CI will reconcile)
2. Run locally for instant transition: `python3 scripts/sdp_set_flow.py --id {ID} --flow {state} --transition`

### Step 6 — Commit & Push

```bash
git add cases/{ID}/
git commit -m "SDP-{ID}: {short description} {YYYY-MM-DD}

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
```

Always to `main`. CI picks it up.

### Step 7 — Confirm

Report:
- What was logged (id, time, voice)
- Tasks/links/approval changes
- Flow transition (if any)
- Push status

---

## Time Format

`15m` `30m` `1h` `2h` `2h30m` `1h45m`. Anything else: ask for clarification.

---

## Important Notes

- Only **newly added lines** (lines starting with `+` in the git diff) are synced by `sync_sdp_worklog.py` — editing existing entries does not re-sync.
- `sync_sdp_fields.py` is **additive** for links/approval/tasks (it won't delete things) except `## Tasks` which is bidirectional (status toggles).
- Tags are markdown-driven by the `Tags:` header line plus the `flow:*` tag.
- SDP portal: `<YOUR_SDP>.sdpondemand.manageengine.com`. Direct case URL: `https://<YOUR_SDP>.sdpondemand.manageengine.com/app/itdesk/ui/requests/{long_id}/details`
- Web links go in the `## 📰 Clerk Card` Links section → rendered as clickable `<a href>` in SDP Description field via CI/CD
- Tags cannot be set via API (permission limitation) — tracked in markdown only; SDP status transitions are the visible equivalent

---

## Composes

```
sdp-worklog
├── sdp_create_stub.py     (Step 2 — scaffold missing folder)
├── sdp_context_bundle.py  (Step 2.5 — fetch SDP_ID if missing)
└── sdp_set_flow.py        (Step 5 — flow + status transition)
```

**Called by:** operator directly; `sdp-investigator` (Phase 6 close); `rounds` (Station 6); `sdp-dispatcher` ("this one's done" handoff).
