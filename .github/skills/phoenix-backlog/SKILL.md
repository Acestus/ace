---
name: phoenix-backlog
description: 'Create new Jira work items with kanban flow labels and add them to the Confluence backlog. Use when the user says "add a work item", "create a Jira story", "new backlog item", "add to backlog", or wants to create a new task with scoring and labels. Handles the full workflow: score assignment, Jira creation, label application, local issue file, and Confluence backlog update.'
argument-hint: 'Describe the work item — what technology, what needs to be done, and any context about urgency or complexity'
---

# Backlog Skill

You help the user create new work items that follow the WIP-limited kanban backlog methodology. Each new item gets properly named, scored, labeled, added to Jira, given a local issue file, and appended to the Confluence backlog page.

## When to Use

- User wants to create a new Jira story or work item
- User says "add a work item", "new backlog item", "add to backlog", "create a story"
- User describes work that needs tracking in the INFRA project

---

## Voice & Tone

Write all descriptions, issue file content, and backlog entries in <YOUR_NAME>'s voice — direct, specific, practical. Not corporate, not vague.

**Style rules:**

- **State the situation plainly** — "The ADF connector is using a key from prod-kv-azsql03-001. The key needs to be rotated." Not "This work item involves updating the key."
- **Name things explicitly** — actual resource names, workspace IDs, team names, service principals. Never write "the relevant service" or "the target system."
- **First action first** — start the description with what needs to happen, not with background history
- **One sentence per idea** — no compound paragraphs
- **Acceptance criteria as checkboxes** — concrete, verifiable outcomes only
- **No filler** — never write "In order to accomplish this goal" or "This task aims to" or "As part of our ongoing efforts"
- **Decision Points** — if there are two viable approaches, name them both clearly with trade-offs. Bold the option names.

**Description template feel:**
```
Requested By: {Name} on {Date}

{What needs to happen — one or two direct sentences. Name the actual thing.}

**{Specific entity or list}:**
- Item one
- Item two
```

**Issue file initial COMMENT:**
```
- COMMENT: Issue created. {One sentence of context — who asked, what it is, why it matters.}
```

---

### Urgency Scale (1 = most urgent, 5 = least)

| Score | Label | Meaning |
|-------|-------|---------|
| 1 | Critical | Blocking someone today |
| 2 | High | Due this week, causing pain |
| 3 | Moderate | Due this sprint |
| 4 | Low | No deadline |
| 5 | None | Pure backlog |

### Importance Scale (1 = most important, 5 = least)

| Score | Label | Meaning |
|-------|-------|---------|
| 1 | Critical | Production/security/revenue impact |
| 2 | High | Unblocks teams, enables key initiatives |
| 3 | Moderate | Meaningful operational improvement |
| 4 | Low | Nice-to-have |
| 5 | Minimal | Housekeeping only |

### Labels

| Category | Options | Description |
|----------|---------|-------------|
| Flow | `flow:queue` | Always starts in queue |
| Way | `way:flow`, `way:feedback`, `way:learning` | Which lean principle it serves |
| Constraint | `constraint:technician`, `constraint:vendor`, `constraint:dependency` | What bottleneck applies (if any) |

## Workflow

### Step 1 — Gather Information

Ask the user (one question at a time, using ask_user tool) for any missing details:

1. **What needs to be done** — the task description and context
2. **Technology/platform** — the Key Noun (e.g., Fabric, AWS, Entra, GitHub)
3. **Component** — the Medium Noun (e.g., Pipeline Schedule, Security Groups)
4. **Epic** — which epic it belongs to (show relevant options if unsure)

If the user provides enough context in their message, skip asking and propose the values.

### Step 2 — Determine Scores

Based on the user's description, propose scores for both Eisenhower dimensions:

- **Urgency**: Is someone blocked today? (1) Or is this strategic/backlog? (4-5)
- **Importance**: Does this affect production/security/revenue? (1) Or is it housekeeping? (5)

**Auto-score heuristics** — use these keyword patterns to propose scores immediately without asking. Only ask for confirmation if the score is ambiguous or the user's context is sparse.

| Signal Keywords | Urgency | Importance | Quadrant |
|---|---|---|---|
| outage, down, broken, production, blocked, urgent, emergency, security breach | 1 | 1 | Q1 — Do First |
| access request, grant, onboarding, permissions, unlock, unblock, SDP ticket | 2 | 2 | Q1 — Do First |
| cleanup, housekeeping, nice-to-have, tech debt, refactor, rename, documentation | 4-5 | 4-5 | Q4 — Someday |
| investigate, spike, evaluate, POC, research, explore | 3 | 3 | Q2/Q3 |
| automate, pipeline, deploy, CI/CD, monitor, alert | 2-3 | 2 | Q1/Q2 |
| vendor, waiting, external, Microsoft support | 3 | 2-3 | Q2 — Schedule |

