---
applyTo: '**/*.html'
---

# HTML Document Style Guide

## Purpose

When creating HTML documents (deep-dives, architecture docs, implementation plans, proposals), follow this style. These are polished, standalone pages designed to look good in a browser, in Notion Live Docs (paste the rendered HTML), and when printed.

## Visual Identity

- **Font:** Segoe UI → Tahoma → Geneva → Verdana → sans-serif
- **Body:** `max-width: 1200px`, centered, `#faf9f8` background, `#323130` text, `line-height: 1.6`
- **Primary accent:** `#0078d4` (Azure blue)
- **Secondary heading:** `#106ebe`
- **Muted text:** `#605e5c`

## Typography

- `h1` — Blue (`#0078d4`) with a `3px solid #0078d4` bottom border
- `h2` — Blue (`#106ebe`) with a `4px solid #0078d4` left border and `15px` left padding
- `h3` — Default text color (`#323130`)
- `h4` — Muted (`#605e5c`)

## Component Library

Use these CSS classes. All styles are inline in a single `<style>` block in `<head>` — no external stylesheets.

### Executive Summary

```html
<div class="executive-summary">
    <strong>Purpose:</strong> ...
    <br><br>
    <strong>Audience:</strong> ...
</div>
```

Light blue background (`#e1f5fe`), 5px blue left border, rounded corners.

### Callout Boxes

| Class | Background | Border | Use for |
|-------|-----------|--------|---------|
| `.principle-box` | `#f3f2f1` | `1px solid #d2d0ce` | Key principles, definitions, important context |
| `.highlight-box` | `#fff4e6` | `1px solid #ffcc80` | Warnings-lite, things to note |
| `.warning-box` | `#ffebee` | `1px solid #f48fb1` | Risks, danger, things that are broken |
| `.success-box` | `#e8f5e8` | `1px solid #81c784` | Positive outcomes, confirmations |

### Metric Cards

```html
<div class="metric-row">
    <div class="metric-card">
        <div class="number">2,000+</div>
        <div class="label">Description text</div>
    </div>
</div>
```

Flex row of cards with bottom border accent. Add `.green`, `.orange`, or `.red` class to change the accent color.

### Phase Cards

```html
<div class="phase-container">
    <div class="phase-card phase-1">
        <h3>Phase title</h3>
        <p>Description</p>
    </div>
</div>
```

White cards with colored top border. Use `.phase-1` (green), `.phase-2` (orange), `.phase-3` (purple), `.phase-4` (red).

### Comparison Grid

```html
<div class="comparison-grid">
    <div class="comparison-card dead-end">
        <h3>❌ Bad option</h3>
        <ul>...</ul>
    </div>
    <div class="comparison-card target">
        <h3>✅ Good option</h3>
        <ul>...</ul>
    </div>
</div>
```

Two-column grid. `.dead-end` = red top border. `.target` = green top border.

### Flow Diagrams

```html
<div class="flow-diagram">
    <span class="flow-step">Step 1</span>
    <span class="flow-arrow">→</span>
    <span class="flow-step">Step 2</span>
</div>
```

Centered white box with border. Steps are blue rounded pills. Add `.green`, `.orange`, `.purple`, `.red`, `.gray` to flow-steps.

### Tables

Standard HTML tables with blue header row (`th` background `#0078d4`, white text), alternating row striping, hover highlight, and subtle box shadow.

### Code Blocks

```html
<div class="code-block">yaml or code content here</div>
```

Dark background (`#1e1e1e`), light text (`#d4d4d4`), monospace font, `white-space: pre`. Use inline `<span>` tags with VS Code theme colors for syntax highlighting:
- Keywords/keys: `#569cd6`
- Strings: `#ce9178`
- Comments: `#6a9955`

### Inline Code

```html
<span class="inline-code">some-command</span>
```

Light gray background, blue monospace text.

### Badges

```html
<span class="badge badge-free">Free</span>
```

Small rounded pills. Define badge colors as needed (e.g., `.badge-free` green, `.badge-included` blue).

### Todo Items (numbered)

```html
<div class="todo-item">
    <div class="todo-number">1</div>
    <div class="todo-text">
        <strong>Title</strong>
        <span>Description</span>
    </div>
</div>
```

White card with numbered circle and two-line layout (bold title, muted description).

## Table of Contents

Every document with 5+ sections should include a TOC near the top:

```html
<div class="toc">
    <h3>Contents</h3>
    <ol>
        <li><a href="#section-id">Section Name</a></li>
    </ol>
</div>
```

## Document Structure

1. `<h1>` title with em-dash separator (e.g., "Plan Title — repo-name")
2. Executive summary box (Purpose, Audience/Context, Key Message)
3. Table of contents
4. Numbered `<h2>` sections with `id` attributes for anchor links
5. Footer with document name and date

## Footer

```html
<div style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #d2d0ce; color: #a19f9d; font-size: 12px;">
    <p>Document Title — Prepared Month Year</p>
</div>
```

## Responsive

Include a media query for mobile (`max-width: 768px`) that collapses grid/flex layouts to single-column.

## Self-Contained

Every HTML file must be completely self-contained:
- All CSS in a single `<style>` block in `<head>`
- No external stylesheets, no JavaScript, no images
- Should render identically when opened as a local file or pasted into Notion
