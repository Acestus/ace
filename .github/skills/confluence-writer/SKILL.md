---
name: confluence-writer
description: 'Create and publish Confluence pages from markdown. Use when the user says "write a confluence page", "create a confluence article", "publish to confluence", "new topic article", or wants to author documentation for the Confluence wiki. Handles the full workflow: stub creation, page ID reservation, markdown authoring, PlantUML diagrams, editorial review, and publishing.'
argument-hint: 'Describe the page topic, or provide a title and source material (transcripts, issue keys, technical domain)'
---

# Confluence Writer Skill

You help the user create, author, and publish Confluence pages by writing markdown files in the `confluence/` directory. Pages are converted from markdown to Atlassian Document Format (ADF) and published via the project's Python scripts. The full workflow covers page reservation, content authoring, diagram creation, editorial review, and publishing.

## When to Use

- User wants to create a new Confluence page or topic article
- User says "write a confluence page", "publish to confluence", "new article", or "topic article"
- User wants to update or republish an existing Confluence page
- User wants to draft documentation for the Confluence wiki

## Key Conventions

### File Naming

- Pattern: `{pageId}-{Sanitized-Page-Title}.md`
- New files start as `{Descriptive-Slug}.md` until the page ID is obtained
- The page ID prefix lets the publish script identify the target page

### No H1 Headings

Never include a `# Title` (H1) heading in the markdown body. Confluence Live Docs display the page title above the content — an H1 creates a duplicate.

### Frontmatter

Every page must have YAML frontmatter with tags:

```yaml
---
version: 1
tags:
  - primary-technology
  - infrastructure
---
```

- Use **lowercase, hyphenated** tag names
- Always include `infrastructure` for Infrastructure team docs
- Keep to **5–8 tags** per document

### Markdown Format

Follow these rules for ADF compatibility:

- **Headings:** `##` through `######` only (no H1)
- **Embeds:** `!embed[label](url)` for Loom/YouTube videos
- **Cards:** `!card[label](url)` for rich preview cards
- **Panels:** `!panel` / `!panel(warning)` / `!panel(error)` etc.
- **Status lozenges:** `!status[text](color)` — colors: neutral, blue, purple, yellow, red, green
- **Diagrams:** `!plantuml(assets/{pageId}/architecture.puml)`
- **Standard markdown:** bold, italic, code, links, tables, bullet/numbered lists, code blocks

### Tone

Write in <YOUR_NAME>'s voice — the same voice in the case notes and worklogs.

- **Direct and practical** — write like explaining to a peer engineer, not publishing a press release
- **First-person where it fits** — "I set up a meeting with Microsoft Support." "I confirmed the Fabric Runtime is 1.3." For topic articles, drop the "I" but keep the directness.
- **Opinionated** — state the standard, don't hedge. "Use `replaceWhere` for Silver writes. This makes re-runs safe." Not "You may want to consider using replaceWhere..."
- **Specific** — use real resource names, actual CLI commands, actual workspace IDs. Never write "the target resource" when you can write `lh_loanetl_brz`.
- **Structured for scanning** — tables, bullet lists, code blocks over long prose
- **Short sentences for emphasis** — one idea per sentence when it matters
- **No corporate filler** — never write "In order to achieve our goals" or "As part of our ongoing journey" or "This document aims to provide"
- **Name things** — connector names, vault names, pipeline names, service principal names. Readers should be able to act on what they read without going to look things up.

## Workflows

### A. Create a New Page

Use this when the user wants a brand new Confluence page.

#### Step 1 — Gather Information

Ask the user (one question at a time) for any missing details:

1. **Page title** — clear, descriptive title for the Confluence page
2. **Topic/content** — what the page should cover; source material (transcripts, issue keys, technical domain)
3. **Parent page ID** — defaults to `<PAGE_ID>` (Infrastructure topic articles) unless specified
4. **Space key** — defaults to `IPM` unless specified

If the user provides enough context, skip asking.

#### Step 2 — Reserve the Page (Get Page ID)

Create a stub markdown file and run the create script to obtain the real page ID. This must happen before writing content.

1. Create the stub:
   ```bash
   cat > confluence/{Descriptive-Slug}.md << 'EOF'
   ---
   tags:
     - infrastructure
     - topic-tag
   ---

   Article in progress.
   EOF
   ```

2. Run the create script:
   ```bash
   python3 scripts/create-confluence-page.py confluence/{Descriptive-Slug}.md \
     --space-key IPM \
     --parent-id <PAGE_ID> \
     --title "Page Title Here"
   ```

3. The script renames the file to `confluence/{pageId}-{Sanitized-Title}.md` and writes `version: 1`

4. Create the asset directory:
   ```bash
   mkdir -p assets/{pageId}
   ```

#### Step 3 — Author the Content

Write the full article in the renamed file. For **topic articles** (thematic collections of Loom videos and technical content), use this structure:

```markdown
---
version: 1
tags:
  - primary-technology
  - secondary-technology
  - infrastructure
---

One-paragraph summary of the topic area.

**Team:** <ORG_NAME> Infrastructure · Internal Documentation

| Metric | Value |
| --- | --- |
| Key metric 1 | Value |
| Key metric 2 | Value |

!plantuml(assets/{pageId}/architecture.puml)

### Contents

1. Section One
2. Section Two

## 1. Section One

Content with embeds for Loom videos.

!embed[duration - Title](https://www.loom.com/share/...)

## Related Pages

- [Related Article](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{pageId}) — brief description

## N. Video Walkthroughs

!embed[duration - Title](https://www.loom.com/share/...)
```

For **non-topic pages** (guides, runbooks, reference docs), adapt the structure — skip the metrics table and video walkthroughs if not applicable, but keep the frontmatter, summary paragraph, and logical section organization.

