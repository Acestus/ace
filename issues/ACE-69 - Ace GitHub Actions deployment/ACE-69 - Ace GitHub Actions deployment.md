---
LINEAR: ACE-69
title: Ace — GitHub Actions deployment
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Deploy every `main` commit to the dev environment.

Deliverables: build and deploy workflow, pinned tool versions, PlantUML build, Bun build, Hugo build, .NET build and tests, Azure deployment integration, and smoke checks.

Acceptance: a commit to `main` deploys the static site and API, failures in diagrams/TypeScript/Hugo/.NET block deployment, credentials do not appear in logs, the deployed site requires authentication, the health endpoint passes after deployment, and Git history identifies every deployed revision.

## Actions

### 2026-07-19

WORKLOG: Confirmed the deployment workflow still needs the Azure credentials, environment targets, and smoke-check contract.

## Follow-up

Status: Blocked
TODO:
- [ ] Provide the deployment target(s) and the Azure credentials or federated auth setup.
- [ ] Confirm whether the pipeline should deploy one site or both site roots.
