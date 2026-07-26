---
LINEAR: ACE-65
title: Ace — Storage and managed identity integration
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

WORKLOG: Identified the storage and identity integration points that depend on the backend project shape and Azure resources.

## Follow-up

Status: Blocked
TODO:
- [ ] Confirm the storage account/container names and whether queue storage is actually required.
- [ ] Confirm the identity strategy for local development and production.
