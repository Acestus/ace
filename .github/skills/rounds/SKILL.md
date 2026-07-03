---
name: rounds
description: 'Orchestrate the work session as a kanban station rotation. Each rounds instance owns one lane (1–5) and works one ticket at a time — any lane can work any Linear ticket. Run up to 5 tabs → full parallel coverage. Use when the user says "start rounds", "do rounds", "start rounds 1/2/3/4/5", "next ticket", or "done/waiting/blocked" on a ticket.'
argument-hint: 'start rounds [1|2|3|4|5] — each tab claims one lane. Lanes are interchangeable. Say "done", "waiting", "blocked", or "park" to transition.'
---

# Rounds Skill

## Role

This skill is a thin collar over the rounds command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- rounds start --help`
- `dotnet run --project src/Ace.Tools.Cli -- rounds transition --help`
- `dotnet run --project src/Ace.Tools.Cli -- rounds clear-lane --help`

## Operating Contract

1. Keep lane-claim, dispatch, and transition logic in the CLI.
2. Use this file to route intent only.
3. Defer command detail and examples to CLI `--help`.
4. Keep this skill short and maintainable (<200 lines).
