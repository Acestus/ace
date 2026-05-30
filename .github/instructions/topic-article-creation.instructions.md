---
description: "End-to-end workflow for creating new Confluence topic articles from Loom transcripts, case work, and IaC stacks. Use when the user asks to create a new topic article, generate an article from transcripts, or categorize videos into a new domain article."
applyTo: "confluence/**/*.md"
---

# Topic Article Creation Workflow

## Purpose

Defines the end-to-end process for creating a new Confluence topic article — from identifying the domain, gathering source material (Loom transcripts, case work, IaC stacks), through authoring, fact-checking, publishing, and cross-linking.

Topic articles are thematic knowledge articles that consolidate related Loom video walkthroughs and technical content into a single readable reference. Each article covers one infrastructure domain (e.g., networking, CI/CD, AI). All topic articles live under parent page `<PAGE_ID>` in space `IPM`.

---

## Phase 1 — Identify the Domain

### When to Create a New Article

Create a new topic article when a domain has:

- **3+ Loom videos** covering related topics
- **Active case work** or IaC stacks in the domain
- **No existing article** covering the topic (check the registry in `confluence-live-docs.instructions.md`)

### Candidate Discovery

Check `BACKLOG.md` under "New Topic Articles" for pre-identified candidates. Each candidate includes:

- Evidence (issues, stacks, existing coverage gaps)
- Suggested parent page ID
- Priority ranking

### Video Inventory

The Loom video library is tracked in `docs/transcripts/loom-library.md` (121 videos). VTT transcript files are in `transcripts/` (git-ignored, 506 files including training content).

To identify unassigned videos:

1. List all `!embed` URLs across existing articles:
   ```bash
   grep -h '!embed\[' confluence/16*.md | grep -oP 'https://www\.loom\.com/share/[a-f0-9]+' | sort -u
   ```
2. Compare against `docs/transcripts/loom-library.md` to find videos not yet embedded in any article

---

## Phase 2 — Reserve the Page

Create a stub page on Confluence to obtain the page ID before writing any content. The page ID is used in file names, asset directories, `!plantuml` paths, and cross-links — having it early eliminates post-publish renaming and placeholder tokens.

### Create the Stub

1. Create a minimal markdown file with only frontmatter and a placeholder summary:
   ```
   confluence/{Descriptive-Slug}.md
   ```
   ```markdown
   ---
   tags:
     - infrastructure
   ---

   Article in progress.
   ```
2. Run the create script:
   ```bash
   python3 scripts/create-confluence-page.py confluence/{Descriptive-Slug}.md \
     --space-key IPM \
     --parent-id <PAGE_ID> \
     --title "My New Topic Article"
   ```
3. The script creates the page, renames the file to `{pageId}-{Sanitized-Title}.md`, and writes `version: 1` into the frontmatter.
4. Create the asset directory using the page ID:
   ```bash
   mkdir -p assets/{pageId}
   ```

From this point forward, all references use the real page ID — no slugs, no placeholders, no renaming.

---

## Phase 3 — Gather Source Material

### Transcript-Based Articles

For articles built primarily from Loom transcripts:

1. **Identify matching VTT files** in `transcripts/` by video title (filenames mirror Loom titles)
2. **Read the transcripts** to understand what each video covers — focus on key decisions, architecture patterns, and CLI commands demonstrated
3. **Group related videos** into logical sections (typically 3–8 sections per article)
4. **Extract key content** from each transcript:
   - Architecture decisions and their rationale
   - CLI commands or code patterns demonstrated
   - Before/after comparisons
   - Problems and their solutions

### Case-Based Articles

For articles where case work provides the primary evidence:

1. **Read the issue docs** in `issues/{ticketNumber} - {description}/` — focus on the Actions log (reverse-chronological) and Follow-up status
2. **Extract patterns** that generalize beyond the specific ticket — architecture decisions, solution approaches, lessons learned
3. **Reference IaC stacks** in `infrastructure/` that implement the patterns described in issues

### Hybrid Approach

Most articles combine transcripts and issue work. Lead with the conceptual content from transcripts, reinforce with real examples from issues.

---

## Phase 4 — Author the Markdown

### File Setup

The file already exists as `confluence/{pageId}-{Sanitized-Title}.md` from Phase 2. Replace the placeholder summary with the full article content.