**Fast-path rule:** If the description clearly matches a single row above, propose the scores without asking. Say: "Auto-scored — urgency:{N} importance:{N} (Q{X}). Confirm or adjust?"

Present the proposed scores to the user and ask for confirmation or adjustment.

### Step 3 — Determine Labels

Assign labels based on the work type:

- **Flow**: Always `flow:queue` for new items (never start as active unless WIP < 5)
- **Way**: 
  - `way:flow` — improves delivery speed, eliminates handoffs
  - `way:feedback` — monitoring, alerting, detection, validation
  - `way:learning` — POC, spike, evaluation, experimentation
- **Constraint**:
  - `constraint:technician` — only one person has the knowledge to do this
  - `constraint:vendor` — waiting on external vendor (Microsoft, AWS, etc.)
  - `constraint:dependency` — blocked by another team or prerequisite

### Step 4 — Build the Summary

Format: `{Key Noun} - {Medium Noun} - {~6 Word Description}`

Rules:
- Title case all segments
- Separate with ` - ` (space-dash-space)
- Description starts with a verb: Create, Fix, Grant, Deploy, Configure, Build, Migrate, Evaluate, Spike
- Target 6 words in description (5–8 acceptable)

### Step 5 — Create the Jira Issue

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

KEY=$(python3 scripts/jira_create_issue.py \
  --project INFRA \
  --type Story \
  --summary "{Key Noun} - {Medium Noun} - {Description}" \
  --description "{Full description of the work to be done.}" \
  --epic {EPIC-KEY} \
  --label flow:queue \
  --label "way:{way}" \
  --label "constraint:{constraint}" \
  --label "urgency:{N}" \
  --label "importance:{N}")
echo "Created: $KEY"
```

### Step 6 — Fetch Jira Description

After the ticket is created, pull its description back from Jira so it appears verbatim in the issue file:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Fetch the description field from the newly created ticket
JIRA_DESC=$(curl -s -u "${CONFLUENCE_EMAIL}:${WWEEKS_CONFLUENCE_API_TOKEN}" \
  "https://<YOUR_ATLASSIAN>.atlassian.net/rest/api/3/issue/${KEY}?fields=description" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
desc = data.get('fields', {}).get('description')
if not desc:
    print('')
elif isinstance(desc, str):
    print(desc)
else:
    # Atlassian Document Format — extract plain text
    def extract(node):
        if not node: return ''
        if node.get('type') == 'text': return node.get('text', '')
        return ''.join(extract(c) for c in node.get('content', []))
    print(extract(desc).strip())
")
echo "Description fetched: ${#JIRA_DESC} chars"
```

### Step 7 — Create Local Issue File

Create the folder and markdown file:

```
issues/{KEY} - {summary}/
└── {KEY} - {summary}.md
```

Use this template — the `## Description` block contains the Jira description verbatim, followed by scores and labels:

```markdown
# {KEY} - {Key Noun} - {Medium Noun} - {Description}
<!-- jira: {KEY} -->
<!-- last_synced: 1970-01-01T00:00:00Z -->

## Description

------------------------------------------------

- Jira: https://<YOUR_ATLASSIAN>.atlassian.net/browse/{KEY}
- Epic: {EPIC-KEY}
- Status: Open

{JIRA_DESC — the full description pulled from the ticket, pasted verbatim here}

Scores: Urgency: {N} · Importance: {N}
Labels: flow:queue, way:{way}, constraint:{constraint}

## Actions

------------------------------------------------

### {YYYY-MM-DD} — Created

- COMMENT: Issue created. {One sentence — who requested it, what it is, why it matters.}

## Follow-up

------------------------------------------------

Status: Open
TODO:
- [ ] {First concrete action item}
```

### Step 8 — Update the Confluence Backlog

Add the new item to the appropriate priority section in `confluence/<PAGE_ID>-Infrastructure-Backlog-Meeting-Prep.md`.

Priority group = (Urgency + Importance) × 5. Insert the item in the correct P-section.

Format:
```markdown
**{KEY} — {Summary}**
Priority: P{N} · Urgency: {N} · Importance: {N} · !status[Open](neutral)
Epic: {Epic Name} ({EPIC-KEY})
{One-line description}
```

### Step 9 — Publish and Commit

