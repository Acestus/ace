---
name: aws-investigator
description: "Investigate AWS IAM users, roles, policies, CloudWatch access, and CloudTrail configuration. Use when the user asks about AWS permissions, who has access to what, or wants to verify/document IAM grants. Handles MFA login automatically. Account: 496800238012 (<ORG_NAME>)."
argument-hint: "Provide a question or target (e.g. 'check greg carlton permissions', 'list roles with CloudWatch access', 'verify <PROJECT>-384')"
---

# AWS Investigator Skill

## Role

This is a thin caller. Keep investigation logic in CLI commands.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- aws --help`
- `dotnet run --project src/Ace.Tools.Cli -- aws mfa-login --help`

## Operating Contract

1. Route user intent to the `aws` command group.
2. Do not implement IAM logic in this skill file.
3. Use CLI `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
