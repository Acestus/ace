---
title: Catholic Daily Gospel GPT (GPT Store, Gospel v1)
created: 2026-07-03
status: draft
---

## User Story

## User Story

As a ChatGPT user, I want to open the "Catholic Daily Gospel" Custom GPT on
the public GPT Store and ask for today's reading, so that I get today's
Gospel text without needing a paid subscription app like Hallow — mirroring
the same daily-reading idea already explored on iOS (ACE-33), Android
(ACE-34), and OpenClaw (ACE-36), this time on the GPT Store platform.

## Acceptance Criteria

- [ ] A new standalone GitHub repo `catholic-daily-gpt` exists, containing a
      dedicated Azure Function backend (separate from ACE-33/34/36's
      backends).
- [ ] The Azure Function scrapes/parses USCCB.org and returns today's Gospel
      citation + full text as JSON on request.
- [ ] If the backend call fails (network issue, USCCB page format change,
      parse failure, etc.), it returns a clear error response rather than
      malformed data or an unhandled exception.
- [ ] A Custom GPT named "Catholic Daily Gospel" is built in OpenAI's GPT
      Builder, with a GPT Action configured to call this Function.
- [ ] When a user asks the GPT for today's reading, it automatically invokes
      the Action and returns the Gospel text — no extra confirmation step
      required.
- [ ] If the Action call fails, the GPT surfaces a clear error message to the
      user instead of hallucinating content or failing silently.
- [ ] The GPT is published and publicly listed on the OpenAI GPT Store (not
      private/unlisted).
- [ ] Verified end-to-end: asking the live, publicly listed GPT for today's
      reading returns the real, current Gospel text sourced from USCCB.org.

## Out of Scope (v1)

- First reading, responsorial psalm, second reading — Gospel only, matching
  ACE-36's scope.
- Sharing/reusing the Azure Function backends built for ACE-33/34/36 — this
  GPT gets its own separate backend.
- Any other Hallow-style feature (rosary, examen, saint of the day, etc.).
- Monetization/pricing on the GPT Store — free/public listing only.

## Open Dependency

- Requires a ChatGPT Plus/Team/Enterprise subscription to build and publish
  GPTs — not yet in place; acquiring one is part of this ticket's work.

## Implementation Plan

## Implementation Plan

Pattern: new standalone repo + backend (mirrors ACE-36's approach), paired
with OpenAI's GPT Builder for the GPT/Action configuration itself (which has
no repo — it's configured and hosted in ChatGPT). Fully independent of
ACE-33/34/36 — no shared backend or code.

1. **Acquire ChatGPT subscription**
   - Sign up for ChatGPT Plus, Team, or Enterprise (whichever is
     appropriate) — required to access GPT Builder and publish to the GPT
     Store.

2. **Create the repo**
   - New GitHub repo `catholic-daily-gpt`, containing the Azure Function
     backend only (the GPT/Action config lives in OpenAI's platform, not in
     this repo).

3. **Backend: USCCB Gospel scraper (Azure Function)**
   - HTTP-triggered Function, e.g. `GET /api/gospel?date=YYYY-MM-DD`
     (defaults to today).
   - Fetches USCCB's daily readings page for the given date, parses out only
     the Gospel citation + full text.
   - Returns JSON `{ date, citation, text }` on success.
   - Returns a distinct error response (e.g. 502 with
     `{ error: "parse_failed" }`) if the page can't be parsed.
   - Deploy via Bicep IaC (dev environment), OIDC-based GitHub Actions
     workflow — no long-lived secrets.

4. **Build the Custom GPT**
   - In OpenAI's GPT Builder, create a new GPT named "Catholic Daily
     Gospel."
   - Write instructions so the GPT automatically calls the Action whenever
     asked for "today's reading" (or similar), rather than requiring an
     explicit trigger phrase.
   - Configure a GPT Action with the OpenAPI schema for the deployed Azure
     Function endpoint (auth: function key or anonymous, matching the
     Function's config).
   - Add instructions for how the GPT should present a clear error message
     if the Action call fails, instead of guessing/hallucinating content.

5. **Publish to the GPT Store**
   - Complete OpenAI's publishing flow (builder profile, category, etc.) to
     list the GPT publicly on the GPT Store.

6. **Verification**
   - From the live, publicly listed GPT, ask for today's reading.
   - Confirm it returns the real, current Gospel citation + text sourced
     from USCCB.org via the deployed Function.
   - Force a failure path (e.g., temporarily point the Action at a bad URL)
     and confirm the GPT surfaces a clear error instead of fabricating
     content.

## What Stays Untouched

- The `ace` repo — this is a fully separate project/repo.
- Any backend or code built for ACE-33 (iOS), ACE-34 (Android), or ACE-36
  (OpenClaw) — this GPT's backend is independent and not shared.
- No readings beyond the Gospel, no monetization/pricing configuration.