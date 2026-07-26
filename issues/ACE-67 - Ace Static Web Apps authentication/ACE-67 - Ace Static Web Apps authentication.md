---
LINEAR: ACE-67
title: Ace — Static Web Apps authentication
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Make the entire Ace website private to the owner.

Deliverables: `staticwebapp.config.json`, Entra configuration documentation, route rules for `/*` and `/api/*`, sign-in and sign-out links, unauthorized redirect behavior, and owner-assignment instructions.

Acceptance: anonymous requests cannot read any Ace page, anonymous API requests fail, the owner can sign in using Entra ID, unused providers are disabled or inaccessible, the client principal reaches the Function API, and authentication behavior is documented for local development.

## Actions

### 2026-07-19

WORKLOG: Scoped the private-site auth flow and confirmed the Entra app details are still missing.

## Follow-up

Status: Blocked
TODO:
- [ ] Provide the Entra tenant/app registration details needed for the SWA auth config.
- [ ] Confirm the owner-assignment and provider restrictions for the site.
