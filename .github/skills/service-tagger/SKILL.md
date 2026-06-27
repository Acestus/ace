---
name: service-tagger
description: "Apply and normalize service tags/labels across issues and pull requests so routing, ownership, and reporting stay consistent."
argument-hint: "Provide scope (issue/pr/repo), target item, and the service tags to apply."
---

# Service Tagger Skill

## Role

This skill is a thin collar for service-tag governance across GitHub issues and pull requests.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- github issues --help`
- `dotnet run --project src/Ace.Tools.Cli -- github prs --help`
- `gh label list`
- `gh issue edit <number> --add-label <service-tag>`
- `gh pr edit <number> --add-label <service-tag>`

## Operating Contract

1. Treat labels as service taxonomy (e.g., service:web, service:cli, service:infra).
2. Apply missing service tags and remove conflicting ones when requested.
3. Keep enforcement lightweight; do not block work for taxonomy drift alone.
4. Keep this skill short and maintainable (<200 lines).
