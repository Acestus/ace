---
name: waiting-ticket-followup
description: 'Scan flow:waiting Linear tickets, group by stakeholder, show stale time, and draft follow-up messages. Use when the user says "follow up on waiting tickets", "who am I waiting on", "check stale tickets", or "draft follow-ups".'
argument-hint: 'Optionally specify a stakeholder name or stale-days threshold'
---

# Waiting Ticket Follow-up Skill

## Role

This skill is a thin collar over the Linear follow-up command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- linear followup --help`

## Operating Contract

1. Route user intent to the `linear followup` command.
2. Keep staleness calculation, stakeholder grouping, and nudge-draft logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
