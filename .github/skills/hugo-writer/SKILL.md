---
name: hugo-writer
description: 'Create and update Hugo Markdown content with optional PlantUML diagrams rendered by CI into static image assets. Use when the user says "write a Hugo page", "create a Hugo article", "add a markdown page", "make a blog post", or wants documentation for a Hugo static site.'
argument-hint: 'Describe the Hugo page, post, or documentation topic to create'
---

# Hugo Writer Skill

Create and update Hugo Markdown pages for the Ace static sites. Use for technical documentation, runbooks, blog posts, architecture notes, and knowledge-site pages that should live as Markdown in Git.

## When to Use

- User says "write a Hugo page", "create a Hugo article", "make a blog post", or "add a Markdown page"
- User wants content for `content/` or `sites/journal/content/`
- User wants a diagram-backed technical page for the static web app
- User wants documentation that should be reviewed, versioned, and published through GitHub Actions

## Workflow

### Step 1 - Choose the site root

Use the repo root for the Ace knowledge site:

```bash
cd ~/git/ace
```

Use `sites/journal/` only when the user explicitly asks for the Journal Hugo site.

### Step 2 - Choose the content path

- Ace site pages live under `content/`.
- Journal site pages live under `sites/journal/content/`.
- Technical pages usually belong under `content/technical/`.
- Planner or work-plan pages usually belong under `content/planner/`.
- Keep file names short, lowercase, and hyphenated.

### Step 3 - Draft Hugo Markdown

Start every page with TOML or YAML front matter matching the local pattern. Use the repo's existing pages as the closest template.

Basic shape:

```markdown
---
title: Example Technical Page
date: 2026-08-04
description: One sentence explaining the page.
draft: false
---

## Overview

Start with the direct answer: what this page covers and why it exists.
```

Writing rules:

- Open with the point, not throat-clearing.
- Use active voice.
- Name exact resources, repositories, services, commands, and paths.
- Make commands copy-pasteable.
- Use short sections, tables, and diagrams when they make the page easier to scan.
- Do not include secrets, tokens, private transcript bodies, or credentials.

### Step 4 - Add PlantUML when a diagram helps

Use PlantUML for workflows, boundaries, dependencies, infrastructure, and sequence diagrams.

Source convention:

- Put diagram source in `assets/plantuml/<page-slug>.puml`.
- For Journal, put source in `sites/journal/assets/plantuml/<page-slug>.puml`.
- Name the `.puml` file after the Markdown page slug unless there is more than one diagram.

Rendered asset convention:

- CI renders changed `.puml` files with Java/PlantUML into PNG assets.
- Ace rendered PNGs are expected at `static/diagrams/<page-slug>.png`.
- Journal rendered PNGs are expected at `sites/journal/static/diagrams/<page-slug>.png`.
- Do not hand-edit rendered diagram files unless the user explicitly asks; change the `.puml` source instead.

Reference diagrams from Markdown with the Hugo diagram shortcode:

```markdown
{{< diagram src="/diagrams/example-technical-page.png" alt="Example technical page flow" caption="Request flow for the example system." >}}
```

If the current repo still renders SVG, follow the local shortcode and generated-file policy already in the repo, then call out the mismatch so the PlantUML CI can be updated to PNG.

### Step 5 - Verify locally

Run the narrowest useful check:

```bash
./scripts/build-site.sh
```

For Journal:

```bash
hugo --source sites/journal
```

Report the created Markdown path, any PlantUML source path, and the expected rendered diagram path.

## Publishing Notes

- Hugo content is published by committing Markdown, PlantUML source, and any required static assets.
- GitHub Actions should install Java, run PlantUML for updated `.puml` files, create PNGs under the static diagram path, then build the Hugo static web app.
- Keep generated diagram paths stable so old links do not break.
