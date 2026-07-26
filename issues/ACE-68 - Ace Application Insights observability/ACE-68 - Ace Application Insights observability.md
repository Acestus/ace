---
LINEAR: ACE-68
title: Ace — Application Insights observability
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-19
---

## Description

Provide useful operational visibility without leaking private content.

Deliverables: Application Insights integration, structured logging conventions, correlation middleware/helper, sample KQL queries, failure/dependency logging, and data-redaction guidance.

Acceptance: requests, failures, and dependencies appear in Application Insights; logs can correlate a front-end API request with Function execution; logs exclude tokens, secrets, transcripts, and private note bodies; and the documentation includes queries for failures, slow requests, and dependency errors.

## Actions

### 2026-07-19

WORKLOG: Scoped the observability work and identified the remaining telemetry target and redaction-policy inputs.

## Follow-up

Status: Blocked
TODO:
- [ ] Provide the Application Insights and Log Analytics resource targets.
- [ ] Confirm the redaction policy for private notes, transcripts, and secrets.
