---
name: notion-writer
description: 'Create and publish Notion pages from markdown. Use when the user says "write a Notion page", "create a Notion article", "publish to Notion", or wants to author documentation. Handles the full workflow: page creation, content formatting, and publishing under the right parent.'
argument-hint: 'Describe the page you want to create, or provide the content'
---

# Notion Writer Skill

Create and publish Notion pages from markdown content. Use for runbooks, architecture notes, how-to articles, and any documentation that should live in Notion.

## When to Use

- User says "write a Notion page", "create a Notion article", "publish to Notion"
- User wants to document findings from a ticket investigation
- User wants to write a runbook, how-to, or architecture note

## Workflow

### Step 1 — Determine parent page

Ask the user where this page should live, or use the default:

```bash
# List top-level pages to find the right parent
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)
python3 scripts/notion_search.py --query "Infrastructure"
```

The `NOTION_ROOT_PAGE_ID` in `.env` is the default parent. Override with `--parent PAGE_ID` if needed.

### Step 2 — Draft the content

Write the article in markdown. Structure:
- `# Title` — matches the page title
- `## Overview` — 2-3 sentence summary
- `## Background` — context and why this matters
- `## Solution / Process` — the actual content
- `## References` — links to Linear issues, GitHub, Azure resources

### Step 3 — Create the page

```bash
python3 scripts/notion_create_page.py \
    --parent {PARENT_PAGE_ID} \
    --title "Infrastructure Runbook: Auth Token Configuration" \
    --file /tmp/article.md
```

Or with inline content:
```bash
python3 scripts/notion_create_page.py \
    --parent {PARENT_PAGE_ID} \
    --title "Quick Note: Deploy Process" \
    --body "## Steps\n- Step 1\n- Step 2"
```

### Step 4 — Verify and report

```
✓ Published to Notion: Infrastructure Runbook: Auth Token Configuration
  ID:  {page-id}
  URL: https://notion.so/...
```

Share the URL with the user for immediate access.

## Updating Existing Pages

To append content to an existing page:
```bash
python3 scripts/notion_update_page.py --page {PAGE_ID} --file update.md
```

To update the title:
```bash
python3 scripts/notion_update_page.py --page {PAGE_ID} --title "New Title"
```

## Article Writing Standards

- **Opening sentence** answers: what is this and why does it exist?
- **Active voice** throughout — "Configure the token TTL" not "The token TTL should be configured"
- **Commands are copy-pasteable** — no placeholders without clear instructions to replace them
- **Link to source** — every article links to the Linear issue that prompted it (if applicable)
- **Short sections** — aim for scannable, not comprehensive

## Environment

```
NOTION_API_KEY       — Integration token from notion.com/my-integrations
NOTION_ROOT_PAGE_ID  — Default parent page ID for new articles
```

Get a token at: https://www.notion.so/my-integrations
Share your Notion workspace/pages with the integration for it to have write access.
