---
name: swa-deploy
description: 'Deploy, monitor, and debug Azure Static Web App (SWA) projects. Use when the user says "deploy the site", "check deploy status", "watch the Actions run", "why did the deploy fail", or "is fabric.acestus.com live". Wraps swa_deploy.py and swa_status.py.'
argument-hint: 'Specify repo or config path. Actions: deploy, status, watch-run RUN_ID, logs'
---

# SWA Deploy Skill

## Role

This skill is a thin collar over the SWA deployment and status command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- swa --help`
- `dotnet run --project src/Ace.Tools.Cli -- swa deploy --help`
- `dotnet run --project src/Ace.Tools.Cli -- swa status --help`

## Operating Contract

1. Route user intent to the `swa` command group.
2. Keep deploy, watch-run, DNS check, and status logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
