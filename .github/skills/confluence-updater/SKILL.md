---
name: confluence-updater
description: 'Edit sections, append content, and update existing Confluence pages. Use when the user says "update the runbook", "append to the page", "fix the commands on confluence", or wants to patch existing documentation. Wraps scripts/confluence_update_page.py. Distinct from confluence-writer which creates net-new articles.'
argument-hint: 'Specify the Confluence page URL or ID and what content to update, replace, or append'
---

# Confluence Updater Skill

Edit sections, append content, and update existing Confluence pages. Use for patching runbooks, backlog pages, and documentation that already exists. Wraps `scripts/confluence_update_page.py`.

**Distinct from `confluence-writer`:** that skill creates net-new articles. This skill edits what's already there.

## When to Use

- "Update the runbook section on page X"
- "Append the resolution to the Confluence page"
- "Fix the commands in the PIM runbook"
- "Add a new section to the backlog page"
- User says "update confluence" about an existing page

---

## Workflow

### Step 1 — Find the page

If you have a URL like `https://<YOUR_ATLASSIAN>.atlassian.net/wiki/spaces/<SPACE>/pages/<PAGE_ID>`, the page ID is `<PAGE_ID>`.

If you need to search:
```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

python3 scripts/confluence_update_page.py --search "PIM runbook" --space IPM
```

### Step 2 — Read current content

```bash
python3 scripts/confluence_update_page.py --page-id {PAGE_ID} --show
```

Shows: title, version, space, last updated, content excerpt.

### Step 3 — Make the edit

**Replace a specific section** (finds heading, replaces content until next heading):
```bash
python3 scripts/confluence_update_page.py \
  --page-id {PAGE_ID} \
  --replace-section "Commands" \
  "new content here — plain text, newlines become paragraphs"
```

**Append to end of page:**
```bash
python3 scripts/confluence_update_page.py \
  --page-id {PAGE_ID} \
  --append "Update $(date +%Y-%m-%d): resolution confirmed, ticket closed."
```

**Update page title:**
```bash
python3 scripts/confluence_update_page.py --page-id {PAGE_ID} --set-title "New Title"
```

### Step 4 — Confirm

Run `--show` again to verify the edit landed correctly.

---

## Important Notes

- Content is plain text only — Confluence storage format handles rendering
- The `--replace-section` flag does a case-insensitive heading match
- Each PUT increments the page version — check version before editing if working concurrently
- For major rewrites or new pages, use the `confluence-writer` skill instead
- Page IDs are in the URL: `.../pages/{ID}/...` or `.../pages/{ID}?...`
