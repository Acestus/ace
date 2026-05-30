---
applyTo: 'issues/**/*.md'
---

# Jira Issue Note Workflow

## Purpose

Standard markdown format for Jira-backed work notes in the `issues/` directory. Each Jira issue gets a folder and markdown file that acts as the source of truth for descriptions, acceptance criteria, worklog notes, and follow-up items.

## File & Folder Naming

- Folder: `{JIRA-KEY} - {sanitized summary}`
- File: `{JIRA-KEY} - {sanitized summary}.md`
- Invalid filename characters (`<>:"/\|?*`) are stripped automatically

## Document Structure

Every issue file follows this layout in order. **The four bold sections drive Jira state** — markdown is the source of truth; CI reconciles to Jira on push to main.

```markdown
# {JIRA-KEY} - {summary}
<!-- jira: {JIRA-KEY} -->

## Notes                                ← drives Jira "Notes" + "Next Steps"

### Lede
2-3 sentence newspaper lede: what this is, why it matters, what's at risk.

### Status
flow:active|waiting|done — current blocker or owner (one line)

### Next
Literal next action (one line)

## Description

------------------------------------------------

{Jira context, background, and acceptance criteria}

## Investigation                        ← optional, for tickets needing discovery

------------------------------------------------

### {date}

{interview, evidence, hypotheses}

## Actions

------------------------------------------------

### {date or datetime}

{worklog/comment details}

## Checklist                            ← drives HeroCoders Issue Checklist

- [x] Done item
- [ ] Open item

### Phase header                        ← optional H3 sub-sections allowed
- [ ] Item

## Web Links                            ← drives Jira Remote Links panel

- [Label](https://url)
- [Another doc](https://url)

## Linked Issues                        ← drives Jira issue links

- blocks: <PROJECT>-XXX
- is blocked by: <PROJECT>-YYY
- relates to: <PROJECT>-ZZZ

## Follow-up

------------------------------------------------

Status: {status}
TODO:
- [ ] Item
```

### Sections (in order)

1. **Title** (`# heading`) — Jira key and summary
2. **Notes** — newspaper-lede card. Drives `customfield_10246` (Notes) and `customfield_10280` (Next Steps board view)
3. **Description** — issue context, background, and acceptance criteria
4. **Investigation** (optional) — discovery phase findings
5. **Actions** — chronological worklog entries, newest entry on top
6. **Checklist** — drives the HeroCoders Issue Checklist (`customfield_10032`). Re-syncing overwrites the whole list. Sub-headings (`### Phase`) become HeroCoders section headers.
7. **Web Links** — drives Jira Remote Links (clickable "Web links" panel). Markdown owns the full set: links removed from the file are deleted from Jira on next sync.
8. **Linked Issues** — drives Jira issue links (Blocks / Relates / Duplicate / Cloners). Missing links are created; we never delete (too easy to destroy human intent — manual cleanup only).
9. **Follow-up** — **always the very last section**. No other sections may appear after it.

## Newspaper Lede Pattern

Write what the *system* does and why we care, NOT "this ticket tracks…".

> Tenable's CIEM Enterprise module surfaces overprivileged identities and effective permissions across Azure and AWS — closing the identity-risk gap the base Tenable Cloud license leaves unenforced. Without it, the 247 Azure findings already visible in the portal stay advisory rather than actionable, and cross-cloud identity risk goes unscored.

## Action Entries

- Each entry is an `### H3` heading with a date or datetime
- Format: `### YYYY-MM-DD HH:mm` or `### YYYY-MM-DD — Title`
- **Newest entries go on top** (reverse chronological order)
- Content can include tables, bullet lists, code blocks, bold assessments, or short notes
- **Commands run** should be logged as fenced `bash` blocks with a `→` result line:

````markdown
### 2026-05-22 11:29

```bash
az role assignment create --assignee-object-id abc123 --role Contributor --scope /subscriptions/.../rg-example
```
→ Role assigned successfully

- WORKLOG 30m: Granted Contributor to UMI on rg-example
````

Note: You need to be careful with the nested markdown fences — use 4 backticks for the outer fence.

## Follow-up Section

