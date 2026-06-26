---
name: sharepoint-writer
description: 'Create and publish HTML documents to the <ORG_NAME> Infrastructure SharePoint docs library. Use when the user says "write a SharePoint doc", "publish to SharePoint", "create a guide for SharePoint", or wants to produce a polished HTML document for the Infrastructure Files/docs folder. Handles the full workflow: HTML authoring, editorial review, and upload.'
argument-hint: 'Describe the document topic, or provide a title and source material (transcripts, issue keys, technical domain)'
---

# SharePoint Writer Skill

## Role

This skill is a thin collar over the SharePoint document authoring and publishing command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- sharepoint --help`
- `dotnet run --project src/Ace.Tools.Cli -- sharepoint publish --help`

## Operating Contract

1. Route user intent to the `sharepoint` command group.
2. Keep HTML authoring, Graph API upload, and editorial-review logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
