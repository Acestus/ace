---
LINEAR: ACE-49
title: Journal — .NET 10 Azure Functions baseline
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

WORKLOG: Stub created from Linear ACE-49

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work