**Authoring rules:**
- Embed labels follow `[duration - Descriptive Title]` format
- Place `!embed` directives at the end of the section they illustrate
- Include real CLI commands and code snippets
- Use tables for comparisons and component summaries
- Link first mention of key Azure/Microsoft services to Microsoft Learn docs (3–10 links per article)
- Add 3+ cross-links in `## Related Pages` using real Confluence page URLs

#### Step 4 — Create the PlantUML Diagram (if applicable)

Create `assets/{pageId}/architecture.puml` following the project's PlantUML style conventions. The diagram should show 5–10 nodes covering the high-level architecture. Pick a unique complementary color pair (check the Topic Article Registry to avoid duplicates).

#### Step 5 — Editorial Review

Run a three-pass editorial review on the content:

1. **Developmental edit** — structure, section balance, logical flow, opening strength
2. **Line edit** — word choice, active voice, cut filler, tighten prose
3. **Copy edit** — grammar, punctuation, formatting consistency

Apply fixes directly — don't just flag them.

#### Step 6 — Add Documentation Links

Link first mention of key services to Microsoft Learn or GitHub docs:
- 3–10 links per article
- First mention only
- Never inside code blocks, embeds, or table headers
- Use `[display text](url)` format

#### Step 7 — Publish

```bash
python3 scripts/publish-markdown-to-confluence.py confluence/{pageId}-{Title}.md
```

This renders PlantUML to PNG, uploads attachments, and pushes ADF content.

#### Step 8 — Confirm

Tell the user:
- Page title and ID
- URL: `https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{pageId}`
- That the page is live on Confluence

### B. Update an Existing Page

Use this when the user wants to edit a page already in the `confluence/` directory.

1. Find the file in `confluence/` by page ID or title substring
2. Edit the markdown content as requested
3. Publish:
   ```bash
   python3 scripts/publish-markdown-to-confluence.py confluence/{pageId}-{Title}.md
   ```
4. If version conflict occurs, use `--force` flag

### C. Batch Creation (Multiple Pages)

When creating multiple pages:

1. Create all stubs and get all page IDs first (sequentially — not in parallel)
2. Create all asset directories
3. Then write content for all articles — this lets cross-links use real page IDs
4. Publish sequentially to avoid PlantUML server rate limits

## Reference: Topic Article Registry

Check the existing topic articles to avoid overlap and find cross-link targets:

| Page ID | Title |
|---|---|
| <PAGE_ID> | AI Copilot and Agentic Automation |
| <PAGE_ID> | API, APIM, and Connector Microservices |
| <PAGE_ID> | Azure Policy, Governance, and Standards |
| <PAGE_ID> | CI/CD and GitHub Delivery Patterns |
| <PAGE_ID> | Cloud Operations, Utilities, and Enablement |
| <PAGE_ID> | Cross-Cloud Drift and Change Reconciliation |
| <PAGE_ID> | Fabric Scheduling and Orchestration |
| <PAGE_ID> | Infrastructure as Code Foundations |
| <PAGE_ID> | Microsoft Fabric Architecture and Engineering |
| <PAGE_ID> | Networking, IPAM, and Certificate Automation |
| <PAGE_ID> | Platform Engineering for Function App Workloads |
| <PAGE_ID> | Security Monitoring, Sentinel, and Observability |
| <PAGE_ID> | ESS Platform — Business Value & Cross-Team Benefits |

## Reference: Cross-Link Clusters

Group related pages and link within and across clusters:

| Cluster | Topics |
|---|---|
| Fabric Platform | CAF Naming, Onboarding, Architecture, Migration, EDM, Scheduler |
| AI & Copilot | <ORG_SHORT> AI, Copilot Architecture, Agentic Automation |
| Networking & APIM | APIM Spoke Network, Azure IPAM, Five9, Acmebot |
| Security & Governance | Security Scanning, Sentinel, Policy & Standards |
| IaC & CI/CD | IaC Foundations, CI/CD Patterns, Cross-Cloud Drift |
| Platform & Operations | API Microservices, Cloud Operations, Platform Engineering |

## Reference: Common Service URLs

| Service | URL |
|---|---|
| Azure Functions | `https://learn.microsoft.com/azure/azure-functions/functions-overview` |
| Bicep | `https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview` |
| API Management | `https://learn.microsoft.com/azure/api-management/api-management-key-concepts` |
| Microsoft Fabric | `https://learn.microsoft.com/fabric/fundamentals/microsoft-fabric-overview` |
| Microsoft Sentinel | `https://learn.microsoft.com/azure/sentinel/overview` |
| Microsoft Foundry | `https://learn.microsoft.com/azure/foundry/foundry-overview` |
| Azure OpenAI | `https://learn.microsoft.com/azure/ai-services/openai/overview` |
| Key Vault | `https://learn.microsoft.com/azure/key-vault/general/overview` |
| Managed Identity | `https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview` |
| GitHub Actions | `https://docs.github.com/actions` |
| Deployment Stacks | `https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks` |

## Scripts Reference

| Script | Purpose |
|---|---|
| `scripts/create-confluence-page.py` | Create a new page from markdown stub, get page ID |
| `scripts/publish-markdown-to-confluence.py` | Convert markdown → ADF, publish, sync labels |
| `scripts/get-confluence-page.py` | Download a page as markdown |

## Important Notes

- Always get the page ID **before** writing content — this eliminates placeholder filenames and broken cross-links
- The publish script reads `CONFLUENCE_EMAIL` and `WWEEKS_CONFLUENCE_API_TOKEN` from `.env`
- PlantUML diagrams are rendered to PNG at publish time — SVG is not supported
- Version conflicts are detected via the `version:` field in frontmatter — use `--force` to override
- Publish pages sequentially, not in parallel, to avoid rate limits
