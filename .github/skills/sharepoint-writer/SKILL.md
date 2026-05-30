---
name: sharepoint-writer
description: 'Create and publish HTML documents to the <ORG_NAME> Infrastructure SharePoint docs library. Use when the user says "write a SharePoint doc", "publish to SharePoint", "create a guide for SharePoint", or wants to produce a polished HTML document for the Infrastructure Files/docs folder. Handles the full workflow: HTML authoring, editorial review, and upload.'
argument-hint: 'Describe the document topic, or provide a title and source material (transcripts, issue keys, technical domain)'
---

# SharePoint Writer Skill

You help the user create, author, and publish polished HTML documents to the <ORG_NAME> Infrastructure SharePoint site. Documents are self-contained HTML files written in the project's standard visual style and uploaded to `Files/docs` via the Graph API. The full workflow covers HTML authoring, editorial review, and upload.

## When to Use

- User wants to create a new SharePoint document or guide
- User says "write a SharePoint doc", "publish to SharePoint", "create a guide", or "SharePoint HTML"
- User wants to update or re-upload an existing SharePoint document
- User wants a polished, browser-viewable version of a Confluence page or case write-up

## Target Location

| Field | Value |
|---|---|
| Site | `https://<org_short>fg.sharepoint.com/sites/Infrastructure` |
| Library | `Files` |
| Folder | `docs` |
| Browse URL | `https://<org_short>fg.sharepoint.com/sites/Infrastructure/Files/Forms/AllItems.aspx?id=%2Fsites%2FInfrastructure%2FFiles%2Fdocs&viewid=<RESOURCE_GUID>` |

## Key Conventions

### File Naming

- Pattern: `{kebab-case-title}.html`
- Example: `pim-activation-guide.html`, `fabric-workspace-onboarding.html`
- Files live in `sharepoint/` in the repository
- The same filename is used in SharePoint — uploading again overwrites the previous version

### HTML Style

All documents follow the project's HTML document style (see `.github/instructions/html-document-style.instructions.md`):

- **Font:** Segoe UI → Tahoma → Geneva → Verdana → sans-serif
- **Background:** `#faf9f8` · **Text:** `#323130` · **Primary accent:** `#0078d4`
- **h1** — blue with bottom border · **h2** — blue with left border
- All CSS inline in a single `<style>` block — no external dependencies
- Self-contained: renders identically in SharePoint, as a local file, or pasted into Confluence

### Document Structure (Standard)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document Title</title>
    <style>/* full inline CSS */</style>
</head>
<body>
    <h1>Document Title — context</h1>
    <div class="subtitle">Subtitle · <ORG_NAME> Infrastructure</div>

    <div class="executive-summary">
        <strong>Purpose:</strong> ...<br><br>
        <strong>Audience:</strong> ...
    </div>

    <div class="toc">...</div>

    <h2 id="section-1">1. Section Title</h2>
    ...

    <footer>...</footer>
</body>
</html>
```

### CSS Component Classes

| Class | Use |
|---|---|
| `.executive-summary` | Light blue `#e1f5fe`, 5px blue left border — purpose/audience opener |
| `.principle-box` | Gray `#f3f2f1` — key principles, definitions, context |
| `.highlight-box` | Amber `#fff4e6` — notes, tips, things to be aware of |
| `.warning-box` | Red `#ffebee` — risks, danger, things that are broken |
| `.success-box` | Green `#e8f5e8` — positive outcomes, confirmations |
| `.toc` | Table of contents for docs with 4+ sections |
| `.code-block` | Dark `#1e1e1e` bg, monospace — CLI commands, code snippets |
| `.inline-code` | Gray bg, blue monospace — inline `command` or `value` |
| `.metric-row` / `.metric-card` | Flex row of KPI cards |
| `.phase-card.phase-1` through `.phase-4` | White cards with colored top borders (green/orange/purple/red) |
| `.comparison-grid` / `.comparison-card` | Two-column comparison (`.dead-end` = red, `.target` = green) |
| `.flow-diagram` / `.flow-step` / `.flow-arrow` | Horizontal step flow |
| `.todo-item` / `.todo-number` | Numbered action card |
| `.contact-card` / `.contact-row` | Flex row of contact cards |

### Step-Card Pattern

For how-to guides, use numbered step cards:

```html
<div class="steps">
    <div class="step-card">
        <div class="step-number">1</div>
        <div class="step-body">
            <strong>Step Title</strong>
            <p>Step description.</p>
        </div>
    </div>
</div>
```

### Tables

```html
<table>
    <thead><tr><th>Column</th><th>Column</th></tr></thead>
    <tbody>
        <tr><td>Value</td><td>Value</td></tr>
    </tbody>
</table>
```

Blue header (`#0078d4`, white text), alternating row striping, hover highlight.

### Inline Links

Use `target="_blank"` for all external links. Add a direct `.big-link` button for primary CTAs:

```html
<a class="big-link" href="https://..." target="_blank">Open Portal →</a>
```

`.big-link`: blue button, white text, `padding: 10px 20px`, `border-radius: 4px`.

### Tone

Follow the same voice as the rest of the project:
- **Direct and practical** — write for someone who needs to act, not read
- **Specific** — use real names, real URLs, real resource names
- **Structured for scanning** — tables, numbered lists, code blocks over prose
- **No corporate filler** — never write "In order to facilitate" or "This document aims to"
- **Short sentences for emphasis** — one idea per sentence when it matters

