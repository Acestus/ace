---
LINEAR: ACE-35
title: Daily Gospel Reading — Claude Code Skill (Experiment)
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-03
---

## Description

## User Story

# User Story: Daily Gospel Reading — Claude Code Skill (Experiment)

**As a** Claude Code user (myself),
**I want** a Claude Code skill that fetches today's Gospel reading from
[USCCB.org](<http://USCCB.org>) and prints it in chat, backed by its own dedicated Azure Function,
**so that** I can learn what it actually takes to build and publish a skill
to a Claude Skills hub (e.g. [claudeskills.info](<http://claudeskills.info>)), separate from the ACE-33/34
mobile app work.

## Acceptance Criteria

- [ ] A dedicated Azure Function (independent of ACE-34's backend, even if
      the scraping approach is similar) exposes an endpoint that returns
      today's Gospel reading — citation + full text — parsed from
      [USCCB.org](<http://USCCB.org>).
- [ ] The endpoint returns a clear error response if the page can't be
      parsed, rather than an unhandled failure.
- [ ] A Claude Code skill (its own `SKILL.md` + any supporting script) calls
      this endpoint when invoked and prints the Gospel citation and text in
      the chat.
- [ ] If the backend call fails, the skill reports a plain, clear error
      message — no offline cache or fallback content required (this is an
      experiment, not a daily-use tool).
- [ ] Invoking the skill in Claude Code shows the real, correct Gospel
      reading for the current date.
- [ ] The skill is packaged and published so it can be downloaded from a
      Claude Skills hub (e.g. [claudeskills.info](<http://claudeskills.info>) or equivalent submission
      path).
- [ ] Source lives in a new, separate GitHub repo:
      `catholic-daily-claude-skill`.

## Out of Scope

* First/second reading, responsorial psalm — Gospel only for this
  experiment.
* Any reuse of or dependency on ACE-34's Azure backend.
* Offline caching, scheduling, notifications, or any daily-use polish.
* Any Android/iOS app work (that's ACE-33/34, unrelated to this ticket).

## Implementation Plan

# Implementation Plan: Daily Gospel Reading — Claude Code Skill (Experiment)

Pattern: thin new project (new repo, new Azure resource, new Claude skill) —
fully independent of the `ace` repo and of ACE-34's Android backend. Nothing
in either is touched or reused.

1. **Create the repo**
   * New GitHub repo `catholic-daily-claude-skill`.
   * Two parts: `backend/` (Azure Function) and `skill/` (Claude Code skill
     definition + supporting script).
2. **Backend: Gospel-only scraper/parser (Azure Function)**
   * HTTP-triggered function, e.g. `GET /api/gospel?date=YYYY-MM-DD`
     (defaults to today).
   * Fetch USCCB's daily readings page for the given date, parse out just
     the Gospel section (citation + full text).
   * Return 200 with `{ date, citation, text }` on success; return a
     distinct error shape (e.g. 502 `{ error: "parse_failed" }`) if parsing
     fails.
   * Deploy via GitHub Actions with OIDC auth (consistent with this user's
     existing Azure conventions) — Consumption plan is enough for a
     single-user experiment.
3. **Claude Code skill: definition and script**
   * Research the Claude Code skill format (SKILL.md-equivalent) and what
     [claudeskills.info](<http://claudeskills.info>) or the relevant hub expects for submission/packaging
     — this research step itself is part of the experiment.
   * Write the skill so that when invoked, it calls the Function endpoint
     and prints the Gospel citation + text in the chat.
   * On a failed backend call, the skill reports a plain error message —
     no retry, cache, or fallback logic.
4. **End-to-end verification**
   * Invoke the skill locally in Claude Code and confirm it prints the
     real, correct Gospel reading for the current date.
5. **Publish to the hub**
   * Package/submit the skill per whatever process [claudeskills.info](<http://claudeskills.info>) (or
     the chosen hub) requires, so it's downloadable by others.
   * Confirm it can actually be found/downloaded from the hub as the final
     proof of "done."
6. **Explicitly deferred**
   * Full daily readings (first/second reading, psalm) — Gospel only.
   * Any dependency on or reuse of ACE-34's backend.
   * Offline caching, scheduling, or daily-use robustness.

## Actions

### 2026-07-03

WORKLOG: Stub created from Linear ACE-35

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work