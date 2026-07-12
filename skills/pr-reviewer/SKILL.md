---
name: pr-reviewer
description: 'Review GitHub pull requests with an automated checklist. Pulls diff, checks CI, scans for secrets, validates size, and generates findings. Use when the user says "review PR", "check my PRs", "is this PR ready", or wants to run a code review.'
argument-hint: 'Specify a PR number (e.g., 25) and optionally a repo (owner/repo) or Linear key for issue linkage'
---

# PR Reviewer Skill

## Role

This skill is a thin collar over the GitHub PR review command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- github review-pr --help`

## Operating Contract

1. Route user intent to the `github review-pr` command.
2. Keep diff analysis, CI check, secret scanning, and findings logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
