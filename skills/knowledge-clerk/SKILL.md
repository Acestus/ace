---
name: knowledge-clerk
description: 'Knowledge retrieval for <ORG_NAME> infrastructure work. Finds the right process, architecture, precedent, or vendor doc before you build or decide anything. Use when you need to know how something was done before, what the right pattern is, or whether documentation exists. Referenced by the rounds skill before every ticket.'
argument-hint: 'Ask a question or name a topic — "how do we handle UMI permissions", "Five9 call script auth pattern", "Fabric lakehouse naming", "networking spoke config"'
---

# Knowledge Clerk Skill

## Role

This skill is a thin collar over the clerk knowledge-retrieval command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- clerk --help`
- `dotnet run --project src/Ace.Tools.Cli -- clerk search --help`

## Operating Contract

1. Route user knowledge queries to the `clerk` command group.
2. Keep search, ranking, and catalog-sync logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
