---
title: Daily Gospel Reading — Google Cloud AI Agent (Experiment)
created: 2026-07-03
status: draft
---

## User Story

# User Story: Daily Gospel Reading — Google Cloud AI Agent (Experiment)

**As a** Gemini Enterprise / Google Cloud user (myself),
**I want** an A2A-compatible AI agent that returns today's Gospel reading
from USCCB.org, backed by its own dedicated Azure Function,
**so that** I can learn what it actually takes to build and publish an agent
to Google Cloud Marketplace's AI agent ecosystem, in parallel to the Claude
Code skill (ACE-35), OpenClaw skill (ACE-36), Copilot CLI plugin (ACE-37),
and GPT (ACE-38) experiments.

## Acceptance Criteria

- [ ] A dedicated Azure Function (independent of the other tickets'
      backends, even if the scraping approach is similar) exposes an
      endpoint that returns today's Gospel reading — citation + full text —
      parsed from USCCB.org.
- [ ] The endpoint returns a clear error response if the page can't be
      parsed, rather than an unhandled failure.
- [ ] A Google Cloud AI agent, built per Gemini Enterprise / A2A agent
      conventions, calls this endpoint when invoked and returns the Gospel
      citation and text.
- [ ] If the backend call fails, the agent returns a plain, clear error
      message — no offline cache or fallback content required (this is an
      experiment, not a daily-use tool).
- [ ] Invoking the agent (e.g. via Gemini Enterprise or a local A2A test
      harness) returns the real, correct Gospel reading for the current
      date.
- [ ] The agent is submitted/listed on Google Cloud Marketplace's AI agent
      ecosystem per Google's documented submission process.
- [ ] Source lives in a new, separate GitHub repo: `catholic-daily-gcp-agent`.

## Out of Scope

- First/second reading, responsorial psalm — Gospel only for this
  experiment.
- Any reuse of or dependency on the other Gospel-reading tickets' backends
  (ACE-34/35/36/37/38).
- Offline caching, scheduling, notifications, or any daily-use polish.
- Any Android/iOS/Claude-skill/OpenClaw/Copilot-plugin/GPT work, unrelated
  to this ticket.

## Implementation Plan

# Implementation Plan: Daily Gospel Reading — Google Cloud AI Agent (Experiment)

Pattern: thin new project (new repo, new Azure resource, new Google Cloud
AI agent) — fully independent of the `ace` repo and of the other
Gospel-reading tickets' backends. Nothing in any of those is touched or
reused.

1. **Create the repo**
   - New GitHub repo `catholic-daily-gcp-agent`.
   - Two parts: `backend/` (Azure Function) and `agent/` (the Google Cloud
     AI agent definition/code, per A2A/Gemini Enterprise conventions).

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

3. **Google Cloud AI agent: definition and integration**
   - Research Google's A2A (agent-to-agent) protocol and Gemini Enterprise
     agent-building requirements — this research step itself is part of
     the experiment.
   - Build the agent so that when invoked, it calls the Azure Function
     endpoint and returns the Gospel citation + text in the agent's
     expected response format.
   - On a failed backend call, the agent returns a plain error message —
     no retry, cache, or fallback logic.

4. **End-to-end verification**
   - Test the agent locally or via a Gemini Enterprise sandbox/test harness
     and confirm it returns the real, correct Gospel reading for the
     current date.

5. **Submit to Google Cloud Marketplace**
   - Follow Google's documented process for submitting/listing an AI agent
     on Google Cloud Marketplace's agent ecosystem.
   - Confirm submission is accepted/in review as the final proof of "done"
     (full approval may be outside this ticket's control/timeline, but
     submission itself is the completion signal).

6. **Explicitly deferred**
   - Full daily readings (first/second reading, psalm) — Gospel only.
   - Any dependency on or reuse of the other Gospel-reading tickets'
     backends.
   - Offline caching, scheduling, or daily-use robustness.