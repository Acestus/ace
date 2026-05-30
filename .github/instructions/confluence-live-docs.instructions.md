---
applyTo: 'confluence/**/*.md'
---

# Confluence Live Doc Workflow

## Purpose

Guidelines for editing Confluence Live Docs as local markdown files. Pages are downloaded as ADF (Atlassian Document Format), converted to markdown for editing in VS Code, then uploaded back as ADF. These rules ensure clean round-trip conversion.

## File Naming

- Pattern: `{pageId}-{Sanitized-Page-Title}.md`
- The page ID prefix allows the upload script to identify the target page
- Example: `<PAGE_ID>-Microsoft-Fabric-Platform--Onboarding-Guide.md`

## YAML Frontmatter — Tags

Every confluence markdown file **must** include YAML frontmatter with a `tags:` list. These are synced to Confluence as page labels on upload.

```yaml
---
version: 42
tags:
  - fabric
  - onboarding
  - infrastructure
---
```

### Version Field (Conflict Detection)

The `version:` field tracks the Confluence page version this file was last synced with. The upload script uses it to detect conflicts:

- **On upload:** If `version:` exists, the script compares it to the remote version. If they differ, the upload is **aborted** with a conflict error — someone else edited the page since the last download.
- **After successful upload:** The script automatically updates `version:` in the file to the new remote version.
- **If `version:` is missing:** The script warns but proceeds (backward compatible). The version is written into the frontmatter after the first successful upload.
- **To force upload anyway:** Use the `-Force` flag to skip the conflict check.

### Tagging Rules

- Use **lowercase, hyphenated** tag names (e.g., `azure-functions`, not `Azure Functions`)
- Always include `infrastructure` for docs authored by the Infrastructure team
- Use the **project or service name** as a tag (e.g., `fabric`, `ipam`, `acmebot`, `five9`)
- Use **technology tags** for key Azure services (e.g., `bicep`, `azure-functions`, `key-vault`, `private-endpoints`)
- Use **domain tags** for the topic area (e.g., `networking`, `tls-certificates`, `naming-convention`, `rag`)
- Keep tags to **5–8 per document** — enough to be discoverable, not so many they lose meaning
- Do not duplicate the page title as a tag

### Common Tags Reference

| Category | Tags |
|---|---|
| Platform | `fabric`, `azure`, `github`, `confluence` |
| Services | `azure-functions`, `api-management`, `key-vault`, `cosmos-db`, `azure-ai-search`, `azure-openai` |
| Patterns | `bicep`, `deployment-stacks`, `private-endpoints`, `managed-identity`, `rag` |
| Domains | `networking`, `tls-certificates`, `naming-convention`, `onboarding`, `governance`, `scheduler`, `self-healing` |
| Architecture | `medallion-architecture`, `workspace-model`, `deployment-pipeline` |
| Team | `infrastructure` |

## Markdown Formatting for ADF Compatibility

The markdown-to-ADF converter supports a specific subset of markdown. Follow these rules to ensure content renders correctly when uploaded to Confluence Live Docs.

### No H1 Heading in Content

Do **not** include a `# Title` (H1) heading at the top of the markdown body. Confluence Live Docs already display the page title above the content. An H1 in the body creates a duplicate title that looks ugly. Start content with a subtitle, intro paragraph, or `##` heading instead.

### Supported Elements

- **Headings:** `##` through `######` — use H2 and below in the body (H1 is the page title, shown by Confluence)
- **Paragraphs:** Plain text with blank line separation
- **Bold / Italic / Code:** `**bold**`, `*italic*`, `` `inline code` ``
- **Links:** `[text](url)` — converted to ADF link marks
- **Bullet lists:** `- item` or `* item` (one level of nesting)
- **Numbered lists:** `1. item`
- **Tables:** Standard markdown tables with `| col | col |` and `| --- | --- |`
- **Code blocks:** Triple backtick with optional language identifier
- **Horizontal rules:** `---`

### Embeds and Smart Links

The converter supports three custom directives for embedding external content as Confluence Smart Links:

| Syntax | ADF Node | Rendering |
|---|---|---|
| `!embed[label](url)` or `!embed url` | `embedCard` | Smart Link embed — video player for Loom/YouTube, interactive embed for others |
| `!card[label](url)` or `!card url` | `blockCard` | Rich preview card (title, description, thumbnail) |
| `[text](!card:url)` | `inlineCard` | Inline Smart Link within a paragraph |

**All `!embed` directives produce `embedCard` nodes in ADF.** Confluence's Smart Link system unfurls the URL into the appropriate rendering — video player for Loom/YouTube, interactive preview for others. Requires the **Loom Marketplace app** to be installed in the Atlassian instance for Loom URLs to render as embedded players.

