---
name: lorcana
description: 'Scrape a Lorcana card list from lorcanaplayer.com and produce a plain-text copy-paste file (names, rarity, ink color) in assets/lorcana/. Use when the user says "scrape lorcana", "generate lorcana list", or gives you a lorcanaplayer.com URL for a new set.'
argument-hint: 'Set name (e.g. wilds-unknown) or full lorcanaplayer.com URL'
---

# Lorcana Skill

## Role

This skill is a thin collar over the Lorcana scrape command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- lorcana --help`
- `dotnet run --project src/Ace.Tools.Cli -- lorcana scrape --help`

## Operating Contract

1. Route user intent to the `lorcana` command group.
2. Keep scraping, card list formatting, and file-write logic in the CLI.
3. Use `--help` for full syntax and examples.
4. Keep this skill short and maintainable (<200 lines).
