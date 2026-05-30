---
name: knowledge-clerk
description: 'Knowledge retrieval for <ORG_NAME> infrastructure work. Finds the right process, architecture, precedent, or vendor doc before you build or decide anything. Use when you need to know how something was done before, what the right pattern is, or whether documentation exists. Referenced by the rounds skill before every ticket.'
argument-hint: 'Ask a question or name a topic — "how do we handle UMI permissions", "Five9 call script auth pattern", "Fabric lakehouse naming", "networking spoke config"'
---

# <ORG_NAME> Clerk Skill

The clerk is the institutional memory of the <ORG_NAME> infrastructure practice. Before the operator makes a decision or the line lead writes a ticket, the clerk checks whether we've done this before, what the right pattern is, and where the docs live.

The clerk does not build or deploy anything. It finds, reads, and summarizes.

---

## When to Use

- Rounds skill calls it before presenting a ticket chart — "what do we already know about this?"
- User asks "how did we do X before" or "is there a pattern for Y"
- Before writing a Notion page — check if one already exists
- Before a new ticket — check if a precedent or architecture exists
- Any time the right approach is unclear

---

## Script

All searches run through the thin caller:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Standard lookup — brief output, all sources
python3 scripts/<org_short>_clerk.py --topic "{topic}"

# Deep dive — all matches + sources-checked summary
python3 scripts/<org_short>_clerk.py --topic "{topic}" --depth full

