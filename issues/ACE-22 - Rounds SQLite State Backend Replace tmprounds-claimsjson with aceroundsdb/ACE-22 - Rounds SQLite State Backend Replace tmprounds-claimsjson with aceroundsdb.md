---
LINEAR: ACE-22
title: Rounds — SQLite State Backend — Replace /tmp/rounds-claims.json with ~/.ace/rounds.db
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: None
created: 2026-05-31
---

## Description

## Problem

/tmp/rounds-claims.json is fragile. Machine reboot = lost lane claims. No history, no queryability, no audit trail. The rounds system is a durable workflow engine backed by ephemeral state.

## Proposed Solution

Replace /tmp/rounds-claims.json with a local SQLite file at \~/.ace/rounds.db.

### Schema (minimal first step)

CREATE TABLE claims (
  lane      INTEGER PRIMARY KEY,
  key       TEXT NOT NULL,
  claimed_at TEXT NOT NULL,
  pid       INTEGER
);

CREATE TABLE worklogs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  session   TEXT,
  lane      INTEGER,
  key       TEXT,
  action    TEXT,
  note      TEXT,
  ts        TEXT DEFAULT (datetime('now'))
);

### Phase 1 — claims table only (one afternoon)

Replace all reads/writes of /tmp/rounds-claims.json with SQLite. Stale claim detection queries the DB instead of parsing JSON.

### Phase 2 — worklogs table

Every WORKLOG entry written to an issue file also appends to the worklogs table. Enables: SELECT \* FROM worklogs WHERE key = 'ACE-13' ORDER BY ts

### Phase 3 (optional) — Litestream to S3/Azure Blob

Stream \~/.ace/rounds.db offsite. Free durable backup of every rounds session.

## Acceptance Criteria

* rounds claims survive machine reboot
* lane state queryable via sqlite3 \~/.ace/rounds.db
* no change to issue file format or Notion integration
* backward-compatible: if rounds.db does not exist, create it fresh

## Actions

### 2026-05-31

WORKLOG: Stub created from Linear ACE-22

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work
