---
name: jira-worklog
description: 'Log time and comments to Jira issues via markdown files. Use when the user says "log time", "update Jira", "document my time", "worklog", or wants to record work done on a Jira issue. Finds or creates the issue file under issues/, adds WORKLOG/COMMENT entries, updates flow labels if the ticket status changed, commits, and pushes to main for automatic Jira sync.'
argument-hint: 'Specify the Jira issue key (e.g., <PROJECT>-87), time spent (e.g., 2h, 30m), a description of the work done, and optionally the new flow state (active/done/waiting/queue)'
---

# Jira Worklog Skill

You help the user log time and comments to Jira issues by editing markdown files in the `issues/` directory of this repository. When these files are committed and pushed to `main`, a GitHub Actions workflow runs `scripts/sync_jira_worklog.py` to sync new `WORKLOG` and `COMMENT` lines to Jira automatically.

This skill is also **label-aware**: after logging work you check whether the ticket's flow state should change and update Jira labels by running `scripts/jira_set_flow.py`.

## When to Use

- User wants to log time on a Jira issue
- User says "document my time", "update Jira", "log work", or "worklog"
- User wants to add a comment to a Jira issue via the repo
- User says "done", "blocked", "waiting on vendor", or "parking this" — signals a flow state change

---

## Voice & Tone

Write all worklog entries and comments in <YOUR_NAME>'s voice — direct, first-person, past tense. The goal is to sound like notes he typed himself.

**Style rules:**

- **First-person, investigative flow** — narrate what happened as you found it: "I reviewed the ticket. It looks like... I found the connection in ADF..."
- **Direct past tense in WORKLOG lines** — no preamble, just what was done: "Tested the guard approach against ws-27993 — confirmed it resets the field without touching the description. Fixed missing import, all 15 tests passing, pushed to main."
- **Chain steps with em-dashes or periods** — "Found the key in SharePoint - Experian_ereports_ssh_keys. ADF connector is pointing to prod-kv-azsql03-001. I do not have read access to that vault."
- **Name things explicitly** — use actual resource names, vault names, file paths, workspace IDs
- **Honest about blockers** — "I do not have read access to that vault." No softening.
- **Short sentences for emphasis** — "I got a bad FQR. I set up a meeting with Microsoft Support."
- **Decision Points** — when two options exist, label them clearly with bold headers and trade-offs in plain terms
- **No corporate filler** — never write "I hope this helps" or "Please let me know" or "In order to" — just state what happened

**WORKLOG line format (packed, specific):**
```
- WORKLOG 2h: Reviewed Experian SFTP connector in ADF — found key reference points to prod-kv-azsql03-001. Pulled SSH keys from SharePoint, validated PPK format in WinSCP. Confirmed I don't have read access to the key vault. Need <USER_C> to confirm key was rotated.
```

**COMMENT line format (conversational, direct, RICH — 4–10 sentences):**

`COMMENT` is the **default capture mechanism for Jira**. Every worklog gets a substantive COMMENT — not an afterthought summary. The Jira ticket's comment thread should read like a running narrative of the investigation: what was checked, what was found, what was ruled out, where the evidence lives. If a teammate scrolled only the Jira comments they should still understand the full arc of the work.

Pack the comment with the same density as the worklog notes — there is no separate "internal vs Jira" voice in `## Actions`. Both `WORKLOG` and `COMMENT` lines are <YOUR_NAME>'s internal investigative voice. The difference is scope: `WORKLOG` is the line-item time entry; `COMMENT` is the *paragraph* explaining what happened during that time.

A good `COMMENT` covers most of these — pick what's true for the step:

1. **What I did** — the concrete action, named resources, specific commands run
2. **What I found** — the evidence: output, configuration values, error messages, who owns what
3. **What I tried that didn't work** — dead ends, hypotheses ruled out, why
4. **What it means** — the interpretation, the decision, the root cause if known
5. **Links discovered** — Confluence pages, MS Learn docs, PRs, related INFRA tickets (URLs go in `## Web Links` too, but mention them here so the comment thread is self-contained)
6. **What's next** — the literal next action and who owns it

**Example — rich COMMENT (the default):**
```
- COMMENT: Pulled the Experian SFTP connector definition from ADF (experian_sftp_ecsa9798, linked service ls_experian_prod). The private key reference points at prod-kv-azsql03-001/secrets/experian-sftp-key. Confirmed <USER_C> rotated the secret on 2026-05-13 — version e3a91... is current. I do not have Key Vault Reader on prod-kv-azsql03-001 so I could not pull the secret to validate the PPK format locally. Tested two alternate keys from SharePoint > IT > Experian_ereports_ssh_keys — neither matched the public key Experian has on file (verified via their SFTP welcome banner). <USER_C> to grant temporary Key Vault Secrets User so I can verify the bound secret matches the rotated key, or paste the public key here for me to diff. Docs: https://learn.microsoft.com/en-us/azure/data-factory/connector-sftp#linked-service-properties.
```

