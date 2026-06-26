---
name: start-my-day
description: 'Create today''s daily planning note, load active tickets from Linear, and present the day''s board. Use when the user says "start my day", "morning setup", "create today''s note", or "what am I working on today?"'
argument-hint: 'Say "start my day" to create the daily note and load the board'
---

# Start My Day Skill

## Role

This skill is a thin collar over the daily morning setup command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- planner start-my-day --help`
- `dotnet run --project src/Ace.Tools.Cli -- planner daily-note --help`

## Operating Contract

1. Route user intent to the `planner start-my-day` command.
2. Keep daily-note creation, Linear board load, and planning logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