1. Publish the updated Confluence backlog:
   ```bash
   python3 scripts/publish-markdown-to-confluence.py <PAGE_ID> confluence/<PAGE_ID>-Infrastructure-Backlog-Meeting-Prep.md
   ```

2. Commit and push everything:
   ```bash
   git add -A && git commit -m "feat: add {KEY} - {summary}

   Urgency: {N}, Importance: {N}
   Epic: {EPIC-KEY}
   Labels: flow:queue, way:{way}, constraint:{constraint}

   Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" && git push
   ```

### Step 10 — Confirm

Tell the user:
- Jira key and link: `https://<YOUR_ATLASSIAN>.atlassian.net/browse/{KEY}`
- Scores assigned
- Labels applied
- Which epic it's in
- That it's visible on the Confluence backlog and their Jira board

Then assess whether the ticket warrants breaking into subtasks and offer it:

**Offer subtasks when any of these are true:**
- 3 or more distinct action items visible in the description or acceptance criteria
- Work has clearly separable phases (e.g., "first X, then Y, then validate Z")
- Total score (U+I) ≤ 4 and the summary implies multi-step delivery

**Don't offer subtasks when:**
- The ticket is a spike or investigation (`way:spike`, `way:investigate`)
- It's a single atomic action (rotate a key, grant a role, update a config)

**Offer format (only when warranted):**
```
This one looks like it has a few distinct phases. Want me to break it into subtasks?
I'm seeing:
  1. {Phase one — one line}
  2. {Phase two — one line}
  3. {Phase three — one line}

Say "yes subtasks" and I'll create them in Jira linked to {KEY}.
```

**Creating subtasks (when user confirms):**

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Create each subtask linked to the parent story
python3 scripts/jira_create_issue.py \
  --project INFRA \
  --type Subtask \
  --parent {KEY} \
  --summary "{Subtask summary}" \
  --description "{What this subtask covers}"
```

Add each subtask key to the `## Follow-up` TODO list in the issue file:
```markdown
TODO:
- [ ] {<PROJECT>-XXX} — {Subtask one summary}
- [ ] {<PROJECT>-XXX} — {Subtask two summary}
- [ ] {<PROJECT>-XXX} — {Subtask three summary}
```

## Priority Calculation

Priority group = `(Urgency + Importance) × 5`

| Urgency + Importance | Priority Group |
|---------------------|----------------|
| 2 (1+1) | P10 |
| 3 (1+2, 2+1) | P15 |
| 4 (2+2, 1+3, 3+1) | P20 |
| 5 (2+3, 3+2) | P25 |
| 6 (3+3, 2+4, 4+2) | P30 |
| 7 (3+4, 4+3) | P35 |
| 8 (4+4, 3+5, 5+3) | P40 |
| 9 (4+5, 5+4) | P45 |
| 10 (5+5) | P50 |

## WIP Guard Rail

Before creating a new item as `flow:active`:
- Check current WIP: query `labels = "flow:active" AND status != Done`
- If WIP ≥ 5 (one per lane), the new item MUST be `flow:queue`
- Only set `flow:active` if an open lane slot exists

## Finding Epics

Common epics for reference:

| Key | Name | Domain |
|-----|------|--------|
| <PROJECT>-340 | Fabric - Pipeline Identity, Stability and Execution | Fabric |
| <PROJECT>-71 | AI Readiness - Path to Governance & Copilot Premium | AI |
| <PROJECT>-158 | Agentic AI - Five9/Cresta | AI/Telephony |
| <PROJECT>-60 | Alert Source Discovery & Classification | Monitoring |
| <PROJECT>-145 | JIRA Integrations | Tooling |
| <PROJECT>-144 | Web 2.0 - Newsmith | Web Platform |
| <PROJECT>-178 | IAM / JML Automation | Identity |
| <PROJECT>-198 | Web 2.1 - Keycloak b2c - Azure b2c | Identity |
| <PROJECT>-188 | Secure Access Service Edge (SASE) | Security |

If the item doesn't fit an existing epic, ask the user whether to create one or leave it unlinked.

## Important Notes

- **Always start as `flow:queue`** — never bypass the WIP system
- The `.env` file at `~/git/projects/.env` contains `CONFLUENCE_EMAIL` and `WWEEKS_CONFLUENCE_API_TOKEN`
- Jira API base: `https://<YOUR_ATLASSIAN>.atlassian.net`
- Auth: Basic auth with `${CONFLUENCE_EMAIL}:${WWEEKS_CONFLUENCE_API_TOKEN}`
- The backlog page ID is `<PAGE_ID>`
- Board 307 ("wweeks Board") shows these items automatically via the board filter
