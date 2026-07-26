---
title: Ace Operating Guide
date: 2026-07-19
description: How to edit, review, and ship content in Ace.
draft: false
---

## Daily loop

1. Edit Markdown in Neovim.
2. Commit the change in Git.
3. Push to GitHub.
4. Let the deployment pipeline publish the updated site.

## What goes where

- `content/` holds the pages.
- `archetypes/` holds the page starters.
- `assets/plantuml/` holds `.puml` source files.
- `static/diagrams/` holds rendered diagram output.
- `web/` holds the browser bundle and TypeScript code.

## Working with agents

When an agent writes a page, ask it to be exact about resource names, commands, and follow-up work. If the page needs a diagram or table, include it instead of explaining it in prose.
