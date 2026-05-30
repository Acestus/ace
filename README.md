# Workflow Toolkit

A file-driven personal kanban and ITSM workflow for engineers who live in the terminal.

Tickets, time logs, and follow-ups are markdown files. CI/CD syncs them to Jira and ServiceDesk Plus on push. Skills, Copilot CLI agents, and a stack of Python scripts wrap the day-to-day operations: dispatching work, logging time, investigating tickets, publishing Confluence docs, and closing out the day.

This is the de-identified, reusable version of a working personal toolkit. Fork it, replace the bracketed placeholders, and adapt it to your own stack.

---

## What's Inside

| Layer | Count | What it does |
|---|---|---|
| **Skills** (`.github/skills/`) | 24 | Triggered behaviors for the Copilot CLI agent (e.g. `start-my-day`, `rounds`, `jira-worklog`) |
| **Instructions** (`.github/instructions/`) | 17 | File-pattern-scoped rules for AI assistance (issue docs, Confluence pages, PySpark notebooks, etc.) |
| **Scripts** (`scripts/`) | 81 | Python CLI tools — Jira, SDP, Entra, Azure, Confluence, Fabric, PIM, timers |
| **Workflows** (`.github/workflows/`) | 12 | GitHub Actions for auto-sync, scheduled jobs, smoke tests |

---

## The Core Mental Model

### File-driven state

| State lives in | Synced to |
|---|---|
| `issues/<KEY>/<KEY>.md` | Jira (via `jira-worklog-sync.yaml`) |
| `cases/<ID>/<ID>.md` | ServiceDesk Plus (via `sdp-worklog-sync.yaml`) |
| `planner/MM-DD.org` | Local time log (org-mode tables) |
| `confluence/<PAGE_ID>-<title>.md` | Confluence (via publish script) |

You edit markdown, commit, push. CI reconciles to the system of record.

### Kanban Flow Model

Tickets carry exactly one `flow:` label and live in one of 6 lanes:

- **Jira lanes:** 🔴 Lane 1 Urgent · 🔵 Lane 2 Manual · 🟢 Lane 3 Background
- **SDP lanes:** 🔴 Lane 4 SDP-Urgent · 🟠 Lane 5 SDP-Approval · 🟢 Lane 6 SDP-Background

**WIP limit: 6** — one active ticket per lane. `flow:waiting` doesn't count.

| Flow label | Meaning |
|---|---|
| `flow:queue` | In the backlog for its lane |
| `flow:active` | Currently working it |
| `flow:waiting` | Blocked on someone/something external |
| `flow:done` | Closed |

### Skill triggers

Skills are markdown files (`.github/skills/<name>/SKILL.md`) with natural-language triggers. Say "start my day" and the agent runs the `start-my-day` skill. Say "this one's done" and `jira-dispatcher` advances the lane. Say "write a confluence page" and `confluence-writer` handles the full publish workflow.

---

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/<GITHUB_ORG>/workflow-toolkit.git
cd workflow-toolkit
cp .env.example .env
# Edit .env — fill in your Atlassian, SDP, GitHub, Azure credentials
```

### 2. Install dependencies

```bash
pip install -r scripts/requirements.txt   # if you add one
# Most scripts use stdlib + `az` CLI + `gh` CLI
```

### 3. Replace placeholders

Sweep the repo for `<PLACEHOLDER>` style tokens and replace with your real values:

```bash
grep -rh "<[A-Z_]*>" .github/ scripts/ | grep -oE "<[A-Z_]+>" | sort -u
```

Common ones:

| Placeholder | What to replace with |
|---|---|
| `<YOUR_NAME>` | Your real name |
| `<YOUR_EMAIL>` | Your work email |
| `<YOUR_ATLASSIAN>` | Your Atlassian Cloud subdomain |
| `<YOUR_SDP>` | Your ServiceDesk Plus subdomain |
| `<ORG_NAME>` / `<ORG_SHORT>` | Your company name + short code |
| `<ORG_DOMAIN>` | Your work email domain |
| `<PROJECT>` | Your Jira project key (e.g. `INFRA`, `OPS`) |
| `<SPACE>` | Your Confluence space key |
| `<GITHUB_ORG>` | Your GitHub org |
| `<AZURE_TENANT_ID>` / `<AZURE_SUBSCRIPTION_ID>` | Your Azure context |
| `<APPROVER_NAME>` / `<APPROVER_EMAIL>` | Default ticket approver |

### 4. Wire up GitHub secrets

For the workflows in `.github/workflows/` to work, set repo secrets:

- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`
- `WWEEKS_SDP` (SDP OAuth JSON blob)
- `AZURE_CREDENTIALS` (for OIDC or service principal)
- `TEAMS_WEBHOOK_URL` (optional)

### 5. Create the directory scaffolding

```bash
mkdir -p issues cases planner confluence assets
```

---

## Daily Workflow