> **Do NOT use the `widget` macro** (`extension` node with `extensionKey: "widget"`) for video embeds on Live Docs. The `widget` macro is a legacy Confluence macro that renders as a broken gear icon on Live Doc pages. Use `embedCard` instead — it renders correctly on both Live Docs and classic pages.

```markdown
!embed[Architecture Walkthrough](https://www.loom.com/share/146853a963c44f3db845378242497cb2)
!embed[Demo Video](https://www.youtube.com/watch?v=tQMrrNo16jo)
```

**For Microsoft Stream / SharePoint videos**, use `!embed`:

```markdown
!embed[Project Overview Video](https://<org_short>fg.sharepoint.com/:v:/s/Infrastructure/IQDg...)
```

This renders as an `embedCard` in ADF, which Confluence unfurls into an embedded video player (requires SharePoint ↔ Atlassian integration to be configured in the tenant).

**Fallback:** If the embed doesn't render as a player (integration not enabled, unsupported URL), Confluence shows it as a rich link card instead. You can also use `!card` explicitly if you only want the card preview.

### Status Lozenges

Inline colored badges for visual indicators (pipeline stages, statuses, labels). Use `!status[text](color)` inside any paragraph or panel.

| Color | Keyword | Use For |
|---|---|---|
| Gray | `neutral` | Default, intermediate stages |
| Blue | `blue` | Source systems, inputs |
| Purple | `purple` | Special/custom stages |
| Yellow | `yellow` | Warnings, Gold layer |
| Red | `red` | Errors, blockers |
| Green | `green` | Success, final stage, outputs |

```markdown
!status[Bronze](neutral) → !status[Silver](neutral) → !status[Gold](yellow) → !status[BI / Reporting](green)
```

### Panels

Block-level colored containers. Use `!panel` or `!panel(type)` on its own line, followed by content lines. End the panel with a blank line.

| Syntax | Panel Type |
|---|---|
| `!panel` | `info` (default — blue) |
| `!panel(note)` | Note (purple) |
| `!panel(warning)` | Warning (yellow) |
| `!panel(error)` | Error (red) |
| `!panel(success)` | Success (green) |
| `!panel(tip)` | Tip (green) |

```markdown
!panel
!status[Source](blue) → !status[Bronze](neutral) → !status[Gold](yellow)

!panel(warning)
This migration requires downtime. Schedule during maintenance window.
```

### Diagrams (PlantUML)

Extension macros (`bodiedExtension` ADF nodes) render as "Unknown macro" errors on Live Doc pages — do **not** use them for diagrams.

Instead, use the `!plantuml(path)` directive. At publish time the script renders the `.puml` file to PNG, uploads it as a page attachment, and inserts an inline `mediaSingle`/`media` ADF node.

```markdown
!plantuml(assets/<PAGE_ID>/data-flow.puml)
```

- The path is relative to the workspace root (resolved from the markdown file's directory first, then one level up).
- Maintain the `.puml` source file under `assets/<page_id>/` in the repo — see `plantuml-style.instructions.md` for diagram conventions.
- SVG is **not** supported — Confluence shows "preview unavailable" for SVG attachments in `media` nodes. The script renders PNG.
- On `--dry-run`, PlantUML rendering and upload are skipped.

### Elements That Do NOT Round-Trip

These ADF elements flatten to plain text during download and cannot be reconstructed:

- **Panels** (info, warning, note, error boxes) — become plain paragraphs
- **Expand/collapse sections** — content is flattened inline
- **Status lozenges / badges** — become bold text runs
- **Metric cards** (the numbered KPI boxes) — become orphaned numbers and labels
- **Decision/action items** — become plain list items
- **Emoji shortcodes** — preserved as Unicode characters, not `:emoji:` syntax
- **Table of Contents macro** — becomes a collapsed run of SharePoint links (must be manually cleaned to a numbered list)

### Common Cleanup After Download

After downloading a page with `get-confluence-page.py`, review for these artifacts:

1. **Duplicate H1 titles** — ADF sometimes stores the title twice. Keep the descriptive one, remove the raw one.
2. **Collapsed TOC links** — A run of `[Section](https://sharepoint...)` links all on one line. Replace with a plain numbered list of section names.
3. **Orphaned metric numbers** — Numbers like `8+`, `101`, `< 5s` sitting alone on lines followed by labels. Convert to a `| Metric | Value |` table.
4. **Collapsed badge text** — `**Tag1Tag2Tag3**` with no separators. Replace with `` `Tag1` · `Tag2` · `Tag3` `` format.
5. **Empty placeholder lists** — Items like `- 1`, `- 2`, `- 3` where ADF numbered steps lost their content. Either fill in the content or remove.
6. **Collapsed metadata lines** — Multi-field metadata on one line (owner, date, team). Break into separate lines with `**Label:** Value` format.

## Tone and Voice

These documents are authored by a **cloud infrastructure engineer** who is the SME for Microsoft Fabric, GitHub, and Azure. The tone should be:

- **Direct and practical** — write like you're explaining to a peer engineer
- **Opinionated where appropriate** — state what the standard is, not "you might want to consider"
- **Specific** — use real resource names, subscription IDs, CLI commands, and code examples
- **Not marketing copy** — avoid superlatives, buzzwords, and filler phrases
- **Structured for scanning** — tables, bullet lists, and code blocks over long prose paragraphs

## Scripts

| Script | Purpose |
|---|---|
| `scripts/get-confluence-page.py` | Download a page as markdown, storage HTML, or raw JSON |
| `scripts/publish-markdown-to-confluence.py` | Convert markdown → ADF, publish, and sync labels from frontmatter |
| `scripts/update-confluence-page.ps1` | Update a page with raw HTML (non-Live Doc pages) |
| `scripts/create-confluence-page.py` | Create a new page from markdown, sync labels, rename file with page ID |
| `scripts/test-connection.ps1` | Verify Confluence API credentials |

## VS Code Tasks

Use the VS Code tasks (`.vscode/tasks.json`) to run scripts without memorizing commands:

- **Confluence: Upload Markdown** — uploads the current editor file
- **Confluence: Upload Markdown (Dry Run)** — saves ADF output without uploading
- **Confluence: Get Page** — downloads a page by ID

## Topic Article Structure

Topic articles are thematic groupings of related Loom walkthroughs and technical content from across the project. Each article consolidates videos and knowledge around a single domain (e.g., networking, CI/CD, AI). All 12 topic articles live under parent page `<PAGE_ID>` in space `IPM`.

### Standard Layout

Every topic article follows this structure:

```markdown
---
version: 3
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
...

## 1. Section One

Content with !embed directives for Loom videos.

!embed[duration - Title](https://www.loom.com/share/...)

## Related Pages

- [Related Article](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{pageId}) — brief description

## N. Video Walkthroughs

!embed[duration - Title](https://www.loom.com/share/...)
```

### Key Conventions

- **No H1 heading** — the Confluence page title is set during creation
- **Architecture diagram** goes between the metrics table and `### Contents`
- **Related Pages** section goes before the final Video Walkthroughs section
- **Video Walkthroughs** is always the last section, collecting all embeds for easy scanning
- **Embed labels** follow the format `[duration - Descriptive Title]`
- Each article has **one `architecture.puml`** under `assets/{pageId}/` using a unique complementary color palette (see `plantuml-style.instructions.md`)

### Topic Article Registry

| Page ID | Title | Color Palette |
|---|---|---|
| <PAGE_ID> | AI Copilot and Agentic Automation | Purple + Amber |
| <PAGE_ID> | API, APIM, and Connector Microservices | Teal + Rose |
| <PAGE_ID> | Azure Policy, Governance, and Standards | Red + Green |
| <PAGE_ID> | CI/CD and GitHub Delivery Patterns | Blue + Orange |
| <PAGE_ID> | Cloud Operations, Utilities, and Enablement | Slate + Gold |
| <PAGE_ID> | Cross-Cloud Drift and Change Reconciliation | Emerald + Pink |
| <PAGE_ID> | Fabric Scheduling and Orchestration | Indigo + Tangerine |
| <PAGE_ID> | Infrastructure as Code Foundations | Sky + Rose |
| <PAGE_ID> | Microsoft Fabric Architecture and Engineering | Medallion |
| <PAGE_ID> | Networking, IPAM, and Certificate Automation | Cyan + Vermillion |
| <PAGE_ID> | Platform Engineering for Function App Workloads | Violet + Lime |
| <PAGE_ID> | Security Monitoring, Sentinel, and Observability | Amber + Navy |
| <PAGE_ID> | ESS Platform — Business Value & Cross-Team Benefits | Fuchsia + Forest |

### Creating a New Topic Article

1. **Reserve the page first** — create a stub markdown file with minimal frontmatter, run `create-confluence-page.py` to get the page ID, then `mkdir -p assets/{pageId}`. **Do this before writing any content.**
2. **Gather source material** — transcripts, case work, IaC stacks
3. **Author the markdown** in the already-renamed `confluence/{pageId}-{Title}.md` using the layout above — all `!plantuml` paths and cross-links use the real page ID
4. **Create the diagram** under `assets/{pageId}/architecture.puml` using a unique color pair
5. **Fact-check, edit, and add documentation links**
6. **Publish** with the publish script — no renaming needed
7. **Cross-link** related articles using the real page ID and republish them

## Creating a New Page

New pages are created **as the very first step** to obtain the page ID. The page starts as a stub and is published with full content later. **Never use placeholder filenames or temporary page IDs** — always create the Confluence page and get the real ID before writing article content.

### Workflow

1. **Create a stub markdown file** — use a descriptive filename like `My-New-Topic.md` with minimal frontmatter (`tags:` only, no `version:` needed)
2. **Do NOT add an H1 heading** — the `--title` argument becomes the Confluence page title
3. **Run the create script:**

```bash
python3 scripts/create-confluence-page.py confluence/My-New-Topic.md \
  --space-key IPM \
  --parent-id <PAGE_ID> \
  --title "My New Topic"
```

4. **The script automatically:**
   - Creates the page with stub content
   - Syncs frontmatter tags as Confluence labels
   - Renames the file to `{pageId}-{Sanitized-Title}.md`
   - Writes `version: 1` into the frontmatter
5. **Create the asset directory:** `mkdir -p assets/{pageId}`
6. **Author the full article** in the renamed file using the real page ID for cross-links, asset paths, and `!plantuml` directives
7. **Publish** the completed article with `publish-markdown-to-confluence.py`

### AI Agent Workflow — Page ID First

When an AI agent is creating new articles, it **must** obtain the page ID before writing content. This avoids placeholder filenames, broken cross-links, and manual renaming.

**For each new article:**

1. Create a stub file with frontmatter tags only:

```bash
cat > confluence/My-New-Article.md << 'EOF'
---
tags:
  - infrastructure
  - topic-tag
---

Stub — content to follow.
EOF
```

2. Run the create script to get the page ID:

```bash
python3 scripts/create-confluence-page.py confluence/My-New-Article.md \
  --space-key IPM \
  --parent-id <PAGE_ID> \
  --title "My New Article"
```

3. The file is now `confluence/{pageId}-My-New-Article.md` with `version: 1` in frontmatter
4. Create the asset directory: `mkdir -p assets/{pageId}`
5. Write the full article content into the renamed file — all cross-links, `!plantuml(assets/{pageId}/...)` paths, and Related Pages references use the real page ID
6. Publish with `publish-markdown-to-confluence.py`

**When creating multiple articles in a batch**, create all stubs and get all page IDs first, then write content for all articles. This lets cross-links between the new articles use real page IDs from the start.

### Batch Creation

When creating multiple pages under the same parent, create them sequentially (one at a time). The public PlantUML server rate-limits rapid requests, and version conflicts are easier to diagnose sequentially.

## Cross-Linking Between Pages

Every article should link to at least **3 related pages** in the `confluence/` directory. Cross-links improve discoverability and create a navigable knowledge graph in Confluence.

### Link Format

Use the Confluence page URL with the page ID:

```markdown
[Page Title](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/{pageId})
```

### Placement

Add a `## Related Pages` section **before** the `## Video Walkthroughs` section (or before the footer if no video section exists). Use a bulleted list with a brief description of how the linked page relates:

```markdown
## Related Pages

- [Microsoft Fabric CAF Naming Convention](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/<PAGE_ID>) — naming standards for all Fabric artifacts
- [Fabric Migration Guide](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/<PAGE_ID>) — hands-on pilot migration using this naming convention
- [Azure Policy, Governance, and Standards](https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/<PAGE_ID>) — governance controls that enforce naming compliance
```

### Linking Strategy

Group pages into topic clusters and link within and across clusters:

| Cluster | Pages |
|---|---|
| Fabric Platform | CAF Naming, Onboarding Guide, Architecture, Migration Guide, EDM Transformation, Scheduler, Scheduling & Orchestration |
| AI & Copilot | <ORG_SHORT> AI, Copilot Architecture, Agentic Automation |
| Networking & APIM | APIM Spoke Network, Azure IPAM, Five9 Agent, Acmebot, Networking Overview |
| Security & Governance | Security Scanning, Sentinel & Observability, Policy & Standards |
| IaC & CI/CD | IaC Foundations, CI/CD Patterns, Cross-Cloud Drift |
| Platform & Operations | API Microservices, Cloud Operations, Platform Engineering |

Link to pages that a reader would naturally want next — the "what" page links to the "how" page, the architecture page links to the naming convention, the overview page links to the deep-dives.

## Publishing Updated Pages

After editing an existing page (adding cross-links, updating tags, fixing content):

```bash
python3 scripts/publish-markdown-to-confluence.py confluence/{pageId}-{Title}.md
```

Use `--force` if the local `version:` field is behind the remote version (someone edited the page on Confluence since the last sync).

### Publishing All Pages

To republish all pages (e.g., after batch cross-link additions):

```bash
for f in confluence/1*.md; do
  python3 scripts/publish-markdown-to-confluence.py "$f"
done
```

Publish sequentially — not in parallel — to avoid PlantUML server rate limits and version conflicts.
