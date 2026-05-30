---
applyTo: 'issues/**/*.md,confluence/*Backlog*.md'
---

# Backlog Management — Lean Kanban Philosophy

## Purpose

Govern how Jira work items are created, named, scored, tagged, and managed using principles from lean manufacturing, the Eisenhower Matrix, and an Agentic Scale. The goal is to optimize flow, surface constraints, and maintain a healthy work-in-progress limit.

---

## Story Naming Convention

Every Jira story summary follows a three-part structure:

```
{Key Noun} - {Medium Noun} - {~6 Word Description}
```

| Segment | Purpose | Examples |
|---------|---------|----------|
| **Key Noun** | Primary technology or platform | `Fabric`, `AWS`, `Entra`, `GitHub`, `Five9`, `Azure`, `Tenable` |
| **Medium Noun** | Specific component or domain | `Pipeline Schedule`, `Security Groups`, `OIDC`, `Function App`, `IAM` |
| **Description** | ~6 word action summary (verb-first) | `Fix Schedule Loss During CI-CD Deployment` |

### Rules

- Use title case for all three segments
- Separate segments with ` - ` (space-dash-space)
- Description starts with a verb: Create, Fix, Grant, Deploy, Configure, Build, Migrate, Evaluate
- Keep description between 5–8 words (target 6)
- No abbreviations in the description unless universally understood (CI-CD, RBAC, UMI, OIDC)

### Examples

```
Fabric - Pipeline Schedule - Fix Schedule Loss During CI-CD Deployment
AWS - Security Hub - Triage Critical and High Findings
Entra - External ID - Migrate from Keycloak to Entra
GitHub Actions - OIDC - Fix Authentication to Container Registry
Five9 - Function App - Build Call Script Engine for Telephony
Azure - RBAC - Grant Reader Role on AI Resource
```

---

## Scoring Dimensions

Each work item carries three inline scores. Urgency and Importance use **1 = highest/most, 5 = lowest/least**. Agentic uses **1 = most autonomous, 5 = most manual**.

### Agentic Scale — AI Delegation Readiness

How much can AI agents handle this task autonomously:

| Score | Label | Description |
|-------|-------|-------------|
| 1 | Delegate & Check | Hand off to agent entirely — just review the result later |
| 2 | Mostly Background | Kick off, monitor, intervene only if something breaks |
| 3 | Mixed | Roughly equal human work and waiting/automated phases |
| 4 | Mostly Manual | Heavy human effort with short automated steps |
| 5 | Manual | Hands-on the entire time — design, coding, troubleshooting |

### Urgency Scale — Eisenhower: When

| Score | Label | Description |
|-------|-------|-------------|
| 1 | Critical | Deadline now or imminent; blocking others today |
| 2 | High | Due this week or actively causing pain |
| 3 | Moderate | Due this sprint; no immediate consequences if delayed days |
| 4 | Low | No hard deadline; should get done eventually |
| 5 | None | Backlog — no time pressure whatsoever |

### Importance Scale — Eisenhower: Why

| Score | Label | Description |
|-------|-------|-------------|
| 1 | Critical | Production impact, security risk, or directly enables revenue |
| 2 | High | Enables multiple teams, unblocks key initiatives |
| 3 | Moderate | Meaningful improvement to operations or developer experience |
| 4 | Low | Nice-to-have; incremental improvement |
| 5 | Minimal | Housekeeping or administrative only |

### Inline Format

In Confluence and issue markdown, scores appear on the priority line:

```
Priority: P10 · Agentic: 4 · Urgency: 2 · Importance: 1 · !status[In Progress](blue)
```

---

## Jira Labels — Kanban Flow Tagging

Every Jira story receives labels from three dimensions. These labels power the gemba board view and constraint analysis.

### Flow Lane (`flow:*`)

Tracks where work sits in the value stream:

| Label | Meaning | Pull Rule |
|-------|---------|-----------|
| `flow:queue` | Waiting to be started | Pull only when WIP is below limit |
| `flow:active` | Currently being worked | Counts toward WIP limit |
| `flow:waiting` | Blocked on external input | Does NOT count toward WIP limit |
| `flow:done` | Completed | Remove from active board |

