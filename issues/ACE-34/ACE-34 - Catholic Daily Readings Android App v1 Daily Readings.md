---
LINEAR: ACE-34
title: Catholic Daily Readings — Android App (v1: Daily Readings)
team: ACE
state: Backlog
flow: queue
urgency: 3
importance: 
due: 
created: 2026-07-03
---

## Description


## User Story

# User Story: Catholic Daily Readings — Android App (v1: Daily Readings)

**As a** Catholic community member (myself and ~20 others in my community),
**I want** a free, ad-free, subscription-free Android app that shows the
official daily Mass readings from USCCB.org,
**so that** my community has an easy way to read the day's Mass readings
without paying for or being advertised to by apps like Hallow.

## Acceptance Criteria

- [ ] An Azure Function App fetches and parses USCCB.org's daily readings
      page for a given date into structured JSON (first reading, responsorial
      psalm, second reading when present, and Gospel — each with citation and
      full text).
- [ ] The Function App exposes an HTTP endpoint that returns today's readings
      as JSON on request (date defaults to today; explicit date param
      supported for testing/future navigation).
- [ ] The endpoint returns a clear error/fallback response if USCCB's page
      format can't be parsed (e.g. site layout changed), rather than crashing
      or returning malformed data.
- [ ] A Kotlin Android app calls this endpoint and displays today's readings
      in a readable, scrollable layout (citation + full text per reading).
- [ ] The app caches the last successfully fetched day's readings locally, so
      it still shows content if offline or if the backend call fails.
- [ ] The full app runs and displays correct, real readings for the current
      date when launched in an Android emulator (no physical device
      available for testing).
- [ ] Source code for both the Function App and the Android app lives in a
      new, separate GitHub repo: `catholic-daily-android`.

## Out of Scope (v1)

- Any feature beyond daily readings (saints of the day, prayers, audio,
  reflections, notifications, multiple languages, iOS, etc.) — explicitly
  deferred to future tickets.
- Publishing to the Google Play Store — this is emulator/sideload-only for v1.
- User accounts, sync, or any per-user personalization.

## Implementation Plan

# Implementation Plan: Catholic Daily Readings — Android App (v1)

Pattern: thin new project (new repo, new Azure resources) — nothing in the
`ace` repo is touched or reused by this work.

1. **Create the repo**
   - New GitHub repo `catholic-daily-android` (public or private, owner's call).
   - Two top-level folders: `backend/` (Azure Function App, .NET/C# — matches
     existing familiarity) and `app/` (Kotlin Android project).

2. **Backend: USCCB scraper + parser (Azure Function, .NET)**
   - HTTP-triggered function `GET /api/readings?date=YYYY-MM-DD` (defaults to
     today, server timezone or explicit param — decide during implementation).
   - Fetch USCCB's daily readings page for the given date.
   - Parse into a structured DTO: `{ date, firstReading, psalm, secondReading?,
     gospel }`, each with `citation` and `text`.
   - Return 200 with JSON on success; return a distinct error shape (e.g. 502
     with `{ error: "parse_failed" }`) if the page can't be parsed, rather
     than throwing an unhandled exception.
   - Add a lightweight cache (Azure Table Storage or Blob) keyed by date, so
     repeat requests for the same day don't re-scrape USCCB every time.

3. **Backend: deploy to Azure**
   - Provision a Function App (Consumption plan is enough for ~20 users).
   - Deploy via GitHub Actions (OIDC auth, no stored secrets — consistent with
     this user's existing Azure conventions).

4. **Android app: skeleton + networking**
   - New Kotlin project (Jetpack Compose recommended as "standard stack" for
     new Android apps in 2026).
   - A repository/service layer that calls the Function App endpoint and
     deserializes the JSON response.
   - Local cache (e.g. DataStore or a simple file) storing the last
     successfully fetched day's readings, used as fallback on network/API
     failure.

5. **Android app: UI**
   - Single screen: today's date + each reading section (citation + text),
     scrollable.
   - Loading state, error state (shows cached fallback with a subtle "offline
     data" indicator if the live fetch failed).

6. **Emulator verification**
   - Run the app in an Android Studio emulator.
   - Confirm it displays real, correct readings for the current date end to
     end (emulator → Function App → USCCB parse).

7. **Explicitly deferred**
   - Play Store publishing, notifications, additional content types (saints,
     prayers, reflections), iOS, multi-day navigation UI, accounts/sync.

## Actions

### 2026-07-03
WORKLOG: Filed ACE-34 in Linear from the ticket-planner draft (issues/_drafts/catholic-daily-readings-android-app-v1-daily-readings.md). Created local stub, removed the draft.
COMMENT: Created ACE-34 from the approved ticket-planner draft — Catholic daily readings Android app, v1 scope.

## Follow-up

Status: Backlog
TODO:
- [ ] Create the separate catholic-daily-android GitHub repo
- [ ] Start with the Azure Function scraper/parser per the implementation plan above