```bash
# Morning
"start my day"                  # → start-my-day skill: pulls active tickets, creates planner note

# Picking up work
"rounds lane 1"                 # → rounds: routes to urgent lane, dispatches top queue ticket
"<PROJECT>-87"                  # → jira-router: opens or investigates a specific ticket

# Working
tl start <PROJECT>-87           # start a timer
# ... do work, edit code ...
"log 30 minutes on <PROJECT>-87, found root cause" # → jira-worklog skill

# Wrapping a ticket
"this one's done"               # → jira-dispatcher: marks done, pulls next from queue
"waiting on vendor"             # → marks flow:waiting

# End of day
"end my day"                    # → end-my-day: stops timers, generates standup, posts to Teams
```

---

## Skill Reference

### Jira workflow
- `start-my-day` — create today's planner note, load active tickets
- `end-my-day` — close out, generate standup, post to Teams
- `rounds` — kanban station rotation, one ticket per lane at a time
- `jira-router` — fuzzy intent router for ticket-adjacent requests
- `jira-dispatcher` — advance the next queue ticket into active
- `jira-worklog` — log time + comments via markdown
- `ticket-investigator` — structured investigation on a Jira ticket
- `phoenix-backlog` — create new work items with scoring labels
- `weekly-summary` — generate brag doc / sprint summary
- `waiting-ticket-followup` — draft follow-ups for stale `flow:waiting` tickets
- `outbox-refresh` — build per-stakeholder newspaper-lede cards

### ServiceDesk Plus workflow (mirror set)
- `sdp-router`, `sdp-dispatcher`, `sdp-rounds`, `sdp-worklog`, `sdp-investigator`, `sdp-backlog`

### Knowledge & writing
- `knowledge-clerk` — retrieve precedent, process, architecture before building
- `confluence-writer` — create and publish new Confluence pages
- `confluence-updater` — patch sections, append content to existing pages
- `editorial-assistant` — three-pass editorial review (developmental, line, copy)

### Infrastructure
- `aws-investigator` — IAM, CloudWatch, CloudTrail investigations
- `azure-investigator` — Azure RBAC, managed identity, resource investigations
- `pim-runbook` — Azure PIM eligibility and activation
- `fabric-deploy` — Microsoft Fabric pipeline deployments and schedule restore
- `pr-reviewer` — GitHub PR review with automated checklist
- `pr-daily-summary` — daily merged/opened PR digest

### Operators / orchestration
- `customize-cloud-agent` — Copilot cloud agent setup-step configuration

---

## Instructions Reference

File-pattern-scoped rules that govern AI generation against this repo:

- `jira-issue-documentation.instructions.md` — `issues/**/*.md` format
- `sdp-case-documentation.instructions.md` — `cases/**/*.md` format
- `confluence-live-docs.instructions.md` — `confluence/**/*.md` format
- `topic-article-creation.instructions.md` — end-to-end Confluence topic article workflow
- `backlog-management.instructions.md` — backlog hygiene + scoring
- `editorial-writing.instructions.md` — general prose standards
- `pyspark-notebooks.instructions.md` — Fabric notebook authoring
- `fabric-artifacts.instructions.md` — Fabric workspace artifact structure
- `plantuml-style.instructions.md` — diagram conventions
- `html-document-style.instructions.md` — HTML doc conventions
- `acceptance-criteria.instructions.md` — IaC change acceptance gates
- `ai-coding-guidelines.instructions.md` — AI code quality principles
- `pr-review.instructions.md` — PR review checklist
- `vsdd.instructions.md` — Verified Spec-Driven Development
- `error-messaging.instructions.md` — error message style
- `workflow-file-conventions.instructions.md` — `.yaml` vs `.yml`

---

## Scripts Cheat Sheet

```bash
# Load env
export $(grep -v '^#' .env | xargs)

# Jira
python3 scripts/jira_fetch_ticket.py --key <PROJECT>-87
python3 scripts/jira_search.py --jql 'labels = "flow:active"'
python3 scripts/jira_set_flow.py --key <PROJECT>-87 --flow done --transition
python3 scripts/jira_update_fields.py --key <PROJECT>-87 --notes "..."

# SDP
python3 scripts/sdp_fetch_ticket.py --id 33903
python3 scripts/sdp_set_flow.py --id 33903 --flow active --transition
python3 scripts/sdp_create_request.py --subject "..." --requester user@<ORG_DOMAIN> ...

# Azure / Entra
python3 scripts/entra_lookup.py --user user@<ORG_DOMAIN>
python3 scripts/az_pim.py --action check --role "Contributor"

# Confluence
python3 scripts/create-confluence-page.py confluence/stub.md --space-key <SPACE> --parent-id <PAGE_ID>
python3 scripts/publish-markdown-to-confluence.py confluence/<PAGE_ID>-title.md

# Timers
python3 scripts/tl.py start <PROJECT>-87
python3 scripts/tl.py stop <PROJECT>-87
```

---

## License

MIT — do what you want, no warranty. See [LICENSE](LICENSE).

## Credits

Built on the [Copilot CLI](https://github.blog/changelog/) skill model. PRs and forks welcome.