### Required Structure

Follow the standard topic article layout from `confluence-live-docs.instructions.md`:

```markdown
---
version: 1
tags:
  - primary-technology
  - secondary-technology
  - infrastructure
---

One-paragraph summary of the topic area. Direct, practical, specific.

**Team:** <ORG_NAME> Infrastructure · Internal Documentation

| Metric | Value |
| --- | --- |
| Key metric 1 | Value |
| Key metric 2 | Value |
| Key metric 3 | Value |

!plantuml(assets/{pageId}/architecture.puml)

### Contents

1. Section Title
2. Section Title
...

## 1. Section Title

Prose content — architecture decisions, patterns, CLI examples.

!embed[duration - Descriptive Title](https://www.loom.com/share/...)

## Related Pages

- [Related Article](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{pageId}) — brief description

## N. Video Walkthroughs

!embed[duration - Title](https://www.loom.com/share/...)
```

### Authoring Rules

- **No H1 heading** — the Confluence page title is set via `--title` during creation
- **Summary paragraph** — one paragraph, no filler, state what the article covers and why it matters
- **Metrics table** — 3–5 rows of key facts (technologies, patterns, counts)
- **Numbered sections** — each section covers one coherent sub-topic
- **Embed placement** — place `!embed` directives at the end of the section they illustrate, not in the middle of prose
- **Embed labels** — format as `[duration - Descriptive Title]` (e.g., `[3 min - Bicep Config Drift]`)
- **Code blocks** — include real CLI commands, code snippets, or configuration patterns demonstrated in the videos
- **Tables** — use tables for comparisons, decision frameworks, and component summaries
- **Links** — link first mention of each key Azure/Microsoft service to its Microsoft Learn documentation page (3–10 links per article, outside of code blocks and embed directives)
- **Related Pages** — link to 3+ related articles using Confluence page URLs
- **Video Walkthroughs** — always the last section, collecting all embeds for quick scanning

### Writing Standard Content from Transcripts

When converting transcript content to article prose:

1. **Distill, don't transcribe** — extract the decision, pattern, or insight; drop verbal filler, repetition, and tangents
2. **Attribute correctly** — if the video says "we chose X over Y because Z," write it as a decision with rationale
3. **Add structure** — transcripts are stream-of-consciousness; organize into problem → solution → implementation
4. **Include specifics** — real resource names, CLI commands, and configuration values from the video
5. **Skip introductions** — videos often start with "today we're going to look at..." — skip that and lead with the content

---

## Phase 5 — Create the PlantUML Diagram

### Setup

1. Create the diagram source file using the page ID from Phase 2:
   ```
   assets/{pageId}/architecture.puml
   ```

### Style

Follow `plantuml-style.instructions.md`:

- Use Azure-PlantUML sprites via `rectangle` elements (not macros)
- Pick a **unique complementary color pair** from the color wheel (check existing palette assignments in the Topic Article Registry in `confluence-live-docs.instructions.md` to avoid duplicates)
- Vertical top-to-bottom layout with explicit `-down->` arrows
- Do **not** reuse medallion colors (`#F5DEB3`, `#E8E8E8`, `#FFF8DC`) outside of Fabric medallion diagrams

### Content

The diagram should show the high-level architecture of the domain — key Azure services, data flow, and integration points. Keep it to 5–10 nodes. The diagram is rendered to PNG by the publish script and uploaded as a Confluence page attachment.

---

## Phase 6 — Fact-Check

Before publishing, verify technical claims against authoritative sources:

1. **Azure service capabilities** — use Microsoft Learn documentation or Azure MCP tools to confirm feature claims (e.g., "StandardV2 supports VNet injection" — does it?)
2. **Product naming** — use current names (Microsoft Foundry, not Azure AI Foundry; Microsoft Sentinel, not Azure Sentinel)
3. **CLI syntax** — verify command flags and parameter names against `--help` or docs
4. **Feature availability** — confirm features exist in the stated SKU or tier
5. **Architecture patterns** — validate scaling models, identity flows, and networking constraints

### Common Corrections

