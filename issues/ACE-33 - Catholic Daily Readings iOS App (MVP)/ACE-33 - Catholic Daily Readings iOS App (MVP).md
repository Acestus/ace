---
LINEAR: ACE-33
title: Catholic Daily Readings iOS App (MVP)
team: Acestus
state: Backlog
flow: queue
urgency: 3
due:
created: 2026-07-03
---

## Description

## User Story

As a Catholic app user, I want to open a free iOS app and immediately see
today's Mass readings with an option to hear them read aloud, so that I can
do my daily reading/devotional without needing a paid subscription app like
Hallow.

## Acceptance Criteria

- [ ] A new standalone GitHub repo `Acestus/catholic-daily-ios` exists,
      containing a SwiftUI iOS app project.
- [ ] On launch, the app displays today's Catholic Mass readings (from
      USCCB.org) on the main screen.
- [ ] The reading content is fetched from an Azure-hosted backend (HTTP
      Azure Function) that scrapes and parses USCCB.org live per request —
      no scraping happens on-device.
- [ ] The screen includes an "Audio Reading" option that uses on-device
      text-to-speech (AVSpeechSynthesizer) to read the content aloud — no
      pre-recorded/generated audio, no extra backend for audio.
- [ ] If the backend call fails (no network, USCCB format change, etc.), the
      app shows a visible error state instead of a blank/frozen screen.
- [ ] The Azure Function is deployed (Bicep IaC, dev environment) and
      reachable from the app.
- [ ] The app builds and runs successfully on a physical iPhone via Xcode,
      using free-tier (non-paid Apple Developer account) local sideloading —
      no App Store or TestFlight submission required for this ticket.

## Out of Scope (v1)

- Rosary, examen, saint of the day, favorites/bookmarks, offline caching,
  or any other Hallow-style feature beyond daily readings.
- Android version.
- Paid Apple Developer account, TestFlight, or App Store submission.
- Backend caching/storage layer (Function scrapes live per request for v1).
- Pre-recorded or generated audio files.

## Implementation Plan

Pattern: new standalone repo, thin vertical slice (one feature: daily
readings) rather than full Hallow feature parity. iOS-only, Apple-native
stack. Azure backend kept as simple as possible (no caching layer) for MVP.

1. **Scaffold the repo**
   - Create `Acestus/catholic-daily-ios` on GitHub.
   - Create a new SwiftUI iOS App project (Xcode, no CoreData/SwiftData
     needed yet since there's no persistence requirement for v1).
   - Add `.gitignore` for Xcode/Swift Package Manager artifacts.

2. **Azure backend: USCCB scraper Function**
   - New Azure Function App (HTTP-triggered, anonymous or function-key auth)
     in a dedicated resource group, Bicep IaC (dev param file only, per
     acewatch-style dev/stg/prd convention but only `dev` needed for MVP).
   - Function fetches USCCB.org's daily readings page, parses out the
     reading citations/text (e.g., via HTML parsing library appropriate to
     the Function's runtime language), and returns clean JSON
     (e.g., `{ date, readings: [{ citation, text }], gospel: {...} }`).
   - No storage/cache — scrape happens fresh on each HTTP request.
   - Deploy via `az stack group create` (or equivalent), OIDC-based GitHub
     Actions workflow for CI/CD, matching acewatch's secretless deploy
     pattern.

3. **SwiftUI app: readings screen**
   - Single main view: fetches from the Function's HTTP endpoint on
     appear, displays the parsed readings.
   - Loading state while the network call is in flight.
   - Error state (visible banner/message) if the request fails or times
     out — do not fail silently.

4. **Audio reading feature**
   - "Play audio" button on the readings screen.
   - Uses `AVSpeechSynthesizer` to read the fetched text aloud on-device.
     No backend involvement, no audio files.

5. **Local run/verification**
   - Deploy the Azure Function to dev.
   - Point the app's endpoint config at the deployed dev Function URL.
   - Build and run on a physical iPhone via Xcode using a free (personal
     team) Apple ID for local sideloading.
   - Confirm: today's readings appear, audio playback works, and an error
     state renders correctly when the network/backend is unreachable
     (e.g., airplane mode test).

## What Stays Untouched

- No changes to the `ace` repo — this is a fully separate project/repo.
- No Android work, no other Hallow-style features, no App Store/TestFlight
  pipeline in this ticket.

## Actions

### 2026-07-03

WORKLOG: Stub created from Linear ACE-33. Planned via ticket-planner skill
(draft: issues/_drafts/catholic-daily-ios-mvp.md), then filed via
linear-backlog skill.

## Follow-up

Status: Backlog
TODO:
