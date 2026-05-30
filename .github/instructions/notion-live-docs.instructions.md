---
applyTo: 'notion/**/*.md'
---

# Notion Live Doc Workflow

## Purpose

Guidelines for editing Notion live docs as local markdown files. Pages are stored as markdown in the repo, edited in VS Code, then synced back to Notion.

## File Naming

- Pattern: `{pageId}-{Sanitized-Page-Title}.md`
- The page ID prefix allows the sync script to identify the target page
- Example: `<PAGE_ID>-Microsoft-Fabric-Platform--Onboarding-Guide.md`

## Frontmatter

Every Notion markdown file **must** include YAML frontmatter with a `tags:` list.

```yaml
---
version: 42
tags:
  - fabric
  - onboarding
  - infrastructure
---
```

### Version Field

The `version:` field tracks the Notion page version this file was last synced with.

- If `version:` exists and does not match the remote page, sync is aborted with a conflict error
- After successful sync, the script updates `version:` to the new remote version
- If `version:` is missing, the sync script warns but proceeds

### Tagging Rules

- Use lowercase, hyphenated tag names
- Always include `infrastructure` for docs authored by the Infrastructure team
- Use the project or service name as a tag
- Use technology and domain tags where helpful
- Keep tags to 5-8 per document

| Category | Tags |
|---|---|
| Platform | `fabric`, `azure`, `github`, `notion` |
| Services | `azure-functions`, `api-management`, `key-vault`, `cosmos-db`, `azure-ai-search`, `azure-openai` |
| Patterns | `bicep`, `deployment-stacks`, `private-endpoints`, `managed-identity`, `rag` |
| Domains | `networking`, `tls-certificates`, `naming-convention`, `onboarding`, `governance`, `scheduler`, `self-healing` |
| Architecture | `medallion-architecture`, `workspace-model`, `deployment-pipeline` |
| Team | `infrastructure` |

## Markdown Formatting

- Do **not** include an H1 title in the body
- Use H2 and below for content headings
- Use standard markdown tables, lists, code blocks, and links
- Keep formatting simple so the sync script can round-trip it cleanly

## Embeds and Smart Links

Use the custom directives below for rich content:

| Syntax | Use |
|---|---|
| `!embed[label](url)` or `!embed url` | Smart Link embed |
| `!card[label](url)` or `!card url` | Rich preview card |
| `[text](!card:url)` | Inline Smart Link |

- Use `!embed` for Loom and YouTube videos
- Use `!card` when you want a preview card instead of an embed
- Prefer PNG diagrams for attachments

## Diagrams

Use `!plantuml(path)` for PlantUML diagrams.

```markdown
!plantuml(assets/<PAGE_ID>/data-flow.puml)
```

- Keep source `.puml` files under `assets/<page_id>/`
- The sync script renders PNG and uploads it as a page attachment
- SVG is not supported

## Cleanup After Download

After downloading a page with `notion_sync.py`, review for:

1. Duplicate H1 titles
2. Collapsed TOC links
3. Orphaned metric numbers
4. Collapsed badge text
5. Empty placeholder lists
6. Collapsed metadata lines

## Scripts

| Script | Purpose |
|---|---|
| `scripts/notion_sync.py` | Sync markdown files to Notion pages |
| `scripts/notion_update_page.py` | Update an existing Notion page |
| `scripts/notion_create_page.py` | Create a new Notion page from markdown |
| `scripts/notion_search.py` | Search Notion pages by title |