| Mistake | Correction |
|---|---|
| "Azure AI Foundry" | **Microsoft Foundry** (current name) |
| "Azure Sentinel" | **Microsoft Sentinel** (current name) |
| "VNet-injected APIM StandardV2" | StandardV2 supports **outbound VNet integration, inbound private endpoints** (VNet injection is Premium v2 only) |
| "Flex Consumption per-function scaling" | HTTP, Durable, and Blob triggers scale **per group**; other triggers scale per function |
| "Deployment Stacks what-if" | **Bicep what-if** (`az deployment group what-if`) — Deployment Stacks manage lifecycle, not preview |

---

## Phase 7 — Editorial Review (3-Pass)

Run the three-pass editorial process from the `editorial-assistant` skill autonomously — apply all fixes directly without waiting for user interaction between passes. This phase runs after fact-checking (Phase 6) so the content is technically accurate, and before documentation links (Phase 8) so link placement accounts for any prose restructuring.

Load the three reference checklists and evaluate the article against each. For technical articles, skip fiction-specific criteria (character arcs, dialogue, POV) and focus on the applicable items.

### Pass 1: Developmental Edit

Evaluate against `.github/skills/editorial-assistant/references/developmental-edit.md`.

Focus areas for topic articles:

- **Opening & hook** — does the summary paragraph state what the article covers and why it matters?
- **Structure & pacing** — does each numbered section advance the topic? Are there sections that repeat content already covered elsewhere?
- **Argument & logic** — is the thesis clear? Does each section support it with evidence or examples? Are claims concrete and specific?
- **Section balance** — are sections roughly proportional, or is one section three times the length of the others?

Apply fixes: restructure sections, cut redundant content, strengthen the opening, reorder for logical flow.

### Pass 2: Line Edit

Evaluate against `.github/skills/editorial-assistant/references/line-edit.md`.

Focus areas for topic articles:

- **Show vs. tell** — are benefits stated abstractly ("improves efficiency") when they could be shown with specifics ("reduces deploy time from 60 min to 5 min")?
- **Word choice** — replace vague or generic words with precise technical terms. Cut filler words (very, really, basically, actually, just).
- **Filter words** — remove "felt", "seemed", "appeared" — state facts directly.
- **Passive voice** — convert to active where the actor is known.
- **Economy** — cut redundant phrases, unnecessary adverbs, and throat-clearing openings.
- **Transitions** — ensure paragraphs and sections flow logically without overusing transition phrases.

Apply fixes: tighten prose, replace vague language with specifics, cut filler, activate passive constructions.

### Pass 3: Copy Edit

Evaluate against `.github/skills/editorial-assistant/references/copy-edit.md`.

Focus areas for topic articles:

- **Grammar & syntax** — subject-verb agreement, correct verb tenses, dangling modifiers.
- **Punctuation** — em dashes, serial commas, correct use of code backticks.
- **Consistency** — numbers (spelled out vs. numerals), date formats, abbreviation usage, capitalization in headers.
- **Internal consistency** — resource names spelled the same throughout, metric values consistent between summary table and body text.
- **Formatting** — header hierarchy, list formatting, table alignment, consistent use of bold/italic/code markup.

Apply fixes: correct grammar, normalize formatting, enforce consistency.

### Output

After all three passes, the article should be publication-ready. Do not add a summary of changes — the edits speak for themselves in the git diff.

---

## Phase 8 — Add Documentation Links

Link first mention of each key Azure or Microsoft service to its Microsoft Learn or GitHub documentation page.

### Rules

- **3–10 links per article** — enough for reference, not so many the prose is cluttered
- **First mention only** — don't re-link the same service in later sections
- **Outside code blocks** — never add links inside fenced code blocks, table headers, or `!embed`/`!plantuml` directives
- **Standard markdown** — `[display text](url)` format
- **Prefer** `learn.microsoft.com` for Azure services, `docs.github.com` for GitHub features

### Common Service URLs