# Limit to a specific tier
python3 scripts/<org_short>_clerk.py --topic "{topic}" --source notion
python3 scripts/<org_short>_clerk.py --topic "{topic}" --source repo
python3 scripts/<org_short>_clerk.py --topic "{topic}" --source issues
python3 scripts/<org_short>_clerk.py --topic "{topic}" --source docs
```

**Exit codes:**
- `0` — findings returned
- `2` — nothing found across all sources (new precedent signal)

The skill reads the script output directly and surfaces it. No post-processing needed.

---

## Lookup Hierarchy

Work through these sources **in order**. Stop when you find something relevant. If the first source is thin, check the next — don't skip ahead.

### 1. Notion Directory (this repo)

```bash
ls /home/wweeks/git/projects/notion/
grep -ril "{topic}" /home/wweeks/git/projects/notion/
```

Files are named `{pageId}-{title}.md`. Read the ones that match. These are the most current internal docs — written by <YOUR_NAME>, published to the team.

**Key pages to know:**
- `<PAGE_ID>` — Fabric Platform Onboarding Guide
- `<PAGE_ID>` — EDM Cloud Native Transformation (SQL Server → Fabric)
- `<PAGE_ID>` — Microsoft Fabric CAF Naming Convention
- `<PAGE_ID>` — Five9 Call Script Agent
- `<PAGE_ID>` — SKPCerts Acmebot Architecture
- `<PAGE_ID>` — Infrastructure Backlog (Kanban Board)

### 2. Issues & Cases Directory (this repo)

```bash
grep -ril "{topic}" /home/wweeks/git/projects/issues/
grep -ril "{topic}" /home/wweeks/git/projects/issues/
```

Issue files (`issues/INFRA-*/`) contain investigation notes, blockers, decisions, and workarounds from real tickets. Cases (`issues/*/`) are  tickets with resolution history. Both are gold for "how did we solve this last time."

**Search pattern:**
```bash
# Find by keyword across issues and cases
grep -ril "{keyword}" /home/wweeks/git/projects/issues/ /home/wweeks/git/projects/issues/ \
  | head -10

# Read the most relevant match
cat "/home/wweeks/git/projects/issues/{match}/"*.md | head -100
```

### 2b.  Ticket Context (live API)

When a case file has an `_ID:` field, or when the topic relates to an  ticket number, fetch the ticket description directly:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Fetch by display ID (short number)
python3 scripts/sdp_fetch_ticket.py --id {ticket_id}

# Fetch by long  ID (from case file _ID field)
python3 scripts/sdp_fetch_ticket.py --long-id {long_id}

# Search by keyword
python3 scripts/sdp_fetch_ticket.py --search "{keyword}"
```

This gives you the ticket subject, description, requester, and status — use it to understand what the case is actually about without requiring the operator to look it up.

### 2c. Linear History — Prior Art Search

Always check Linear for prior tickets related to the topic. This catches patterns, prior solutions, and related work:

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# Search Linear for related tickets by keyword
python3 scripts/linear_search.py --jql 'project = INFRA AND text ~ "{keyword}" ORDER BY updated DESC'

# Check specific ticket history
python3 scripts/linear_fetch_ticket.py --key {<PROJECT>-XXX}
```

Surface any `flow:done` tickets that solved a similar problem — those are prior art. Also surface `flow:waiting` tickets on the same topic to avoid duplicate work.

### 3. Reference Repositories (local)

These repos contain real <ORG_NAME> architectures and working code. Check them before writing anything from scratch.

| Repo | What's in it | Path |
|------|-------------|------|
| `skplogs` | Log architecture, Sentinel workspace patterns, KQL queries | `/home/wweeks/git/skplogs/` |
| `fabric-edm` | EDM Fabric platform — lakehouses, notebooks, pipelines, workspace config | `/home/wweeks/git/fabric-edm/` |
| `iac-infra` | Bicep + Terraform stacks for all infra — naming, RBAC, network, identity | `/home/wweeks/git/iac-infra/` |
| `five9_agent_call_scripts` | Five9 Function App — auth, call script CRUD, UMI patterns | `/home/wweeks/git/five9_agent_call_scripts/` |
| `networking` | Network topology, spoke configs, NSG rules, IPAM | `/home/wweeks/git/networking/` |

**Search pattern:**
```bash
# Search across all reference repos
grep -ril "{keyword}" \
  /home/wweeks/git/skplogs/ \
  /home/wweeks/git/fabric-edm/ \
  /home/wweeks/git/iac-infra/ \
  /home/wweeks/git/five9_agent_call_scripts/ \
  /home/wweeks/git/networking/ \
  --include="*.md" --include="*.bicep" --include="*.tf" --include="*.py" \
  | head -15
```

### 4. MCP Servers

When local repos don't have enough — query the live environment or Atlassian knowledge graph.

| MCP | Use for |
|-----|--------|
| **Atlassian Rovo** | Search Notion spaces not in the local notion/ dir; Linear history beyond the issues/ files |
| **Azure MCP** | Live resource inventory — what's actually deployed, current RBAC, Key Vault contents, resource group structure |
| **Fabric MCP** | Live workspace state — what lakehouses/notebooks/pipelines exist, current definitions |
| **GitHub MCP** | Cross-repo code search, PR history, Actions workflow patterns |

Use MCP when you need **live state** (what exists right now) rather than **documented patterns** (what we decided to do).

### 5. Microsoft Reference Documentation

When no internal source has the pattern — check official docs.

**Prioritized sources (in order):**

1. **Azure Architecture Center** — `https://learn.microsoft.com/en-us/azure/architecture/`
   - Reference architectures for landing zones, networking, identity, data platforms
   - CAF (Cloud Adoption Framework) patterns

2. **Microsoft Fabric documentation** — `https://learn.microsoft.com/en-us/fabric/`
   - Medallion architecture, lakehouse patterns, pipeline best practices

3. **Azure Well-Architected Framework** — `https://learn.microsoft.com/en-us/azure/well-architected/`
   - Security, reliability, cost optimization pillars

4. **Specific product docs** — look up by service name:
   - `https://learn.microsoft.com/en-us/azure/{service}/`

```bash
# Fetch a specific doc page
curl -s "https://learn.microsoft.com/en-us/azure/architecture/..." | python3 -c "
import sys
from html.parser import HTMLParser
class T(HTMLParser):
    def __init__(self): super().__init__(); self.text = []; self.skip = False
    def handle_starttag(self, t, a): self.skip = t in ('script','style','nav','header','footer')
    def handle_endtag(self, t): self.skip = False
    def handle_data(self, d):
        if not self.skip and d.strip(): self.text.append(d.strip())
p = T(); p.feed(sys.stdin.read()); print('\n'.join(p.text[:200]))
"
```

---

## Output Format

The clerk's output is a **briefing**, not a wall of text. Lead with what's most relevant. **Always cite the exact source** — file path, page ID, repo name, or URL. No unsourced claims.

### Found — standard briefing

```
📚 Clerk findings — {topic}
━━━━━━━━━━━━━━━━━━━━━━━━

**Best match:** {source} — {one line on what it says}
  Source: {exact path or URL}
  "{relevant quote or 2-3 sentence summary}"

**Also relevant:**
- {source 2} — {one line}
  Source: {exact path or URL}
- {source 3} — {one line}
  Source: {exact path or URL}

**Gaps:** {What wasn't found — be explicit}
**Recommendation:** {What to follow, reuse, or establish as the new pattern}
```

### Not found — explicit no-find signal

When nothing relevant is found after exhausting all sources, return this exact structure so the calling skill knows documentation is absent:

```
📚 Clerk findings — {topic}
━━━━━━━━━━━━━━━━━━━━━━━━

⚠  NO VETTED DOCUMENTATION FOUND

Sources checked:
  ✗ notion/         — no match
  ✗ issues/ + issues/    — no match
  ✗ skplogs/            — no match
  ✗ fabric-edm/         — no match
  ✗ iac-infra/          — no match
  ✗ five9_agent_call_scripts/ — no match
  ✗ networking/         — no match
  ✗ Atlassian Rovo MCP  — no match
  ✗ Azure MCP           — no match
  ✗ Microsoft Learn     — no match

Closest reference: {nearest partial match, even if weak — always cite it}
  Source: {path or URL}

This would be a new precedent. No existing <ORG_NAME> pattern to follow.
```

This signal tells the rounds skill (or any caller) that the information is unvetted — the operator is making a first-time decision, not following an established pattern. Rounds surfaces this as:

```
Prior art: ⚠ Clerk found no vetted documentation for this topic.
           Closest: {nearest partial match + source}
           This decision will set a new precedent.
```

### Partial match — some sources found, gaps remain

```
📚 Clerk findings — {topic}
━━━━━━━━━━━━━━━━━━━━━━━━

**Partial match only.**

Found:
- {source}: {what it covers}
  Source: {path or URL}

Not found:
  ✗ {specific aspect of the topic} — no documentation exists

Recommendation: Follow {source} for the parts it covers. The gaps are new ground.
```

---

## Integration with Rounds

When rounds presents a ticket, the clerk is called first (silently, before the chart is shown). It surfaces relevant findings as a "Prior art" line in the chart:

```
━━━━━━━━━━━━━━━━━━━━━━━━
🔴 <PROJECT>-363 — Five9 Call Script Engine
━━━━━━━━━━━━━━━━━━━━━━━━

Prior art (clerk): five9_agent_call_scripts repo has auth pattern (UMI + Sites.Selected).
                   <PROJECT>-360 closed May 22 — same UMI, permissions already granted.
                   Notion: <PAGE_ID> — Five9 Call Script Agent architecture doc.

Last action: ...
```

If there's nothing relevant, the line is omitted — no noise.

The clerk can also be invoked explicitly mid-round:
- `clerk {topic}` — full briefing on any topic
- `clerk prior art` — what's known about the current ticket specifically

---

## Quick Reference — Where to Look for What

| Topic | Start here |
|-------|-----------|
| UMI / managed identity patterns | `iac-infra/stacks-bicep/` + INFRA issues |
| Fabric lakehouse naming / structure | `fabric-edm/` + notion `<PAGE_ID>` |
| Five9 / call script auth | `five9_agent_call_scripts/` + notion `<PAGE_ID>` |
| Network topology / spoke config | `networking/` |
| Log / Sentinel / KQL | `skplogs/` |
| Bicep module patterns | `iac-infra/modules/` |
| Cert automation (Acmebot) | notion `<PAGE_ID>` |
| GitHub Actions / CD patterns | `iac-infra/` + `projects/.github/workflows/` |
| Past  cases | `issues/` directory |
| Past INFRA tickets | `issues/` directory |
| **System of record — "Linear or ?"** | **notion `<PAGE_ID>` ADR-001** |
| Solved patterns (clerk memory) | `notion/patterns/` + issue file reflections |

---

## Pattern Memory — The Feedback Loop

The clerk doesn't just find patterns — it **creates** them. When a ticket is completed, the clerk captures the problem→solution arc so future tickets benefit.

### How Patterns Are Captured

**Trigger:** When `rounds` marks a ticket `flow:done` AND the ticket had:
- A non-trivial investigation phase (investigation section exists in issue file), OR
- A `constraint:technician` label, OR
- The operator said "doc it" during close-out

**The clerk extracts:**

```markdown
## Pattern: {short title}

**Problem:** {one sentence — what was broken or missing}
**Signal:** {how you'd recognize this problem next time — keywords, error messages, symptoms}
**Solution:** {what actually fixed it — specific commands, config changes, architecture decisions}
**Source ticket:** {KEY} — {date closed}
**Applies to:** {domain tags — e.g., "fabric", "identity", "networking", "five9"}
```

### Where Patterns Live

Patterns are stored in `planner/patterns/{domain}.md` as a lightweight pattern catalog:

```bash
# Check existing patterns
ls /home/wweeks/git/projects/planner/patterns/
grep -ril "{keyword}" /home/wweeks/git/projects/planner/patterns/
```

### When to Surface Patterns

During the standard lookup hierarchy (Phase 2, Step 2: Issues & Cases), the clerk also checks `planner/patterns/` for signal-keyword matches. If a pattern's `Signal` field matches the current ticket's summary or description, surface it:

```
📚 Clerk findings — {topic}
━━━━━━━━━━━━━━━━━━━━━━━━

**Known pattern match:** {pattern title}
  Solved in: {source ticket KEY} ({date})
  Solution: {one-line summary}
  Source: notion/patterns/{domain}.md

  → This looks like the same problem. Follow the prior solution?
```

### Pattern Promotion Rules

1. **Single occurrence:** Captured in issue file reflection only (searchable by grep)
2. **Two occurrences:** Clerk notes "this has come up before" and cites the prior ticket
3. **Three+ occurrences:** Clerk recommends formalizing as a pattern entry in `planner/patterns/` and optionally a full Notion article

### Integration with Rounds Close-Out

In Phase 5 of rounds, after reflections are logged, the clerk checks if any completed ticket this round qualifies for pattern extraction:

```
📝 Pattern candidates from this round:
   • <PROJECT>-360: "UMI Graph permission grant" — generalizable? (say "pattern" to capture)
```

If the operator says "pattern", the clerk writes the pattern entry and commits it.


---

##  Awareness (Lanes 4–6)

ServiceDesk Plus work runs as a parallel set of three swimlanes (Lane 4 🔴 -Urgent, Lane 5 🟠 -Approval, Lane 6 🟢 -Background).  case files live under `issues/{display_id}/`. The header `OWNER: linear | sdp` decides which side holds the WIP slot:

- `OWNER: sdp` (default) — the  case is the WIP owner; counts against the  lane cap
- `OWNER: linear` — the  case is a **shadow** of a linked <PROJECT>-XXX issue; does NOT count against any  lane cap

When this skill needs to enumerate or render the operator's work, it MUST union both sources (`issues/` + `issues/`) and dedupe by cross-link (`JIRA:` header in cases, `:` header in issues). Shadows are surfaced as "(shadow of <PROJECT>-XXX)" annotations, not as independent slots.

For lane-routing and rounds claims, see `rounds` and `sdp-dispatcher`. The shared `/tmp/rounds-claims.json` uses keys `lane1`–`lane5` shared across Linear and  tickets (single ticket per lane, regardless of system).

Voice wall:  `COMMENT:` lines are **end-user voice** (plain language). Linear COMMENT lines are internal investigative voice. This skill must preserve that distinction wherever it emits or summarizes comments.

For -specific dispatch, render, or close-out, hand off to: `rounds`, `sdp-dispatcher`, `sdp-investigator`, `sdp-worklog`, `sdp-router`.
