---
name: end-my-day
description: 'Close the work day: stop timers, generate standup summary, commit and push worklogs, post to Teams. Use when the user says "end my day", "close out", "wrap up", "send standup", or "EOD".'
argument-hint: 'Say "end my day" to begin the shutdown sequence'
---

# End My Day Skill

## Role

This skill is a thin collar over the daily shutdown command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- planner end-my-day --help`
- `dotnet run --project src/Ace.Tools.Cli -- planner daily-note --help`

## Operating Contract

1. Route user intent to the `planner end-my-day` command.
2. Keep standup generation, Teams post, timer-stop, and worklog-commit logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