| Service | URL |
|---|---|
| Azure Functions | `https://learn.microsoft.com/azure/azure-functions/functions-overview` |
| Flex Consumption | `https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan` |
| Bicep | `https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview` |
| Terraform on Azure | `https://learn.microsoft.com/azure/developer/terraform/overview` |
| API Management | `https://learn.microsoft.com/azure/api-management/api-management-key-concepts` |
| Microsoft Fabric | `https://learn.microsoft.com/fabric/fundamentals/microsoft-fabric-overview` |
| Microsoft Sentinel | `https://learn.microsoft.com/azure/sentinel/overview` |
| Microsoft Foundry | `https://learn.microsoft.com/azure/foundry/foundry-overview` |
| Azure OpenAI | `https://learn.microsoft.com/azure/ai-services/openai/overview` |
| Key Vault | `https://learn.microsoft.com/azure/key-vault/general/overview` |
| Entra ID | `https://learn.microsoft.com/entra/fundamentals/whatis` |
| Managed Identity | `https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview` |
| GitHub Actions | `https://docs.github.com/actions` |
| OIDC for GitHub | `https://learn.microsoft.com/azure/developer/github/connect-from-azure` |
| Deployment Stacks | `https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-stacks` |
| App Insights | `https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview` |
| Event Grid | `https://learn.microsoft.com/azure/event-grid/overview` |

---

## Phase 9 — Publish and Cross-Link

The page already exists from Phase 2. This phase publishes the full content, renders diagrams, and adds cross-links.

### Publish the Article

```bash
python3 scripts/publish-markdown-to-confluence.py {pageId} confluence/{pageId}-{Title}.md \
  --message "Initial publish with full content and architecture diagram"
```

This renders the PlantUML to PNG, uploads it as a page attachment, and pushes the ADF content with the embedded image.

### Add Related Pages

Link to 3+ related articles in the `## Related Pages` section. Use the real page ID (known since Phase 2) in all cross-link URLs — no placeholders needed.

Group by topic cluster:

| Cluster | Pages |
|---|---|
| Fabric Platform | CAF Naming, Onboarding Guide, Architecture, Migration Guide, EDM Transformation, Scheduler, Scheduling & Orchestration |
| AI & Copilot | <ORG_SHORT> AI, Copilot Architecture, Agentic Automation |
| Networking & APIM | APIM Spoke Network, Azure IPAM, Five9 Agent, Acmebot, Networking Overview |
| Security & Governance | Security Scanning, Sentinel & Observability, Policy & Standards |
| IaC & CI/CD | IaC Foundations, CI/CD Patterns, Cross-Cloud Drift |
| Platform & Operations | API Microservices, Cloud Operations, Platform Engineering |

### Update Existing Articles

Add a reciprocal link from related existing articles back to the new article using the real page ID. Republish each updated file:

```bash
python3 scripts/publish-markdown-to-confluence.py {existingPageId} confluence/{pageId}-{ExistingTitle}.md \
  --message "Add cross-link to {New Article Title}"
```

### Update the Topic Article Registry

Add the new article's page ID, title, and color palette to the `Topic Article Registry` table in `confluence-live-docs.instructions.md`.

---

## Phase 10 — Update Backlog

After successful publish:

1. Remove the article (or mark as done) from `BACKLOG.md` under "New Topic Articles"
2. Add any follow-up items discovered during authoring (missing videos, fact-check corrections, new cross-link candidates) back into the appropriate `BACKLOG.md` section

---

## Checklist

Use this checklist before marking an article as complete:

- [ ] Stub page created and page ID obtained (Phase 2)
- [ ] Asset directory created as `assets/{pageId}/`
- [ ] Markdown follows the standard topic article layout (frontmatter, summary, metrics, diagram, numbered sections, related pages, video walkthroughs)
- [ ] 5–8 tags in frontmatter; includes `infrastructure`
- [ ] `!plantuml(assets/{pageId}/architecture.puml)` directive present with rendered diagram
- [ ] All Loom embed URLs are valid and labels follow `[duration - Title]` format
- [ ] Technical claims fact-checked against Microsoft Learn or authoritative docs
- [ ] Product names are current (Microsoft Foundry, Microsoft Sentinel, etc.)
- [ ] Editorial 3-pass review completed (developmental → line → copy) and fixes applied
- [ ] 3–10 documentation links on first mention of key services
- [ ] No links inside code blocks, embed directives, or table headers
- [ ] 3+ related page cross-links in `## Related Pages` using real page ID
- [ ] Reciprocal links added to existing related articles
- [ ] Full content published to Confluence via `publish-markdown-to-confluence.py`
- [ ] Topic Article Registry updated in `confluence-live-docs.instructions.md`
- [ ] `BACKLOG.md` updated
