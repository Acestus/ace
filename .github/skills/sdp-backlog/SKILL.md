---
name: sdp-backlog
description: 'Create new ServiceDesk Plus requests with scoring labels and case-file scaffolding. Use when the user says "new sdp request", "add to sdp backlog", "create an sdp ticket", or wants to file end-user support work. Handles the full workflow: Jira-duplicate detection, SDP create, scoring header, local case file, optional Confluence backlog note.'
argument-hint: 'Describe the request (subject + requester + any approval requirements). Will create SDP request, scaffold cases/{ID}/, and add scoring.'
---

# SDP Backlog Skill

You add new ServiceDesk Plus work to the backlog. Mirror of `phoenix-backlog` for SDP — but with **Jira-duplicate detection up front** so we don't accidentally double-bill an existing <PROJECT>-XXX project.

---

## When to Use

- User says "new sdp request", "add to sdp backlog", "create an sdp ticket"
- User wants to file an end-user support request (access grant, password reset, workspace provisioning, etc.)
- User says "log this as sdp work" or "this came in via slack — make it real"

---

## Workflow

### Phase 1 — Capture Intent

Use `ask_user` to gather (one at a time):
1. **Subject** — one-line title
2. **Requester** — full name + email (the user this is FOR, not necessarily who's asking)
3. **Description** — what they actually need
4. **Group** — Infrastructure / Identity / Application Dev / etc.
5. **Urgency** — High / Normal / Low (maps to urgency:1-5 scoring)
6. **Approvers** — emails if known; otherwise "—"

### Phase 2 — Duplicate Detection (CRITICAL)

**Before creating anything**, check Jira:

```bash
python3 scripts/jira_search.py --jql "project = INFRA AND summary ~ \"{keyword from subject}\" AND created >= -30d"
```

Also check existing SDP cases:
```bash
python3 scripts/sdp_search.py --keyword "{keyword}"
ls cases/ | xargs -I {} grep -lH "{requester-email}" "cases/{}/" 2>/dev/null
```

If a match exists:
- **Jira match** — propose linking: create SDP as shadow with `OWNER: jira` header and `JIRA: <PROJECT>-XXX`. Do NOT queue for Lane 4-6.
- **SDP match** — propose appending to existing case rather than creating a duplicate.
- **No match** — proceed to Phase 3.

### Phase 3 — Score the Request

Default scoring for SDP backlog:
- **Urgency 1-2** (high) → Lane 4 (SDP-Urgent)
- **Agentic 4-5 + approvers** → Lane 5 (SDP-Approval)
- **Agentic 1-2 + low touch** → Lane 6 (SDP-Background)

Propose scoring to the operator. Adjust per their feedback.

### Phase 4 — Create in SDP

```bash
python3 scripts/sdp_create_request.py \
  --subject "{subject}" \
  --requester {requester-email} \
  --description "{description}" \
  --group "CloudOps" \
  --category "IT Support" \
  --subcategory "Access & Credentials" \
  --item "Account Creation & Deletion" \
  --technician <YOUR_EMAIL> \
  --priority "{priority}" \
  --approver "{approver-email}" \
  --tags "flow:queue"
```

**Field notes:**
- `--group` requires `--category`, `--subcategory`, `--item` — SDP will reject with HTTP 400 if any are missing. Safe defaults: `IT Support` / `Access & Credentials` / `Account Creation & Deletion`.
- `--approver` creates approval level 1 and adds the approver in a single call. Use comma-separated emails for multiple approvers. The API requires one POST per approver using `{"approval": {...}}` (not a bulk array).
- `--urgency` is not accepted by the SDP API — omit it. Priority and impact drive SLA instead.
- <APPROVER_NAME>'s email is `<APPROVER_EMAIL>` (not `@<ORG_DOMAIN>`).

Capture the returned display_id and long_id.

### Phase 5 — Scaffold Local Case File

```bash
python3 scripts/sdp_create_stub.py \
  --id {display_id} \
  --urgency {urgency} --importance {importance} --agentic {agentic} \
  --approvers "{approver-emails}" \
  --owner sdp
```

If linked to Jira:
```bash
python3 scripts/sdp_create_stub.py --id {display_id} --owner jira --jira <PROJECT>-XXX
```

Verify the case file has all the new template sections (`## Tasks`, `## Web Links`, `## Linked Requests`, `## Approval`).

### Phase 6 — Approval Setup (if needed)

For Lane 5 work where approvers are known up front, pass `--approver` directly to `sdp_create_request.py` (handled automatically). For tickets already created without an approver:

```bash
python3 scripts/sdp_approval.py --id {display_id} \
  --create-level 1 \
  --approvers <APPROVER_EMAIL>
```

**API notes:**
- The approver POST uses `{"approval": {"approver": {"email_id": "..."}}}` — singular wrapper, one request per approver.
- The bulk `{"approvals": [...]}` format is rejected by SDP with `EXTRA_KEY_FOUND_IN_JSON`.
- <APPROVER_NAME>: `<APPROVER_EMAIL>`
- <YOUR_NAME>: `<YOUR_EMAIL>`

Also fill the `## Approval` section of the case markdown:
```markdown
### L1
- <APPROVER_EMAIL> — pending
```

### Phase 7 — Optional Confluence Backlog Update

For visible work that needs stakeholder awareness, add a row to the SDP backlog page (if one exists; otherwise skip). Pattern mirrors `phoenix-backlog`'s Confluence update step.

### Phase 8 — Commit & Push

```bash
git add cases/{display_id}/
git commit -m "SDP-{display_id}: backlog scaffold ({lane})"
git push
```

CI workflow `sdp-worklog-sync.yaml` reconciles tags + approval setup on push.

### Phase 9 — Confirm

Report back:
- SDP display id + URL
- Lane assignment (4/5/6)
- Local case file path
- Cross-link if applicable (<PROJECT>-XXX)
- Whether approval was wired up

---

## Important Notes

- **Always run duplicate detection** — most SDP requests trace to an existing Jira project or prior SDP case. Linking is cheaper than retroactive cleanup.
- Default `OWNER: sdp` for standalone brake-fix; `OWNER: jira` only when explicitly linked to a project.
- Scoring labels go in the markdown header only — do NOT push them as SDP tags.
- For requests that came in via Slack/Teams: capture the original message URL in `## Web Links` so context isn't lost.

---

## Composes

```
sdp-backlog
├── jira_search.py         (Phase 2 — duplicate detection across Jira)
├── sdp_search.py          (Phase 2 — duplicate detection across SDP)
├── sdp_create_request.py  (Phase 4 — actual SDP create)
├── sdp_create_stub.py     (Phase 5 — local case scaffold)
└── sdp_approval.py        (Phase 6 — approval level wiring)
```

**Called by:** operator directly when a new SDP request needs to be filed.
