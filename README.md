# Ace — Personal Workflow Toolkit

A file-driven personal kanban for engineers who live in the terminal.

Tickets, time logs, and follow-ups are markdown files. A .NET CLI and GitHub Copilot skills wrap daily operations: dispatching work, logging time, investigating tickets, publishing to Notion, and closing out the day. SQLite is the local source of truth for lane state, worklogs, and operational history.

This is the personal (Acestus) fork of the workflow-toolkit. It uses Linear + Notion instead of Jira/Confluence and adds IaC for Azure Static Web Apps.

---

## What's Inside

| Layer | What it does |
|---|---|
| **CLI** (`src/Ace.Tools.Cli/`) | .NET command surface — Linear, rounds (SQLite), GitHub, legacy runner |
| **Skills** (`.github/skills/`) | Thin collar skills for Copilot CLI. ~25 lines each. Routes intent to CLI. |
| **Instructions** (`.github/instructions/`) | File-pattern-scoped rules for AI assistance |
| **IaC** (`.azure/`) | Azure Static Web App config and identity |

---

## The Core Mental Model

### SQLite as source of truth

Lane claims and worklogs persist in `~/.ace/rounds.db`.

```bash
dotnet run --project src/Ace.Tools.Cli -- rounds status
sqlite3 ~/.ace/rounds.db "SELECT * FROM worklogs ORDER BY ts DESC LIMIT 20;"
```

### File-driven issue state

| State lives in | Synced to |
|---|---|
| `issues/<KEY>/<KEY>.md` | Linear (via CLI) |
| `planner/MM-DD.org` | Local time log |
| `notion/<title>.md` | Notion (via notion-writer skill) |

### Flow labels

| Label | Meaning |
|---|---|
| `flow:queue` | In the backlog |
| `flow:active` | Currently working it |
| `flow:waiting` | Blocked externally |
| `flow:done` | Closed |

**WIP limit: 5** — one lane per tab, one ticket per lane.

---

## Getting Started

### 1. Clone and configure

```bash
git clone https://github.com/Acestus/workflow-toolkit.git ace
cd ace
cp .env.example .env
# Fill in LINEAR_API_KEY, NOTION_API_KEY, GITHUB_TOKEN, Azure creds
```

### 2. Build the CLI

```bash
dotnet build src/Ace.Tools.Cli
```

### 3. Verify

```bash
dotnet run --project src/Ace.Tools.Cli -- --help
dotnet run --project src/Ace.Tools.Cli -- rounds status
```

---

## CLI Reference

```bash
# Linear
dotnet run --project src/Ace.Tools.Cli -- linear get-issue --key ACE-42
dotnet run --project src/Ace.Tools.Cli -- linear search --state "In Progress"
dotnet run --project src/Ace.Tools.Cli -- linear set-flow --key ACE-42 --flow done
dotnet run --project src/Ace.Tools.Cli -- linear dispatch-next --activate

# Rounds (SQLite-backed lane management)
dotnet run --project src/Ace.Tools.Cli -- rounds start --lane 1
dotnet run --project src/Ace.Tools.Cli -- rounds start --lane 2 --key ACE-42
dotnet run --project src/Ace.Tools.Cli -- rounds transition --lane 1 --flow done
dotnet run --project src/Ace.Tools.Cli -- rounds status

# GitHub
dotnet run --project src/Ace.Tools.Cli -- github issues list
dotnet run --project src/Ace.Tools.Cli -- github review-pr --pr 42

# Full help
dotnet run --project src/Ace.Tools.Cli -- --help
dotnet run --project src/Ace.Tools.Cli -- rounds --help
dotnet run --project src/Ace.Tools.Cli -- linear --help
```

---

## Daily Workflow

```bash
"start my day"              # → start-my-day: board + planner note
"start rounds 1"            # → rounds: dispatch next ticket into lane 1
"log 30m on ACE-42"         # → linear-worklog: logs time + comment
"this one's done"           # → rounds transition --lane N --flow done
"end my day"                # → end-my-day: standup, commit worklogs
```

---

## Skill Reference

| Skill | When to use |
|---|---|
| `start-my-day` | Morning setup |
| `end-my-day` | EOD standup + commit |
| `rounds` | Lane rotation — one ticket per lane |
| `linear-dispatcher` | Pull next queue ticket |
| `linear-worklog` | Log time + comments |
| `linear-backlog` | Create issues with Eisenhower scoring |
| `ticket-investigator` | Structured ticket investigation |
| `weekly-summary` | Brag doc / sprint summary |
| `waiting-ticket-followup` | Follow up on stale flow:waiting |
| `outbox-refresh` | Per-stakeholder status cards |
| `knowledge-clerk` | Retrieve precedent before building |
| `notion-writer` | Create and publish Notion pages |
| `sharepoint-writer` | Publish HTML docs to SharePoint |
| `editorial-assistant` | Three-pass editorial review |
| `aws-investigator` | AWS IAM / CloudWatch |
| `azure-investigator` | Azure RBAC, identity, resources |
| `pim-runbook` | Azure PIM roles |
| `fabric-deploy` | Fabric pipeline deployments |
| `pr-reviewer` | GitHub PR review |
| `pr-daily-summary` | Daily PR digest |
| `lorcana` | Scrape Lorcana card lists |
| `swa-deploy` | Azure Static Web App deploys |

---

## License

MIT — do what you want, no warranty. See [LICENSE](LICENSE).
