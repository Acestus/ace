---
LINEAR: ACE-64
title: Ace — .NET 10 Azure Functions baseline
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Create the optional dynamic backend.

Deliverables: .NET 10 isolated Function App, health endpoint, authenticated-principal parser, identity diagnostic endpoint, structured error handling, and unit tests.

Acceptance: the project builds and tests under .NET 10, `/api/health` returns a safe health response, protected endpoints reject requests without an authenticated principal, the principal parser handles malformed input safely, and logs include correlation IDs without secrets.

## Actions

### 2026-07-19

WORKLOG: Reviewed the repo layout and confirmed there is not yet a dedicated Functions project for Ace.

## Follow-up

Status: Blocked
TODO:
- [ ] Decide whether this backend should be a new standalone Functions project or extend `Ace.Crm.Api`.
- [ ] Confirm the project name and folder placement before scaffolding.