**Example — short COMMENT (only when the worklog is genuinely trivial, like a 5-minute tag-up):**
```
- COMMENT: Quick sync with <USER_C> — he confirmed the key was rotated 2026-05-13 and the new secret is in prod-kv-azsql03-001. Continuing investigation; will request Key Vault Secrets User next.
```

If you only have a one-line WORKLOG with no findings to report, the work probably wasn't worth a separate log entry. Combine it into the next substantive update.

**NUDGE line format (stakeholder-facing, Teams-style — short, direct, tags the person):**

`NUDGE` is the **stakeholder-facing companion** to COMMENT. While COMMENT captures internal technician notes for the record, NUDGE is the message a teammate would actually receive — short, plain language, asking for a specific next action, and tagging them via `@firstname.lastname` so they get a Jira notification.

Use a NUDGE whenever the next action belongs to someone else. The Jira ticket becomes a self-service inbox: the stakeholder opens the ticket, reads the latest NUDGE, knows exactly what to do.

**Pairing rule:** when transitioning a ticket to `flow:waiting` or `flow:done + handoff`, write **both**:
1. A rich `COMMENT` capturing the technician narrative (what I tried, what I found, what's outstanding)
2. A `NUDGE` tagging the person whose decision/action unblocks the next step

Write these **while the ticket is still active**, before the transition — not at end of day. The context is freshest now.

A good NUDGE is:
- **One paragraph, single line** (sync requires it)
- **Addressed directly** to the tagged person
- **Specific about what you need** — a decision, an approval, a piece of info, a test
- **Light on internal jargon** — the reader may not be deep in the work
- **Closes with a question or two-option ask** ("can you confirm X, or do we wait for Y?")

**Example — NUDGE on flow:waiting:**
```
- NUDGE: Hey @michael.seaman — I narrowed <PROJECT>-77 to a single-seat pilot for Graham (Teams summaries + Jira lookup, ~$30/mo, vendor risk already approved via the Teams Meetings Agent assessment). Can you confirm a pre-governance pilot is OK to move on now, or do we wait for the full AI governance program to land?
```

**Example — NUDGE on flow:done with handoff:**
```
- NUDGE: Hey @graham.cohen — your Copilot seat is provisioned and the Atlassian Graph Connector is enabled. To verify: open Copilot in Teams, ask "what's <PROJECT>-77 about?" — you should get a sourced answer with a link back to this ticket. Reply here if it works, or @-mention me if you hit anything weird.
```

**Example — NUDGE with multiple recipients:**
```
- NUDGE: @michael.seaman @jagan.subramanian — decision call needed on OIDC vs SAML for the Keycloak migration. ADR is published (linked above). Can one of you propose a 30-min slot this week so we can lock the direction?
```

**Meeting note format** (when logging after a meeting):
```markdown
### 2026-05-14 15:00 — Meeting: Topic Name

**Decisions:**
- Decision one
- Decision two

**Action items:**
- Do this
- Do that
```

---

## The Flow Labels

Every ticket has exactly one `flow:` label. When logging work, always confirm the current flow state is correct:

| Label | Meaning | When to Apply |
|-------|---------|---------------|
| `flow:queue` | Waiting to be pulled into active work | Newly created; parked items |
| `flow:active` | One of the 3 current WIP items (one per lane) | Pulled by dispatcher |
| `flow:waiting` | Blocked — on vendor, approval, or dependency | Actively blocked; does NOT count against WIP limit |
| `flow:done` | Completed — closed out | Work finished |

**WIP Rule:** Only 3 tickets can be `flow:active` at a time — one per lane (🔴 Urgent, 🔵 Manual, 🟢 Background). Never set `flow:active` manually if the lane already has an active ticket. Run `dispatch` instead.

### Lane Classification

A ticket's lane is determined by its scoring labels:

```
urgency:1 or urgency:2               → 🔴 Urgent
agentic:4 or agentic:5 + importance ≤ 3  → 🔵 Manual
agentic:1 or agentic:2               → 🟢 Background
(anything else)                      → 🔵 Manual (default)
```

---

## Workflow

### Step 1 — Gather Information

**First: check for a running timer.** Before asking for time, look up `planner/.timers.json`:

```bash
cat /home/wweeks/git/projects/planner/.timers.json 2>/dev/null || echo "{}"
```

- If a timer is running for this ticket, show the elapsed time:
  ```
  /home/wweeks/git/projects/scripts/tl.py stop {KEY}
  ```
  The `tl stop` output gives the duration in both human (`1h 23m`) and Jira (`1h23m`) format. Use that as the time — no need to ask.

- If no timer is running, ask the user for time manually.

Ask the user for any other missing details (use the ask_user tool, one question at a time):

1. **Jira issue key** — e.g., `<PROJECT>-87`. If unclear, list recent issues from `issues/` and let them pick.
2. **Time spent** — only ask if no timer was running. e.g., `2h`, `30m`, `1h30m`.
3. **Description** — what was done. Keep it concise but specific.

If the user provides all three in their message, skip asking.

### Step 2 — Look Up Current Labels

Fetch the ticket's current labels, status, and notes:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/jira_fetch_ticket.py --key {KEY}
```

Show the user the current flow state and lane. If urgency/importance/agentic scores are missing, note that and proceed.

### Step 3 — Check for Flow State Change

Based on what the user described, determine if the flow label should change:

#### Pre-Transition Gate (active → waiting, done, or queue)

**Before executing any flow transition**, run this checklist against the issue file. If any item is
missing, fill it in now — before changing the label. Context goes stale the moment you leave the
ticket.

```
📋 Pre-transition checklist — {KEY}

  [ ] ## Notes → ### Lede populated (one-paragraph "what is this and why does it matter")
  [ ] ## Notes → ### Status populated (current flow state + blocker/owner in one sentence)
  [ ] ## Notes → ### Next populated (the literal next action and who owns it)
  [ ] ## Actions → at least one WORKLOG entry for today's work
  [ ] ## Actions → at least one COMMENT entry narrating the investigation (not just the WORKLOG line)
  [ ] ## Web Links → at least one entry (Jira link, Confluence page, MS Learn doc, Azure portal link)
  [ ] ## Follow-up → TODO list reflects current state
```

**Lede generation rule — NEVER leave a placeholder.** If the Lede is empty, missing, or contains any
of these patterns, **synthesize a real Lede immediately** from the ticket summary, description, Notes
field from Jira, and any investigation context from this session:

- `_(no description yet)_`
- `What: _(no description yet)_`
- `_(add a 2-3 sentence...`
- `_(none)_`
- any `_(...placeholder...)_` pattern

Use the newspaper lede pattern: what the system/work does + why it matters + what's at risk without
it. Pull from the ticket title, Jira description, and findings. 2-4 sentences. Never transition with
a placeholder Lede.

**Auto-fill rule:** If any section is missing, write it before asking the user to confirm the
transition. Do not ask "should I add this?" — just add it. The user can edit afterward.

**Minimum Web Links for every ticket:**
- The Jira ticket itself: `[<PROJECT>-XXX Jira](https://<YOUR_ATLASSIAN>.atlassian.net/browse/<PROJECT>-XXX)`
- Any Confluence pages referenced in the investigation
- Any Azure Portal resource links (use `#resource/subscriptions/...` deep links)
- Any MS Learn docs cited

**If transitioning to `flow:waiting`:** also write a NUDGE line tagging the person being waited on.
If transitioning to `flow:done`:** write a COMMENT summarizing what was accomplished and confirming
closure.

Only after all checklist items are green should you call `jira_set_flow.py`.

#### Structured Close-Out (when transitioning to done)

When the user signals "done", present exactly 4 close-out options before processing:

```
How should we close {KEY}?

1. ✅ Done + Verify — Work complete, verified working. Standard close.
2. 📝 Done + Needs Docs — Work complete, but a Confluence page should capture the pattern.
3. 🤝 Done + Handoff — Work complete on our side, but someone else owns the next piece (not blocked — just FYI).
4. 🚫 Cancel / Won't Fix — Not doing this. Close with reason.

Which one? (default: 1)
```

**What each option triggers:**

| Option | Flow | Extra Actions |
|--------|------|---------------|
| Done + Verify | `flow:done` | Standard close. Log worklog, transition, dispatch next. |
| Done + Needs Docs | `flow:done` | Close the ticket, then file a `way:doc` backlog item via `backlog` skill linking to the closed ticket. Nudge: "I'll create a doc ticket — what's the topic title?" |
| Done + Handoff | `flow:done` | Close the ticket, add COMMENT tagging the recipient. Draft a Teams message (same as flow:waiting pattern). |
| Cancel / Won't Fix | `flow:done` | Ask for cancellation reason. Add COMMENT with reason. Use Jira transition ID `31` (Done) with resolution. |

**When to skip the menu:**
- If the user already said exactly what kind of done it is (e.g., "it's done, verified"), apply option 1 without asking
- If the user said "cancel this" or "won't fix", apply option 4 without asking
- Only show the menu when the signal is ambiguous ("it's done" with no qualifier)

#### Flow State Transition Table

| User says... | Flow change | Jira status transition |
|---|---|---|
| "done", "finished", "completed", "closed it" | `flow:active` → `flow:done` | → **Done** (transition ID `31`) |
| "blocked", "waiting on vendor", "waiting for approval" | `flow:active` → `flow:waiting` | → **Code Review** (transition ID `61`) |
| "waiting for [person] to confirm/test/review", "next step is for [person] to verify", "sent to [person] for review", "needs user acceptance", "pending UAT", "needs sign-off" | `flow:active` → `flow:waiting` | → **Code Review** (transition ID `61`) |
| "unblocked", "vendor replied", "back on this", "[person] confirmed it works" | `flow:waiting` → `flow:active` | → **In Progress** (transition ID `41`) |
| "parking this", "deferring", "putting back" | `flow:active` → `flow:queue` | → **To Do** (transition ID `101`) |
| (no status signal — just logging time) | No change | No change |

**Important distinction — "waiting for confirmation" vs "done":**
- Use `flow:waiting` when our work is complete but a human must still validate, confirm, or sign off before the ticket can close. The ticket is NOT done — it's blocked on external verification.
- Use `flow:done` only when the ticket is fully closed — confirmation received, SDP ticket closed, no further action needed.
- When in doubt: if the next action belongs to someone else, it's `flow:waiting`.

If a change is needed, apply both the label update and the status transition in one call:

```bash
python3 scripts/jira_set_flow.py --key {KEY} --flow done --transition
# choices: queue | active | waiting | done
```

Always run both commands together — label and transition. The WIP limit (3 In Progress max) is enforced by the dispatcher; the worklog skill only transitions the ticket that is already active.

**If marking done:** also suggest the user run `dispatch` to pull the next ticket into that lane's active slot.

**If marking waiting:** the WIP slot for that lane is now open. Suggest running `dispatch` to pull the next queued ticket.

### Step 4 — Find or Create the Issue File

Look for an existing folder under `issues/` matching the Jira key:

```
issues/<PROJECT>-87/<PROJECT>-87 - Some Summary.md
```

- The folder name starts with the Jira key
- There should be exactly one `.md` file inside

If no folder exists, ask the user for the issue summary and create:

```
issues/{JIRA-KEY}/{JIRA-KEY} - {Summary}.md
```

Use the standard template from the jira-issue-documentation instruction file.

#### SDP Auto-Link Detection

When creating a new issue file (or when the Description section is empty and you're loading for the first time), check if there's a matching SDP ticket:

```bash
# Search SDP by keywords from the Jira summary
python3 scripts/sdp_fetch_ticket.py --search "{first 3-4 meaningful words from summary}"
```

If a match is found:
- Show it to the user: "Found SDP #34102 that looks related — '{SDP subject}'. Link it?"
- If yes, add `SDP #34102` to the issue file Description section
- This auto-triggers Step 6.5 (SDP worklog sync) on future worklogs

If no match: proceed silently. Don't ask about SDP unless there's a likely candidate.

### Step 5 — Add the Worklog Entry

Insert a new action entry **above the `## Follow-up` section** and **below any existing action entries**. Newest entries go on top of the Actions section.

Format:

```markdown
### {YYYY-MM-DD HH:mm}

- WORKLOG {time}: {description}
- COMMENT: {rich technician narrative for the Jira thread — see Voice & Tone}
- NUDGE: {Teams-style ask of @firstname.lastname — only when the next action belongs to someone else}
```

**Rules:**
- Date format: `YYYY-MM-DD HH:mm` using the current date/time
- `WORKLOG` lines sync as Jira time entries — always include time and description
- `COMMENT` lines sync as Jira comments — **always add a substantive COMMENT** (see Voice & Tone for the rich-comment template). The Jira comment thread is the running narrative; a reader scrolling only the comments should understand the full arc of the work.
- `NUDGE` lines sync as Jira comments with `@mention` notifications. **Add a NUDGE whenever the next action belongs to someone else** — on every transition to `flow:waiting`, on `flow:done` with handoff, and at any active-phase checkpoint where you need a decision or input. Use `@firstname.lastname`.
- **Default is rich** — 4–10 sentences covering what was done, what was found, what was ruled out, links discovered, and what's next. Short one-line COMMENTs are reserved for genuinely trivial check-ins (a 5-minute sync, a status nudge).
- **Author COMMENT + NUDGE while the ticket is active** — not at end of day, not after dispatch. The technician narrative is freshest in your head before you context-switch.
- Each `WORKLOG`/`COMMENT`/`NUDGE` must be a single line (no line breaks)
- **CRITICAL FORMAT**: Lines MUST start with `- WORKLOG`, `- COMMENT`, or `- NUDGE` (dash-space prefix). The sync regex requires this exact format. NEVER use `<!-- WORKLOG: -->` HTML comments, bare `WORKLOG:` without the dash prefix, or any other variation.

If the flow state changed, note it in the worklog description (e.g., `Completed initial fix. Marking done.`).

### Step 6 — Commit and Push Jira Worklog

```bash
git add issues/{JIRA-KEY}/
git commit -m "{JIRA-KEY}: {short description} {YYYY-MM-DD}"
git push
```

Always commit directly to `main` — the Jira sync workflow triggers on push to `main` when `issues/**` changes.

Include the co-authored-by trailer:
```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

### Step 6.25 — Update the Planner Time Log

If a `tl` timer was running and you stopped it in Step 1, the Time Log row in today's org file is already updated — skip this step.

If no timer was running, open `planner/$(date +%m-%d).org` and update the `* Time Log` table manually:

- If the ticket already has an `active` row (End is blank): fill in the End time and update Duration and Worklog
- If no row exists: append a new row with Start = approximate start time, End = now, Duration ≈ time logged

```org
| 08:21 | 08:33 | <PROJECT>-395 | Azure AI - Resource Access - Grant Read Access | ~15m  | 0.25h |
```

**Never remove or overwrite existing completed rows.** Only append or fill in blanks.

### Step 6.5 — Update the SDP Ticket (if linked)

Check whether the Jira issue has a linked SDP ticket number. Look for `SDP #XXXXX` in the issue description.

If found:
1. Find or create `cases/{SDP_ID}/{SDP_ID} - {Summary}.md`
2. Add a `WORKLOG` and `COMMENT` entry matching the Jira worklog — same voice, same facts, written for the end-user (not internal):

```markdown
### {YYYY-MM-DD HH:mm}

- WORKLOG {time}: {description — same as Jira worklog}
- COMMENT: {user-facing note — what was done, what they need to do next, plain language}
```

**COMMENT tone for SDP:** Write directly to the requester. Tell them what was done, what they should do to verify, and what to reply with to close the ticket. No jargon, no internal references.

3. Commit and push `cases/{SDP_ID}/` to main — the SDP sync workflow will post the comment automatically:

```bash
git add cases/{SDP_ID}/
git commit -m "fix({SDP_ID}): {short description}"
git push
```

**If no SDP ticket is linked:** skip this step.

### Step 6.6 — Draft a Teams Message

If the flow state changed to `flow:waiting` (i.e., the next action belongs to someone else), draft a ready-to-send Teams message for the operator to copy and paste.

**Format — short, direct, action-oriented:**

```
Hey {FirstName} — I've {what was done}. {One sentence on what they can now do}.

To verify:
1. {Step 1}
2. {Step 2}
3. {Step 3 if needed}

Let me know if it works and I'll close the ticket. 🙏
```

**Rules:**
- Address by first name only
- No corporate filler ("I hope this finds you well", "Please don't hesitate")
- Tell them exactly what to do to verify — specific steps, not vague instructions
- One ask at the end: confirm it works so the ticket can close
- Keep it under 10 lines total

Present the message in a clearly labeled block so the operator can copy it immediately.

**If flow state is NOT `flow:waiting`** (just logging time or marking done): skip the Teams message — there's nothing the other person needs to do.

### Step 7 — Confirm

Tell the user:
- What was logged (issue key, time, description)
- The current flow state (and what it was changed to, if applicable)
- Which lane the ticket belongs to
- That it was pushed to main and the Jira sync workflow will pick it up
- Whether SDP was updated (and which ticket)
- If the flow state opened a WIP slot: remind them to run `dispatch` to pull the next ticket

---

## Example — Simple Time Log (No State Change)

User: "log 2 hours on <PROJECT>-87 for fixing the IPAM deployment error and rewriting the README"

1. Fetch labels → `flow:active`, `agentic:5`, `urgency:2`, `importance:2` → 🔴 Urgent lane
2. No state change signal — flow stays `flow:active`
3. Write the entry in <YOUR_NAME>'s voice:
   ```markdown
   ### 2026-05-21 09:00

   - WORKLOG 2h: Tracked down the IPAM deployment error — missing subnet delegation on the spoke vnet. Fixed the Bicep template and reran the stack deployment. Rewrote the README to document the delegation requirement and link the AVM module version.
   - COMMENT: The IPAM stack was failing on `Microsoft.Network/virtualNetworks/subnets` with a delegation-required error. Traced it to the spoke vnet definition in `stacks-bicep/skpipam/main.bicep` — the IPAM subnet was missing the `Microsoft.Network.IPAM` delegation that the AVM virtual-network module expects when `enableIpam = true`. Added the delegation block, redeployed via `./scripts/deploy-bicep.ps1 -Env dev -Stack skpipam -Action deploy` — green. While I had the file open I rewrote the README to call out the delegation requirement and pin the AVM `avm/res/network/virtual-network` version we tested against (`0.5.2`) so the next person doesn't hit this. Docs: https://learn.microsoft.com/en-us/azure/virtual-network/subnet-delegation-overview. No follow-up; the stack is idempotent on re-deploy.
   ```
4. Commit and push
5. Confirm: "Logged 2h on <PROJECT>-87 (🔴 Urgent, flow:active). Pushed to main."

---

## Example — Marking a Ticket Done

User: "log 1h on <PROJECT>-360 — added the Graph permission, it's done"

1. Fetch labels → `flow:active`, `agentic:5`, `urgency:3`, `importance:2` → 🔵 Manual lane
2. User said "it's done" → change `flow:active` → `flow:done` via Jira API
3. Write the entry in <YOUR_NAME>'s voice:
   ```markdown
   ### 2026-05-21 14:30

   - WORKLOG 1h: Added Sites.Selected Graph API permission to the Five9 UMI. Tested the call script — confirmed it can now read the SharePoint site. Marking done.
   - COMMENT: Granted Sites.Selected on the Five9 user-assigned managed identity (umi-skpfive9-prd-usw2-dat) via Microsoft Graph PowerShell — `New-MgServicePrincipalAppRoleAssignment` against the Graph SP, app role id `883ea226-...`. Then issued site-scoped read with `Grant-PnPAzureADAppSitePermission` against the `Recordings` SharePoint site (read-only role). Re-ran the Five9 call recordings ingestion script against the dev container — it pulled 14 recordings cleanly where before it was failing on `403 accessDenied`. No production cutover needed; the UMI is the same one prod uses, so the permission is live now. Marking done. Docs I leaned on: https://learn.microsoft.com/en-us/graph/permissions-selected-overview.
   ```
4. Commit and push
5. Confirm: "Logged 1h on <PROJECT>-360. Flow updated: active → done. 🔵 Manual lane slot is now open — run `dispatch` to pull the next ticket."

---

## Example — Work Done, Waiting for User Confirmation

User: "log 15m on <PROJECT>-395 — granted Reader and Monitoring Reader to jmarquard, waiting for him to confirm the traces query works"

1. Fetch labels → `flow:active`, `agentic:4`, `urgency:2`, `importance:2` → 🔵 Manual lane
2. "Waiting for him to confirm" → next action belongs to Joshua → change `flow:active` → `flow:waiting` via Jira API
3. Add worklog to `issues/<PROJECT>-395/...md`:
   ```markdown
   ### 2026-05-21 08:33

   - WORKLOG 15m: Granted jmarquard@<ORG_DOMAIN> Reader + Monitoring Reader on ai-skpana-dev-usw2-001. Waiting for Joshua to confirm traces query works before closing SDP #33920.
   - COMMENT: Access granted. Assigned Reader and Monitoring Reader to jmarquard@<ORG_DOMAIN>. Please confirm traces queries work in Application Insights and reply here so we can close the SDP ticket.
   ```
4. Commit and push `issues/<PROJECT>-395/`
5. Issue description mentions `SDP #33920` → find/update `cases/33920/33920 - ai-skpana-dev-usw2-001 Read Access.md`:
   ```markdown
   ### 2026-05-21 08:33

   - WORKLOG 15m: Granted jmarquard@<ORG_DOMAIN> Reader and Monitoring Reader on ai-skpana-dev-usw2-001 (Application Insights, rg-skpana-dev). Pending Joshua's confirmation.
   - COMMENT: Access has been granted. I assigned Reader and Monitoring Reader to jmarquard@<ORG_DOMAIN> on the ai-skpana-dev-usw2-001 Application Insights resource. You should now be able to browse the resource in the portal and run KQL queries including `traces`. Please confirm it works and reply here so we can close this ticket.
   ```
6. Commit and push `cases/33920/`
7. Draft Teams message (flow is now `flow:waiting` → someone else must act):
   ```
   Hey Josh — I've granted you access to the ai-skpana-dev-usw2-001 Application Insights resource. You should be able to run `traces` queries in the portal now.

   To verify:
   1. Go to portal.azure.com
   2. Search for ai-skpana-dev-usw2-001
   3. Open Logs and run a `traces` query

   Let me know if it works and I'll close the ticket. 🙏
   ```
8. Confirm: "Logged 15m on <PROJECT>-395. Flow updated: active → waiting. SDP #33920 updated. 🔵 Manual lane slot is open — run `dispatch` to pull the next ticket."

---


User: "log 30m on <PROJECT>-395 — reached out to the AI team, waiting on their response"

1. Fetch labels → `flow:active`, `agentic:3`, `urgency:1`, `importance:1` → 🔴 Urgent lane
2. "Waiting on their response" → change `flow:active` → `flow:waiting` via Jira API
3. Write the entry in <YOUR_NAME>'s voice:
   ```markdown
   ### 2026-05-21 10:15

   - WORKLOG 30m: Reviewed the access request — the principal is the AI team's managed identity, ai-skpana-dev-usw2-001. Reached out to the AI team to confirm the resource they need access to. Waiting on their response before I can set the RBAC assignment.
   - COMMENT: Pulled the request details — the requester wants Reader/Monitoring Reader on `ai-skpana-dev-usw2-001` (Application Insights, rg-skpana-dev) for the AI team's managed identity, but the request didn't specify whether that's the workspace-scoped MI or the per-function MI. Looked up both in Entra (`umi-skpana-dev-usw2-ai` and `umi-skpana-dev-usw2-fn`) — different object IDs, different scopes. Messaged the AI team channel asking which MI to bind and confirming Monitoring Reader is the right floor (Reader alone doesn't grant Log Analytics traces access). Waiting on their reply before I assign anything — don't want to grant the wrong principal and have to roll it back. flow:active → flow:waiting.
   ```
4. Commit and push
5. Confirm: "Logged 30m on <PROJECT>-395. Flow updated: active → waiting (doesn't count against WIP). 🔴 Urgent lane slot is open — run `dispatch` to pull next urgent ticket."

---

## Step 6.75 — Update Jira Ticket Fields (via markdown)

The issue file in `issues/<KEY>/<KEY>...md` is the **source of truth** for the ticket's Notes card, Checklist, Web Links, and Linked Issues. You edit those sections in the markdown — `scripts/sync_jira_fields.py` reconciles them to Jira on every push to main.

The **Notes section is the ticket's newspaper-lede card** — a self-contained snapshot any teammate can read in 20 seconds at standup and know:
1. **What it is + why it matters** (the `### Lede`)
2. **Where it stands right now** (`### Status`)
3. **What happens next** (`### Next`)
4. **Where to click** to see the wider ecosystem (`## Web Links` + `## Linked Issues`)

No dead-end stubs. If a worklog mentions a Confluence page, MS Learn URL, vendor doc, or related INFRA ticket, it **must** appear in `## Web Links` (clickable docs) or `## Linked Issues` (Jira dependencies).

### What to edit, where

Open the issue file and update these four sections in place:

```markdown
## Notes

### Lede
Tenable's CIEM Enterprise module surfaces overprivileged identities across AWS, Azure, and GCP — closing the SASE control-plane gap the standard CNAPP license leaves open. Without it, identity-risk findings stay advisory instead of enforceable.

### Status
flow:waiting — <APPROVER_NAME> to approve Enterprise upgrade budget

### Next
Send escalation message today after standup

## Checklist

- [x] Investigate ticket scope and blocker
- [x] Draft escalation message
- [ ] Send escalation message after standup
- [ ] Confirm Enterprise budget approval

### Deployment phase
- [ ] Schedule CNAPP Enterprise module deployment
- [ ] Document deployment runbook in Confluence

## Web Links

- [Parent epic — <PROJECT>-188 SASE](https://<YOUR_ATLASSIAN>.atlassian.net/browse/<PROJECT>-188)
- [Tenable CIEM overview](https://docs.tenable.com/cloud-security/Content/Topics/CIEM/CIEMOverview.htm)
- [Confluence — CNAPP Runbook](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/12345)
- [Azure entitlement management](https://learn.microsoft.com/en-us/entra/id-governance/entitlement-management-overview)

## Linked Issues

- is blocked by: <PROJECT>-263
- blocks: <PROJECT>-244
- relates to: <PROJECT>-188
```

Save, commit, push. CI runs `scripts/sync_jira_fields.py --changed-since <before>` and reconciles every changed issue file to Jira.

### Test locally before pushing

```bash
# Parse and report — no Jira writes
python3 scripts/sync_jira_fields.py --key <PROJECT>-257 --dry-run

# Push this one file's state to Jira now
python3 scripts/sync_jira_fields.py --key <PROJECT>-257
```

### Sections → Jira fields

| Markdown section | Jira target | Reconciliation semantics |
|------------------|-------------|--------------------------|
| `## Notes` → `### Lede` / `### Status` / `### Next` | `customfield_10246` (Notes) | State-based. Markdown wins; hand-edits in Jira get overwritten on next push. |
| `### Next` (also) | `customfield_10280` (Next Steps board view) | Mirrored from `### Next` line. |
| `## Checklist` (` - [x] ` / ` - [ ] ` items, `### Phase` subheaders → HeroCoders section headers) | `customfield_10032` (HeroCoders Issue Checklist) | State-based. Empty section clears the field. |
| `## Web Links` (` - [Label](url) ` lines) | Remote Links (`/issue/{key}/remotelink`) | State-based. Links removed from markdown are deleted from Jira. Links written by other tools (no `url-<sha1>` globalId) are left untouched. |
| `## Linked Issues` (` - verb: KEY ` lines) | `issuelinks` | Missing links are created; **never deleted** (too risky — manual cleanup only). |

Recognised link verbs in `## Linked Issues`:

```
- blocks: <PROJECT>-275
- is blocked by: <PROJECT>-263
- relates to: <PROJECT>-188
- duplicates: <PROJECT>-100
- clones: <PROJECT>-50
```

### Composition rules — the Notes card

**Lede (`### Lede`).** Write it like the first paragraph of a newspaper article. Two-sentence pattern:

> *"\<System X\> does \<thing Y\> for \<consumer Z\> — \<the wedge it fills in our environment\>. Without it, \<concrete failure mode\>, so \<business impact\>."*

Avoid Jira-speak ("This ticket tracks…"). Write what the *system* does and why we care.

**Status (`### Status`).** Always begins with `flow:<state>`, em-dash, then who/what we're waiting on.

- `flow:active — running OIDC plumbing on the GHA workflow side`
- `flow:waiting — <APPROVER_NAME> to approve budget`
- `flow:queue — needs scoping interview with vendor`

**Next (`### Next`).** Literal next action. One sentence.

### Composition rules — Web Links

Build the spider-web. Every URL surfaced by the worklog goes in `## Web Links`. Notes stays clean prose; URLs live exclusively here so they render as clickable hyperlinks with favicons in Jira's Web Links panel.

**Hard rules — anything cited in the worklog must appear in `## Web Links`:**

- **Every Confluence page** created or referenced
- **Every MS Learn / docs.microsoft.com / learn.microsoft.com URL** in WORKLOG/COMMENT
- **Every vendor doc** (Tenable, Five9, Microsoft Graph, etc.)
- **SDP cases** when relevant

**Do NOT** use Web Links for <PROJECT>-to-INFRA dependencies — those go in `## Linked Issues` so the relationship is queryable in board views.

### Composition rules — Checklist

The HeroCoders Checklist is the **authoritative working list** — what you tick off as you work, what shows progress at standup, what `rounds` reads to surface state in the kanban card.

- Use it for **actionable engineering steps on this ticket**. Not for permanent acceptance criteria, not for long-horizon roadmap items.
- Use `- [x] text` for done, `- [ ]` for open. Use `### Phase` for grouping (renders as HeroCoders section header).
- **Re-syncing overwrites the whole list** — when you edit, re-confirm the full plan. This is by design.
- Keep items concrete and verb-led: *"Send escalation message"* not *"escalation"*.

### Composition rules — Linked Issues

Use real Jira issue links for ticket-to-ticket relationships. They're queryable, show in blocker reports, and drive the `rounds` kanban card.

- **Every blocker discovered during investigation** → `- is blocked by: <PROJECT>-XXX`. Reciprocal is auto-created by Jira.
- **Use `relates to:` sparingly** — only for true "see also" tickets where neither blocks the other.
- Linked Issues are additive in CI — to *remove* a link, you must delete it manually in the Jira UI. (We never auto-delete issue links; too easy to destroy human intent.)

### Escape hatch: `jira_update_fields.py`

For one-off scripted updates (e.g. backfill, bulk operations from a notebook), `scripts/jira_update_fields.py` still works with its `--lead` / `--status` / `--next` / `--related` / `--checklist` / `--blocks` / `--blocked-by` flags. Use it for tooling; for normal worklog flow, edit the markdown.

### What stays in the markdown body (not in these four sections)

- Investigation transcripts, command output, blow-by-blow worklog history → `## Actions` (synced as WORKLOG/COMMENT lines via the diff-based worklog sync)
- Acceptance criteria → still set via `jira_update_fields.py --ac` (driving a separate Jira field)
- Due dates and SDP URLs → still `jira_update_fields.py --due` / `--sdp-url`

### Flow label updates

After every worklog, run `scripts/jira_set_flow.py` if the flow state changed:

```bash
python3 scripts/jira_set_flow.py --key <PROJECT>-366 --flow waiting
# choices: queue | active | waiting | done
```

This replaces all inline `curl` calls for label updates.

---

## Important Notes

- The `WORKLOG` and `COMMENT` prefixes are **required** — `scripts/sync_jira_worklog.py` pattern-matches on them
- **Every worklog gets a rich `COMMENT` by default** (4–10 sentences, see Voice & Tone). The Jira comment thread is the running narrative of the work — not an optional add-on. Only fall back to a short COMMENT when the worklog is genuinely trivial.
- Time format must be Jira-compatible: `15m`, `1h`, `2h30m`, `1d`, etc.
- Only **newly added lines** (lines starting with `+` in the git diff) are synced — editing existing entries won't re-sync
- Flow label updates run immediately via `scripts/jira_set_flow.py` — they don't wait for CI/CD
- Notes, Checklist, Web Links, and Linked Issues sync from the markdown file via CI on push to main (see Step 6.75). For an immediate one-shot push without waiting, run `python3 scripts/sync_jira_fields.py --key <PROJECT>-XXX` locally.
- AC, due dates, SDP URLs still go through `scripts/jira_update_fields.py` (escape hatch — these fields aren't in the markdown schema yet)
- Never set `flow:active` without running `dispatch` — it enforces the WIP limit and lane balancing
- **Never update the `description` field** — it is the original problem statement. All running context goes in the markdown's `## Notes` section.

---

## Stop the Line

**Hard stops — flag these before committing:**
- **WIP violation:** If logging a new `flow:active` ticket would exceed the 3-ticket WIP limit → "🛑 Stop the line: WIP limit 3. Close or park one before pulling new work."
- **Repeated blocker pattern:** If the same blocker text (same stakeholder + same issue) appears in 3+ consecutive worklogs → "🛑 Stop the line: same blocker 3x. Escalate or re-route — don't keep logging against a stuck ticket."
- **Zero-progress cycle:** If this ticket has 3+ worklogs in the last 7 days but no TODO items checked off in the Follow-up section → "🛑 Stop the line: effort without progress. Consider breakdown, spike, or park."

These are signals, not automatic blocks. Surface them prominently so the operator can make an informed decision.

---

## Composes

```
jira-worklog
├── jira-set-flow         (Step 3 — flow label + status transition)
├── markdown sync         (Step 6.75 — edit ## Notes / ## Checklist / ## Web Links / ## Linked Issues; CI reconciles on push)
├── jira-update-fields    (escape hatch — AC, due date, SDP URL, bulk scripted updates)
├── sdp-worklog           (Step 6.5 — if SDP ticket linked)
├── jira-dispatcher       (suggested after done/waiting — WIP slot opened)
└── backlog              (Step 3 close-out option 2 — "Done + Needs Docs")
```

**Called by:** `rounds` (Phase 4), or directly by user
