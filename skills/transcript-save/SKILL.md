---
name: transcript-save
description: 'Save Copilot chat transcript snippets (user prompts + assistant replies) into the matching Linear issue file Actions section by key or lane.'
argument-hint: 'Use "transcript save --lane N" to capture lane context into the currently claimed issue file.'
---

# Transcript Save Skill

## Role

Thin caller for transcript-to-issue persistence in `ace`.
SQLite-backed local databases are the source of truth for transcript and lane state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- transcript --help`
- `dotnet run --project src/Ace.Tools.Cli -- transcript sync --help`
- `dotnet run --project src/Ace.Tools.Cli -- transcript show-ticket --key ACE-22`
- `dotnet run --project src/Ace.Tools.Cli -- transcript save --lane 2`

## Operating Contract

1. Resolve target ticket from explicit `--key` or from lane claim in `~/.ace/rounds.db`.
2. Sync transcript turns from session store, then append compact USER/ASST excerpts to `issues/<KEY>/*`.
3. Persist only transcript context in `## Actions` (WORKLOG + COMMENT + excerpts).
4. Keep this skill short and maintainable.
