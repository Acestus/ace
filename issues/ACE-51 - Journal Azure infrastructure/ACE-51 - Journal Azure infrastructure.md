---
LINEAR: ACE-51
title: Journal — Azure infrastructure
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Provision Journal’s dev resources using repeatable infrastructure as code.

Deliverables: Bicep or the repository standard, Static Web App, Function App and hosting dependencies, Storage account and required containers, Application Insights, Log Analytics workspace where required, managed identity, RBAC assignments, and configuration settings.

Acceptance: a new dev environment can be deployed repeatably, names follow CAF-style conventions and service constraints, no secrets appear in source control, Function-to-Storage access uses managed identity, Application Insights receives Function telemetry, and outputs provide deployment identifiers needed by CI.

## Actions

### 2026-07-19

WORKLOG: Stub created from Linear ACE-51

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work