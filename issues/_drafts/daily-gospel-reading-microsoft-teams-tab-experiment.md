---
title: Daily Gospel Reading — Microsoft Teams Tab (Experiment)
created: 2026-07-03
status: draft
---

## User Story

# User Story: Daily Gospel Reading — Microsoft Teams Tab (Experiment)

**As a** Microsoft Teams user (myself),
**I want** a Teams personal tab that shows today's Gospel reading from
USCCB.org, backed by its own dedicated Azure Function,
**so that** I can learn what it actually takes to build and publish a Teams
app to Microsoft AppSource/Marketplace, in parallel to the Claude Code skill
(ACE-35), OpenClaw skill (ACE-36), and Copilot CLI plugin (ACE-37)
experiments.

## Acceptance Criteria

- [ ] A dedicated Azure Function (independent of ACE-34/35/36/37's backends,
      even if the scraping approach is similar) exposes an endpoint that
      returns today's Gospel reading — citation + full text — parsed from
      USCCB.org.
- [ ] The endpoint returns a clear error response if the page can't be
      parsed, rather than an unhandled failure.
- [ ] A Microsoft Teams app (manifest + a personal tab) calls this endpoint
      on load and displays the Gospel citation and text.
- [ ] If the backend call fails, the tab shows a plain, clear error message
      — no offline cache or fallback content required (this is an
      experiment, not a daily-use tool).
- [ ] Sideloading the app into Teams and opening the tab shows the real,
      correct Gospel reading for the current date.
- [ ] The app is submitted to Microsoft AppSource/Marketplace per Microsoft's
      documented submission process.
- [ ] Source lives in a new, separate GitHub repo: `catholic-daily-teams-app`.

## Out of Scope

- First/second reading, responsorial psalm — Gospel only for this
  experiment.
- Any reuse of or dependency on ACE-34/35/36/37's backends.
- Any Teams app surface other than a personal tab (bots, message
  extensions, etc.).
- Offline caching, scheduling, notifications, or any daily-use polish.
- Any Android/iOS/Claude-skill/OpenClaw/Copilot-plugin work
  (ACE-33/34/35/36/37, unrelated to this ticket).

## Implementation Plan

# Implementation Plan: Daily Gospel Reading — Microsoft Teams Tab (Experiment)

Pattern: thin new project (new repo, new Azure resource, new Teams app) —
fully independent of the `ace` repo and of ACE-34/35/36/37's backends.
Nothing in any of those is touched or reused.

1. **Create the repo**
   - New GitHub repo `catholic-daily-teams-app`.
   - Two parts: `backend/` (Azure Function) and `teams-app/` (Teams app
     manifest, icons, and the personal tab's web content).

2. **Backend: Gospel-only scraper/parser (Azure Function)**
   - HTTP-triggered function, e.g. `GET /api/gospel?date=YYYY-MM-DD`
     (defaults to today).
   - Fetch USCCB's daily readings page for the given date, parse out just
     the Gospel section (citation + full text).
   - Return 200 with `{ date, citation, text }` on success; return a
     distinct error shape (e.g. 502 `{ error: "parse_failed" }`) if parsing
     fails.
   - Deploy via GitHub Actions with OIDC auth (consistent with this user's
     existing Azure conventions) — Consumption plan is enough for a
     single-user experiment.

3. **Teams app: manifest and personal tab**
   - Scaffold a Teams app manifest (`manifest.json`) defining a single
     personal tab, per Microsoft's Teams app documentation.
   - Build the tab as a simple static web page (hosted via Azure Static Web
     App or similar) that calls the Function endpoint on load and renders
     the Gospel citation + text.
   - On a failed backend call, the tab renders a plain error message.

4. **Sideload and verify**
   - Sideload the app into Teams (developer/personal sideloading) and
     confirm opening the tab shows the real, correct Gospel reading for the
     current date.

5. **Submit to AppSource/Marketplace**
   - Follow Microsoft's Partner Center submission process to submit the app
     to Microsoft AppSource/Marketplace.
   - Confirm submission is accepted/in review as the final proof of "done"
     (full approval may be outside this ticket's control/timeline, but
     submission itself is the completion signal).

6. **Explicitly deferred**
   - Full daily readings (first/second reading, psalm) — Gospel only.
   - Any dependency on or reuse of ACE-34/35/36/37's backends.
   - Bots, message extensions, or other Teams app surfaces.
   - Offline caching, scheduling, or daily-use robustness.