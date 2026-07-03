---
title: Catholic Daily Readings OpenClaw Skill (Gospel v1)
created: 2026-07-03
status: draft
---

## User Story

## User Story

As a user of OpenClaw (an agent runtime with a skills/plugins system), I want
to ask my agent for today's Gospel reading and get it back immediately, so
that I can get a feel for what a daily-reading OpenClaw skill would be like,
independent of the iOS (ACE-33) and Android (ACE-34) apps.

## Acceptance Criteria

- [ ] A new standalone GitHub repo `catholic-daily-openclaw` exists,
      containing an OpenClaw skill (`SKILL.md` + supporting files) plus its
      own Azure Function backend.
- [ ] The skill is installable/loadable into a local OpenClaw install.
- [ ] When invoked (e.g. "give me today's reading"), the skill calls a
      dedicated Azure Function backend (separate from any backend built for
      ACE-33/34) that scrapes/parses today's Gospel reading from USCCB.org.
- [ ] The response returned to the user is the Gospel citation and full text
      for today's date — not the full set of Mass readings, not a summary.
- [ ] If the backend call fails (network issue, USCCB page format changes,
      parse failure, etc.), the skill surfaces a clear error message to the
      user instead of failing silently or returning malformed content.
- [ ] The Azure Function is deployed (Bicep IaC, dev environment) and
      reachable by the skill.
- [ ] Verified end-to-end: asking the local OpenClaw install for today's
      reading returns today's actual Gospel text, sourced live from USCCB.org
      through the deployed Function.

## Out of Scope (v1)

- First reading, responsorial psalm, second reading — Gospel only for v1.
- Scheduled/proactive delivery (e.g., heartbeat-triggered daily push) — this
  is on-demand only.
- Sharing/reusing the Azure Function backend planned for ACE-33/34 — this
  skill gets its own separate backend.
- Publishing the skill to ClawHub (the public OpenClaw skill registry) — this
  is a local/experimental install for now.
- Any other Hallow-style feature (rosary, examen, saint of the day, etc.).

## Implementation Plan

## Implementation Plan

Pattern: new standalone repo, thin experimental slice (Gospel-only, on-demand
skill) to get a feel for OpenClaw skill mechanics before deciding whether to
invest further. Fully independent of ACE-33/34 — no shared backend or code.

1. **Create the repo**
   - New GitHub repo `catholic-daily-openclaw`.
   - Two top-level areas: `skill/` (OpenClaw skill: `SKILL.md` + any
     supporting scripts) and `backend/` (Azure Function App).

2. **Backend: USCCB Gospel scraper (Azure Function)**
   - HTTP-triggered Function, e.g. `GET /api/gospel?date=YYYY-MM-DD`
     (defaults to today).
   - Fetches USCCB's daily readings page for the given date, parses out only
     the Gospel citation + full text.
   - Returns JSON `{ date, citation, text }` on success.
   - Returns a distinct error response (e.g. 502 with
     `{ error: "parse_failed" }`) if the page can't be parsed, rather than an
     unhandled exception.
   - Deploy via Bicep IaC (dev environment only), OIDC-based GitHub Actions
     workflow — no long-lived secrets, consistent with existing conventions.

3. **OpenClaw skill**
   - Write `SKILL.md` describing the skill: when to invoke it (e.g. user asks
     for "today's reading" or "Gospel reading"), and what it does (calls the
     dedicated Function endpoint, returns the Gospel text, or surfaces a
     clear error).
   - Skill calls the deployed Function's HTTP endpoint and returns the result
     as the agent's response.
   - No ClawHub publishing step for v1 — install locally for testing.

4. **Local verification**
   - Deploy the Function to dev.
   - Install/load the skill into a local OpenClaw instance.
   - Ask the agent for today's reading; confirm it returns today's actual
     Gospel citation + text.
   - Force a failure path (e.g. point at a bad date or simulate a network
     error) and confirm the skill surfaces a clear error instead of failing
     silently.

## What Stays Untouched

- The `ace` repo — this is a fully separate project/repo.
- Any backend or code built for ACE-33 (iOS) or ACE-34 (Android) — this
  skill's backend is independent and not shared.
- No ClawHub publishing, no scheduled/proactive delivery, no readings beyond
  the Gospel — all explicitly deferred.