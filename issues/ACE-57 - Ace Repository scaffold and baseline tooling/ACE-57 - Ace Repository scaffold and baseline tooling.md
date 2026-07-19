---
LINEAR: ACE-57
title: Ace — Repository scaffold and baseline tooling
team: Acestus
state: Done
flow: done
urgency: 3
due: 
created: 2026-07-19
---

## Description

Create the Ace repository structure and baseline documentation.

Deliverables: Hugo project shell, content directories, API projects, TypeScript source directories, PlantUML directories, .gitignore, README, and tool-version documentation.

Acceptance: an empty but navigable Hugo site builds, the .NET solution builds, Bun installs from a committed lockfile, and the repository layout matches the documented boundaries.

## Investigation

- Confirmed the repo already has a green .NET solution and a static `web/wwwroot` deployment target.
- Confirmed the missing scaffold pieces are the Hugo source tree, a Bun/TypeScript workspace, PlantUML directories, and tool-version documentation.
- Confirmed local tooling is available for the scaffold: Hugo `v0.164.0+extended`, Bun `1.3.14`, and .NET SDK `10.0.301`.

## Actions

### 2026-07-19

WORKLOG: Built the Ace scaffold, added the Hugo site shell, created the Bun/TypeScript workspace, and verified the main build commands.
COMMENT: Created the Ace knowledge-site scaffold at the repo root with Hugo content directories, layouts, archetypes, PlantUML staging, and tool-version documentation. Added the Bun workspace under `web/`, pinned it with a committed lockfile, and added a typecheck baseline so the front-end workspace is no longer just a folder. Verified `hugo --source . --destination web/wwwroot`, `bun run typecheck`, and `dotnet build Ace.Tools.slnx` all succeed in this environment. The remaining warning is the pre-existing SQLite package advisory from the CLI project, which is outside the scope of this scaffold ticket.

WORKLOG: Investigated the existing repo boundaries and confirmed the ticket is a scaffold gap rather than a build break.
COMMENT: Verified the .NET solution already builds cleanly, then mapped the missing baseline pieces for Ace: the Hugo source tree, a Bun workspace with a committed lockfile, PlantUML directories, and explicit tool-version docs. The current static site shell lives in `web/wwwroot`, so the new Hugo source can publish there without disrupting the CRM app. Local Hugo and Bun tooling are available in this environment, which means the scaffold work can be verified immediately instead of being blocked on tool install.
WORKLOG: Stub created from Linear ACE-57

## Follow-up

Status: Done