- Always the **last section** in the document
- Includes `Status:` (e.g., Investigating, Waiting, Resolved, In Progress)
- TODO items use `- [ ]` / `- [x]` checkboxes
- Completed items should include a brief summary: `- [x] Task — result`
- Outstanding items remain unchecked: `- [ ] Task`

## Integration

The repository syncs to Jira via `.github/workflows/jira-worklog-sync.yaml`, which runs on pushes to `main` when `issues/**` changes.

Two scripts run in sequence:

1. **`scripts/sync_jira_worklog.py`** — diff-based. Reads the git diff and posts NEW `- WORKLOG` / `- COMMENT` lines from `## Actions`.
2. **`scripts/sync_jira_fields.py`** — state-based. For every changed issue file, reconciles `## Notes`, `## Checklist`, `## Web Links`, `## Linked Issues` to Jira. **The markdown is the source of truth** — hand-edits in Jira will be overwritten on the next push.

Local commands (require env in `.env`):

```bash
# Pull current Jira state into a new/existing markdown file
python3 scripts/materialize_issue_files.py --key <PROJECT>-275

# Push a single file to Jira (dry-run first)
python3 scripts/sync_jira_fields.py --key <PROJECT>-275 --dry-run
python3 scripts/sync_jira_fields.py --key <PROJECT>-275

# Push every issue file at once (useful after bulk markdown edits)
python3 scripts/sync_jira_fields.py --all
```

### ⚠️ WORKLOG / COMMENT / NUDGE Format Requirements (CRITICAL)

The sync script uses a strict regex. These are the **only** formats that sync to Jira:

```
- WORKLOG 15m: description here
- WORKLOG 2h: description here
- COMMENT: description here
- NUDGE: Hey @firstname.lastname — short, direct ask of a specific next action.
```

**Three line types, three jobs:**

| Line | Goes to Jira as | Visibility | Voice | Purpose |
|---|---|---|---|---|
| `WORKLOG` | Worklog entry (time + body) | Internal (worklog visibility default) | Internal investigative | Time accounting + per-slice notes |
| `COMMENT` | Plain Jira comment, marked `sd.public.comment internal=true` | **Internal** — JSM hides from the reporter portal; non-JSM projects show per project permissions | Internal investigative (technician notes) | Running narrative — what I tried, what I found, what I ruled out, links |
| `NUDGE`   | Jira comment, marked `sd.public.comment internal=false`, with @mention notifications | **Public** — visible to the reporter in the JSM customer portal | Conversational, end-user-friendly | A ready-to-read Teams-style message to the person whose next action unblocks the ticket, OR a 6–10 sentence end-user-voice status update for a JSM reporter |

**Author both COMMENT and NUDGE while the ticket is active — never defer to end of day.** The investigation is freshest in your head right now; the stakeholder thread should already read like a coherent story by the time you transition the ticket. See the rounds and ticket-investigator skills for the active-phase write-as-you-go cadence.

**Visibility, in plain terms:**
- A JSM reporter will only ever see your `NUDGE` lines. They will never see WORKLOG or COMMENT.
- Internal collaborators (anyone with project access) see all three.
- On non-JSM projects (INFRA, etc.) the `sd.public.comment` property is silently ignored, so COMMENT and NUDGE both behave like normal comments — no behavior change there.

**Mentions (NUDGE only):** Use `@firstname.lastname` (e.g., `@michael.seaman`). The sync script resolves the handle via Jira's user search and injects an ADF mention node so the user gets notified. Unresolved handles fall back to plain text with a warning — sync does not fail. Multiple mentions per line are fine: `@michael.seaman @graham.cohen`.

**DO NOT USE these formats — they will NOT sync:**
```
<!-- WORKLOG: date | time | desc -->     ← HTML comment, invisible to sync
WORKLOG: desc                            ← missing "- " prefix and time
WORKLOG 15m: desc                        ← missing "- " prefix
- WORKLOG: desc                          ← missing time value
- NUDGE @michael.seaman: ...             ← @mention belongs INSIDE the text, after the colon
```

Rules:
- Must start with `- ` (dash space)
- Time value immediately after WORKLOG (e.g., `15m`, `2h`, `0.5h`, `45m`)
- Colon + space separates the prefix from the body
- Single line only — no line breaks within the entry
- NUDGE @mentions go inside the body text, not before the colon
