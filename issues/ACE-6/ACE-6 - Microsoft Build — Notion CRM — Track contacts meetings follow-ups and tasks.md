---
LINEAR: ACE-6
title: Microsoft Build — Notion CRM — Track contacts meetings follow-ups and tasks
team: Acestus
state: Backlog
flow: queue
urgency: 3
due: None
created: 2026-05-29
---

## Description

Use Notion to track contacts, meetings, follow-ups, and prep tasks for Microsoft Build.

## Investigation

------------------------------------------------

### 2026-05-30 00:05

**Problem confirmed:** There is no system for turning Microsoft Build attendees into an ongoing network-building workflow. The user wants a Notion CRM to track public attendees, outreach status, contact details, small-talk hooks, and follow-up reminders, with follow-up items promoted into Linear issues.

**Current state:**
- No existing Notion database for this workflow
- Source list is the public Build attendee page
- Follow-up work should create Linear issues
- The model should use separate databases in a star-schema shape

**Constraints:**
- Use publicly listed attendee information
- No restriction on capturing public contact details
- The system should support ongoing opportunities after Build, not just one-off notes
- Important follow-ups can all become Linear issues

**Decisions made:**
- Reminder cadence: **weekly** default; monthly for nurturing relationships post-Build
- Follow-up becomes a Linear issue when real delivery work is needed (demo, proposal, intro)
- Reminders driven by the `Due Date` field in the Follow-ups DB (filter Today/This Week)

**Notion databases created (2026-05-30):**
- 👤 People — `370202bafe718124b661dfc0c8d43fff`
- 📨 Outreach — `370202bafe71812d9b07fda6e8b56ec8`
- ✅ Follow-ups — `370202bafe7181808bfbe6aadab99a31`
- Hub page updated with workflow doc and field guide

**Related links:**
- Build attendees: https://build.microsoft.com/en-US/attendees
- Notion: Microsoft Build CRM — https://www.notion.so/Microsoft-Build-CRM-370202bafe7181c4ae18ff8219554d9d

## Actions

### 2026-05-29

WORKLOG: Stub created from Linear ACE-6

### 2026-05-30 00:05

- WORKLOG 15m: Interviewed the request and narrowed the ticket to a Build attendee CRM that supports networking, visibility, and opportunity generation.
- COMMENT: The work is not just contact storage; the goal is a repeatable network-building workflow for Microsoft Build. The user wants to track attendee outreach state, email, LinkedIn, how each person was met, and a small-talk note that makes the next conversation easier. The source of truth starts with the public Build attendee page, and the model should be split into separate Notion databases in a star-schema shape. Follow-up items can all become Linear issues, which keeps the outreach loop actionable instead of hiding it in a note-taking system. I have not yet locked the reminder cadence, so that is the main open design detail. Next step is to define the database model and follow-up workflow.

### 2026-05-30 00:06

- WORKLOG 10m: Drafted and published the first Notion page for the Build CRM design.
- COMMENT: Published the initial Microsoft Build CRM page in Notion and linked it back to the Linear ticket so the documentation stays connected to the work. The page captures the star-schema direction, the core entities, and the tracking fields for each person. That gives us a durable place to refine the workflow instead of trying to hold the model in conversation. Next step is to flesh out the exact database properties and the follow-up/reminder mechanics.

### 2026-05-30 00:47

- WORKLOG 20m: Created all three Notion databases and updated hub page with workflow doc.
- COMMENT: The CRM is now live with three databases — People, Outreach, and Follow-ups — structured in a star schema. The hub page has been updated with the full workflow, field guide, and reminder cadence decision. Weekly cadence is the default. Follow-ups become Linear issues only when real delivery work is required. The system is ready to use: open People, add someone from the Build attendee list, set Next Action Date, then log each touchpoint in Outreach. The daily working view is the People board filtered by Next Action Date = Today.

## Actions

### 2026-05-30 22:36

- WORKLOG 2h: Wrote and ran bulk import script — all 2,213 Build attendees loaded into Notion People DB.

## Follow-up

Status: In Progress
TODO:
- [x] Define database schema
- [x] Create Notion databases
- [x] Document workflow and reminder cadence
- [x] Add first real contacts from Build attendee page (2,212 imported via script)
- [ ] Fill LinkedIn + Email for priority contacts as you meet them at Build
- [ ] Create a filtered "Today" view in People database (deferred, low priority)