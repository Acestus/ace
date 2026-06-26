---
name: weekly-summary
description: 'Generate a weekly status report or brag document. Pulls flow:done tickets from Linear, calculates hours by swimlane from planner org files, and drafts a markdown summary. Use when the user says "weekly summary", "brag doc", "what did I do this week", "weekly status", or "sprint summary".'
argument-hint: 'Optionally specify a week start date (YYYY-MM-DD) or output format (report/markdown)'
---

# Weekly Summary Skill

## Role

This skill is a thin collar over the weekly summary command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- planner weekly-summary --help`

## Operating Contract

1. Route user intent to the `planner weekly-summary` command.
2. Keep Linear query, hour calculation, and markdown generation logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
