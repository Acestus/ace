---
LINEAR: ACE-37
title: Daily Gospel Reading — GitHub Copilot CLI Plugin (Experiment)
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: 
created: 2026-07-03
---

## Description

## User Story

# User Story: Daily Gospel Reading — GitHub Copilot CLI Plugin (Experiment)

**As a** GitHub Copilot CLI user (myself),
**I want** a Copilot CLI plugin that fetches today's Gospel reading from
[USCCB.org](<http://USCCB.org>) and prints it in the terminal, backed by its own dedicated Azure
Function,
**so that** I can learn what it actually takes to build and publish a plugin
to Copilot CLI's marketplace system, in parallel to the Claude Code skill
experiment (ACE-35) and the OpenClaw skill experiment (ACE-36).

## Acceptance Criteria

- [ ] A dedicated Azure Function (independent of ACE-34/35/36's backends,
      even if the scraping approach is similar) exposes an endpoint that
      returns today's Gospel reading — citation + full text — parsed from
      [USCCB.org](<http://USCCB.org>).
- [ ] The endpoint returns a clear error response if the page can't be
      parsed, rather than an unhandled failure.
- [ ] A GitHub Copilot CLI plugin (its own plugin directory + a
      `marketplace.json`, per GitHub's plugin marketplace format) calls this
      endpoint when invoked and prints the Gospel citation and text in the
      terminal.
- [ ] If the backend call fails, the plugin prints a plain, clear error
      message — no offline cache or fallback content required (this is an
      experiment, not a daily-use tool).
- [ ] Invoking the plugin in Copilot CLI shows the real, correct Gospel
      reading for the current date.
- [ ] The plugin is installable via `copilot plugin marketplace add     <owner>/<repo>` per GitHub's documented plugin marketplace flow.
- [ ] Source lives in a new, separate GitHub repo:
      `catholic-daily-copilot-plugin`.

## Out of Scope

* First/second reading, responsorial psalm — Gospel only for this
  experiment.
* Any reuse of or dependency on ACE-34/35/36's backends.
* Offline caching, scheduling, notifications, or any daily-use polish.
* Any Android/iOS/Claude-skill/OpenClaw work (ACE-33/34/35/36, unrelated to
  this ticket).

## Implementation Plan

# Implementation Plan: Daily Gospel Reading — GitHub Copilot CLI Plugin (Experiment)

Pattern: thin new project (new repo, new Azure resource, new Copilot CLI
plugin) — fully independent of the `ace` repo and of ACE-34/35/36's backends.
Nothing in any of those is touched or reused.

1. **Create the repo**
   * New GitHub repo `catholic-daily-copilot-plugin`.
   * Two parts: `backend/` (Azure Function) and a plugin directory
     (e.g. `plugins/gospel-reading/`) containing the plugin's own manifest
     and script, per GitHub's Copilot CLI plugin format.
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
3. **Copilot CLI plugin: directory and marketplace.json**
   * Follow GitHub's plugin-creation docs to scaffold the plugin directory.
   * Add a `.github/plugin/marketplace.json` (or `.claude-plugin/`,
     whichever applies) listing this plugin with name, description,
     version, and `source` path.
   * Write the plugin so that when invoked, it calls the Function endpoint
     and prints the Gospel citation + text in the terminal.
   * On a failed backend call, the plugin prints a plain error message —
     no retry, cache, or fallback logic.
4. **End-to-end verification**
   * Install the plugin locally (`copilot plugin marketplace add <owner>/catholic-daily-copilot-plugin`) and confirm invoking it prints
     the real, correct Gospel reading for the current date.
5. **Publish/share**
   * Confirm the repo is publicly installable via the documented
     `copilot plugin marketplace add` flow as the final proof of "done."
6. **Explicitly deferred**
   * Full daily readings (first/second reading, psalm) — Gospel only.
   * Any dependency on or reuse of ACE-34/35/36's backends.
   * Offline caching, scheduling, or daily-use robustness.

## Actions

### 2026-07-03

WORKLOG: Stub created from Linear ACE-37

## Follow-up

Status: Backlog
TODO:
- [ ] Review and scope work