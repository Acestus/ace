---
name: pr-daily-summary
description: 'Generate a daily pull request summary for standup. Fetches yesterday''s merged and opened PRs across the <GITHUB_ORG> org, formats a readable summary, and publishes to Notion. Use when the user says "PR summary", "yesterday''s PRs", "daily PR report", "standup PRs", or "what got merged yesterday?"'
argument-hint: 'Optionally specify a date (YYYY-MM-DD) or say "publish" to push to Notion'
---

# PR Daily Summary Skill

## Role

This skill is a thin collar over the GitHub daily summary command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- github daily-summary --help`

## Operating Contract

1. Route user intent to the `github daily-summary` command.
2. Keep PR fetch, formatting, and Notion publish logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
