---
notion_id: 370202bafe718186b473c638160a870b
title: Test Page — sync pipeline verified
parent:
---

## Overview

This page is managed as markdown source of truth in `notion/test-page.md`.
Edits committed to main are automatically pushed to Notion via the sync-notion CI workflow.

## How it works

- Edit `notion/test-page.md` locally
- Commit and push to main
- `sync-notion.yaml` triggers, runs `scripts/notion_sync.py`
- Page content is replaced in Notion with the current markdown

## Notes

- Source: `notion/test-page.md` in the workflow-toolkit repo
- Linked to Linear issue [ACE-5](https://linear.app/acestus/issue/ACE-5/test-ticket)
- Pipeline verified: 2026-05-29