### Footer

Always include:
```html
<footer>
    <p>Document Title · <ORG_NAME> Infrastructure · Month Year</p>
</footer>
```

---

## Workflows

### A. Create a New Document

#### Step 1 — Gather Information

Collect what you need before writing:
1. **Document title** — what the document is called
2. **Topic/content** — what it covers; source material (Confluence page, issue key, transcript, description)
3. **Audience** — who will read it (e.g., business analyst, engineer, end user)
4. **Document type** — how-to guide, reference doc, architecture deep-dive, proposal, etc.

If the user provides enough context, skip asking.

#### Step 2 — Create the File

Create the HTML file in `sharepoint/`:

```bash
touch sharepoint/{kebab-case-title}.html
```

Name it clearly: `pim-activation-guide.html`, `fabric-workspace-onboarding.html`, `azure-dns-reference.html`.

#### Step 3 — Author the HTML

Write the full document. Guidelines:
- Start with `<!DOCTYPE html>` and the full `<style>` block
- Use the standard structure: `h1` → executive-summary → toc → numbered h2 sections → footer
- Include the full CSS component library inline — never link external stylesheets
- Use step cards for how-to guides, comparison grids for options, metric cards for KPIs
- All external links use `target="_blank"`
- Real URLs, real names, real resource identifiers throughout

For **end-user guides** (how-tos): prioritize step cards, warning/success boxes, big-link buttons for primary actions.

For **technical reference docs**: prioritize tables, code blocks, and comparison grids.

For **architecture docs / deep-dives**: use flow diagrams, phase cards, metric cards, and comparison grids.

#### Step 4 — Editorial Review

Three-pass review before publishing:
1. **Developmental** — is the structure right? Does the opening tell you what this is for? Are sections in the right order?
2. **Line edit** — active voice, cut filler, tighten every sentence
3. **Copy edit** — grammar, punctuation, consistent formatting, broken links

Apply fixes directly.

#### Step 5 — Publish

**Run this from your local WSL or Windows terminal** (the <ORG_NAME> SharePoint tenant IP allowlist blocks cloud agent IPs):

```bash
cd /home/wweeks/git/projects
python3 scripts/upload_to_sharepoint.py sharepoint/{filename}.html
```

This uploads via the Microsoft Graph API using your current `az` session. Run `az login` first if needed.

To publish to a subfolder other than `docs`:
```bash
python3 scripts/upload_to_sharepoint.py sharepoint/{filename}.html --folder docs/guides
```

Dry run to verify path without uploading:
```bash
python3 scripts/upload_to_sharepoint.py sharepoint/{filename}.html --dry-run
```

The Copilot agent commits the file to git — you run the upload locally after it pushes.

#### Step 6 — Confirm

Tell the user:
- File name and SharePoint URL
- Browse link: `https://<org_short>fg.sharepoint.com/sites/Infrastructure/Files/Forms/AllItems.aspx?id=%2Fsites%2FInfrastructure%2FFiles%2Fdocs&viewid=<RESOURCE_GUID>`
- Commit the file to the repo

---

### B. Update an Existing Document

1. Find the file in `sharepoint/` by name
2. Edit the HTML directly
3. Re-upload:
   ```bash
   python3 scripts/upload_to_sharepoint.py sharepoint/{filename}.html
   ```
   Uploading with the same filename **overwrites** the SharePoint version.
4. Commit the updated file.

---

### C. Convert a Confluence Page to SharePoint HTML

Use this when the user wants both a Confluence version and a SharePoint version:

1. Read the existing Confluence markdown from `confluence/{pageId}-{Title}.md`
2. Convert content to HTML using the standard style — same structure, adapted to HTML components
3. Save as `sharepoint/{kebab-title}.html`
4. Upload and commit

Cross-link the two versions in their respective files.

---

## Scripts Reference

| Script | Purpose |
|---|---|
| `scripts/upload_to_sharepoint.py` | Upload HTML file to SharePoint Infrastructure/Files/docs |

### upload_to_sharepoint.py Flags

| Flag | Default | Description |
|---|---|---|
| `file` | required | Path to the HTML file |
| `--folder` | `docs` | Target folder inside the Files library |
| `--dry-run` | off | Show what would happen without uploading |

---

## Important Notes

- **Run upload from your local machine** — the <ORG_NAME> SharePoint tenant has an IP allowlist that blocks cloud agent IPs. `upload_to_sharepoint.py` must be run from your WSL terminal or Windows PowerShell, not from the Copilot agent. The agent writes the file and commits it; you run the upload.
- Auth uses the current `az` CLI session (SharePoint resource token). Run `az login` if you see auth errors.
- Uploading the same filename to the same folder **replaces** the previous version — there's no versioning prompt.
- The SharePoint "Files" library is distinct from the default "Documents" library — the script targets it specifically by drive name.
- Always commit the `sharepoint/` file to the repo after publishing so the source of truth is in git.
- HTML must be fully self-contained — no external CSS, fonts, or images. SharePoint renders it as a static file.

---

## Document Registry

Track published SharePoint documents here. Update when you add a new one.

| Filename | Title | Published |
|---|---|---|
| `pim-activation-guide.html` | How to Activate Your Fabric Workspace Access (PIM) | 2026-05-27 |
