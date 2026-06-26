---
name: azure-investigator
description: 'Investigate Azure resources, managed identities, role assignments, and access patterns. Use when the user asks about Azure permissions, RBAC, resource inventory, identity investigation, or access debugging. Wraps az CLI with higher-level investigation commands.'
argument-hint: 'Specify what to investigate: an identity name, resource group, or access scope'
---

# Azure Investigator Skill

## Role

This skill is a thin collar over the Azure investigation command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- azure --help`
- `dotnet run --project src/Ace.Tools.Cli -- azure investigate --help`
- `dotnet run --project src/Ace.Tools.Cli -- azure resource --help`
- `dotnet run --project src/Ace.Tools.Cli -- azure pim --help`

## Operating Contract

1. Route user intent to the `azure` command group.
2. Keep RBAC, identity, and resource investigation logic in the CLI.
3. Use `--help` for command examples and flag details.
4. Keep this skill short and maintainable (<200 lines).