### Lean Way (`way:*`)

Which of the Three Ways the work primarily serves:

| Label | Way | Examples |
|-------|-----|----------|
| `way:flow` | 1st — Optimize delivery left-to-right | Pipeline identity, workspace provisioning, CI-CD fixes |
| `way:feedback` | 2nd — Fast feedback loops | Monitoring, alerting, auditing, security scanning |
| `way:learning` | 3rd — Continuous learning & experimentation | POCs, evaluations, new tooling |

Items may carry multiple `way:*` labels when they serve more than one Way.

### Constraint (`constraint:*`)

Surfaces bottlenecks per Theory of Constraints:

| Label | Meaning | Action |
|-------|---------|--------|
| `constraint:technician` | Only one person (wweeks) can do this | Document, automate, or train others to relieve |
| `constraint:vendor` | Waiting on Microsoft, AWS, or other vendor | Escalate or find alternative path |
| `constraint:dependency` | Blocked by another team or system | Coordinate, escalate, or decouple |

---

## Work-in-Progress (WIP) Limit

**Active WIP limit: 3 items (one per swimlane).**

### The Three Swimlanes

| Lane | Emoji | Criteria | Slot |
|------|-------|----------|------|
| 🔴 **Urgent** | Do First | Urgency 1–2 | 1 active ticket |
| 🔵 **Manual** | Hands-on Focus | Agentic 4–5 AND Importance 1–3 | 1 active ticket |
| 🟢 **Background** | Delegate to Agents | Agentic 1–2 | 1 active ticket |

### Rules

1. Only items labeled `flow:active` count toward WIP
2. Items labeled `flow:waiting` do NOT count (they are blocked externally)
3. Each lane has exactly one active slot — never two from the same lane
4. When a ticket completes, pull the next ticket from *that same lane's queue*
5. When WIP exceeds limit: **stop the line** — finish or park before pulling
6. Quick wins (takes < 30 minutes) may be executed without consuming a WIP slot if done same-day

### Pull Priority (What to Pull Next)

When a lane slot opens, pull the item from that lane's queue with the best combined score:

1. **Urgency + Importance** — lowest sum wins (U1+I1=2 is highest priority)
2. Break ties with Jira key number — lower number wins (older = waited longer)
3. Never pull a `constraint:technician` item when you already have 2+ technician items active

---

## Constraint Management — Relieving the Bottleneck

Lean kanban teaches: **elevate the constraint, don't feed it more work.**

### When technician Constraint Exceeds 50%

If more than half of backlog items are `constraint:technician`:

1. **Document** — Write runbooks (<PROJECT>-342 pattern) so others can execute
2. **Automate** — Script repetitive access grants, provisioning, and config changes
3. **Delegate** — Train team members or create self-service tooling
4. **Batch** — Group similar technician tasks (e.g., all access grants) into a single focused session

### Vendor Constraints

- Set a follow-up date when submitting to vendor
- After 5 business days with no response, escalate
- Move to `flow:waiting` immediately — do not hold a WIP slot

### Dependency Constraints

- Identify the specific blocker and document in the issue Follow-up section
- Offer to pair or provide what the other team needs to unblock
- If blocked > 1 sprint, find an alternative path or descope

---

## Gemba Board (Confluence View)

The backlog Confluence page includes a gemba board section that visualizes:

1. **WIP status** — current active count vs limit, with 🔴/🟢 indicator
2. **Flow lanes** — table showing Active, Waiting, and Queue counts with item keys
3. **Constraint analysis** — breakdown of technician/vendor/dependency counts
4. **Three Ways distribution** — how work maps to flow, feedback, learning
5. **Stop-the-line actions** — concrete next steps to restore flow

### Updating the Gemba Board

When updating the backlog Confluence article:

- Recalculate WIP count from items currently labeled `flow:active`
- Update constraint percentages
- Refresh the "Kanban Actions" section with current recommendations
- Flag any items that have been `flow:active` for more than 2 weeks without progress

---

## File & Folder Convention

Issue folders and files follow the naming convention from `jira-issue-documentation.instructions.md`:

