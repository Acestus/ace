---
LINEAR: ACE-50
title: Journal — Storage and managed identity integration
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Allow Functions to access Blob and Queue Storage without account keys.

Deliverables: managed-identity usage, blob client abstraction, optional queue abstraction, RBAC documentation, local-development credential instructions, and tests using mocks or an emulator where appropriate.

Acceptance: production config requires no storage account key, the Function App system-assigned identity has least-privilege assignments, a sample blob can be read through the service abstraction, queue infra is not deployed unless used, and access failures produce structured telemetry.

## Actions

### 2026-07-19

WORKLOG: Stub created from Linear ACE-50

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work