```
issues/{JIRA-KEY} - {Key Noun} - {Medium Noun} - {Description}/
└── {JIRA-KEY} - {Key Noun} - {Medium Noun} - {Description}.md
```

Example:
```
issues/<PROJECT>-366 - Fabric - Pipeline Schedule - Fix Schedule Loss During CI-CD Deployment/
└── <PROJECT>-366 - Fabric - Pipeline Schedule - Fix Schedule Loss During CI-CD Deployment.md
```

---

## Creating New Work Items

When creating a new Jira story:

1. **Name** it using the three-part convention: `{Key Noun} - {Medium Noun} - {~6 Word Description}`
2. **Score** it: assign Agentic, Urgency, and Importance values (1–5 each)
3. **Label** it: add `flow:queue`, at least one `way:*`, and any applicable `constraint:*`
4. **Create local folder**: `issues/{KEY} - {summary}/` with the standard markdown template
5. **Update backlog**: add the item to the appropriate priority section in the Confluence article
6. **Check WIP**: if the item needs immediate work and WIP is at limit, identify what to park first

### Template for New Issue Markdown

```markdown
# {JIRA-KEY} - {Key Noun} - {Medium Noun} - {Description}

## Description

------------------------------------------------

{Context, background, acceptance criteria}

Scores: Agentic: {1-5} · Urgency: {1-5} · Importance: {1-5}
Labels: flow:queue, way:{flow|feedback|learning}, constraint:{technician|vendor|dependency}

## Actions

------------------------------------------------

### {YYYY-MM-DD} — Created

- COMMENT: Issue created. {Brief context.}

## Follow-up

------------------------------------------------

Status: Open
TODO:
- [ ] {First action item}
```

---

## Workflow Integration

### Automated Sync

- `.github/workflows/jira-worklog-sync.yml` syncs WORKLOG/COMMENT entries to Jira on push to main
- Labels are managed via Jira API (manual or scripted updates)
- Confluence backlog article is published via `scripts/publish-markdown-to-confluence.py`

### Weekly Review Cadence

1. Review WIP — are we at or below limit?
2. Review constraints — has technician percentage improved?
3. Move completed items to `flow:done`
4. Pull highest-priority items from queue if WIP allows
5. Update gemba board section in Confluence and publish

---

## Philosophy Summary

> *"Any improvements made anywhere besides the bottleneck are an illusion."* — Eliyahu Goldratt, Theory of Constraints

| Principle | Implementation |
|-----------|---------------|
| **Flow** (1st Way) | WIP limits, pull-based queue, flow lane labels, kanban board |
| **Feedback** (2nd Way) | Stop-the-line gates, score recalibration, carried-forward detection |
| **Learning** (3rd Way) | Pattern memory, kaizen retrospectives, reflection prompts, doc-it nudges |
| **Eisenhower Matrix** | Urgency/Importance scores separate "urgent" from "important" |
| **Theory of Constraints** | `constraint:*` labels identify and elevate bottlenecks |
| **Agentic Scale** | Agentic score guides what to delegate to AI agents vs do manually |

### Skill-Level Enforcement

| Principle | Primary Skill | Mechanism |
|-----------|--------------|-----------|
| WIP = 3 | `jira-dispatcher` | Refuses to pull if all slots full |
| Stop the Line | `rounds`, `pr-reviewer`, `fabric-deploy`, `jira-worklog` | Hard-stop conditions that block progress |
| Fast Feedback | `start-my-day`, `end-my-day`, `weekly-summary` | Forecasts, carried-forward flags, cycle time metrics |
| Continuous Learning | `knowledge-clerk`, `rounds` (reflection), `weekly-summary` (kaizen) | Pattern memory promotion, retrospective triggers |
| Elevate Constraint | `rounds`, `end-my-day`, `sdp-investigator` | Document-it nudges for `constraint:technician` work |
| Automate Repetition | `sdp-investigator` (repeat detection), `backlog` | Auto-create `way:flow` items for repetitive manual work |
| Visualize Work | `jira-dispatcher` (kanban board), `start-my-day` (forecast) | Org file boards, lane emojis, velocity snapshots |
