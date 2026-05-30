---
name: outbox-refresh
description: 'Regenerate per-stakeholder outbox files from flow:waiting (In Review) issue markdown. Produces newspaper-lede cards (Lede / Status / Next / Links) in planner/outbox/{slug}.md. Use when the user says "refresh outbox", "rebuild outbox", "update outbox for backlog meeting", "fill the outbox", or before a 1:1/manager sync.'
argument-hint: 'Optional: --no-catchall, --manager "Name", --dry-run'
---

# Outbox Refresh Skill

Rebuild the per-stakeholder outbox under `planner/outbox/` from the `flow:waiting` issue markdown files. Each outbox file is a list of **newspaper-style cards** — Lede, Status, Next, Links — reconstructed from the source ticket's `## Notes` section. The same ticket can appear in multiple outbox files (one per stakeholder + manager catch-all + any vendor / code-review / external-ticket bucket).

This is what feeds backlog 1:1s, especially the <APPROVER_NAME> manager sync. Every waiting ticket should be visible to him in one place.

## When to Use

- User says "refresh outbox" / "rebuild outbox" / "regenerate outbox"
- User says "fill the outbox" / "outbox for backlog meeting" / "outbox for 1:1"
- End of day, before pushing — so tomorrow's manager sync has the full picture
- After bulk editing `flow:waiting` issue files

## Workflow

1. **Refresh the markdown.** `python3 scripts/outbox_refresh.py` — rebuilds `planner/outbox/*.md` from the source `issues/` files. Each card carries a prominent `💬 Comment on Linear →` link.
2. **Publish to Notion.** `python3 scripts/outbox_publish.py` — mirrors each outbox file to a child page under **WWeeks → WWeeks Outbox** in the IPM space. Idempotent; updates existing pages in place.
3. Open `planner/outbox/INDEX.md` and copy the URL of the stakeholder you're meeting with — paste it into the calendar invite or Teams chat.
4. During the meeting, share the Notion page and walk the cards. **Every direction or decision gets typed straight into the Linear ticket as a comment** — click `💬 Comment on Linear →` on the card; you land on the ticket; add the comment there. That's the durable record. The Notion page is just the read-only meeting agenda.
5. Commit and push (`planner/outbox/INDEX.md` reflects the latest Notion URLs).

The data flow is one-way: `issues/` → `planner/outbox/*.md` → Notion. Steering captured during the meeting lives in Linear (where every stakeholder, including future-me on rounds, can already see it). No round-trip sync needed.

## Standard Commands

```bash
cd /home/wweeks/git/projects && export $(grep -v '^#' .env | xargs)

# The 90% case — refresh + publish
python3 scripts/outbox_refresh.py
python3 scripts/outbox_publish.py

# Preview routing without writing files
python3 scripts/outbox_refresh.py --dry-run

# Preview Notion calls without making them
python3 scripts/outbox_publish.py --dry-run

# Skip <APPROVER_NAME> manager catch-all (only route by explicit stakeholder)
python3 scripts/outbox_refresh.py --no-catchall

# Different manager catch-all
python3 scripts/outbox_refresh.py --manager "Some Other Manager"
```

## Sharing With Stakeholders

After `outbox_publish.py` runs, each person/bucket has a dedicated Notion
page. Open `planner/outbox/INDEX.md` for the URL table — copy the link to the
stakeholder's page when chasing a response (e.g. in a Teams DM to <APPROVER_NAME>
<APPROVER_NAME>, paste their `Outbox · <APPROVER_NAME>` URL — he sees every ticket I'm
waiting on him for as newspaper-lede cards, each with a direct `💬 Comment on
Linear →` link).

Page IDs persist in `planner/outbox/.notion-pages.json` so subsequent
publishes update the same pages. **Do not delete that file** — without it the
script would create duplicate pages instead of updating the existing ones.

## What the Script Does

1. **Scans** every `*.md` file under `issues/` (skipping `archive/`).
2. **Filters** to files containing the literal `flow:waiting` string.
3. **Parses** each file:
   - `## Notes` → `### Lede` / `### Status` / `### Next` subsections (the card body)
   - `## Web Links` → list of inline reference links
   - `## Linked Issues` → blocks/blocked-by/relates-to chain
   - `## Follow-up` → `Waiting on:` field (explicit stakeholder names)
   - Last `### YYYY-MM-DD` action header → waiting-since date and stale-days
4. **Routes** each ticket to one or more outbox files:
   - Any names in `Waiting on:` (split on comma, em-dash stripped)
   - Any names parsed from the `### Status` line (`waiting on X`, `blocked by X`)
   - Fallback buckets when no person is identified:
     - `_code-review.md`, `_vendor.md`, `_external-ticket.md`, `_global-admin.md`, `_leadership.md`, `_compliance.md`, `_no-stakeholder.md`
   - **Always: the manager catch-all (default `michael-seaman.md`)** so the weekly backlog meeting shows everything in one file
5. **Renders** a newspaper-style card per ticket — lede paragraph, **Status** line, **Next** line, then Links and Linked Issues.
6. **Preserves** the existing `## Draft Messages` block at the bottom of each outbox file (everything below `## Draft Messages` survives the refresh).
7. **Prunes** outbox files that no longer have any routed tickets (stale stakeholder files are deleted).

## Card Format

```markdown
### [<PROJECT>-371](https://<YOUR_ATLASSIAN>.atlassian.net/browse/<PROJECT>-371) — <PROJECT>-371 - Enable M365 Copilot Teams Meetings Agent (Scope + Propose)
_Waiting since 2026-05-25 · 1d ago_

M365 Copilot Teams Meetings agent enablement gives <ORG_NAME> users native transcript recap, action items, and cross-platform knowledge retrieval — satisfying Graham's ask without any custom Graph or OBO authentication development. Before licenses can be ordered, GLBA compliance requires an AI Use Policy and Vendor Risk Assessment reviewed and approved by <APPROVER_NAME>.

**Status.** flow:waiting — waiting on <APPROVER_NAME> to approve AI Use Policy and Vendor Risk Assessment on Notion
**Next.** <APPROVER_NAME> reviews AI Use Policy (Notion <PAGE_ID>) and Risk Assessment (<PAGE_ID>) and adds approval comment

**Links:**
- [Notion — AI Use Policy](https://...)
- [Microsoft data boundary documentation](https://...)

**Linked issues:**
- blocks: <PROJECT>-77  <!-- M365 Copilot Licensing -->

---
```

If a ticket renders with a thin lede or no Status/Next, **fix it at the source** — edit `issues/{KEY}*/...md` `## Notes` section, push, and re-run the refresh.

## Rules

- Always run a real refresh (not `--dry-run`) before committing — the outbox files are part of repo state.
- The `## Draft Messages` block is the operator's scratchpad. Never edit anything above it.
- If a card looks thin, the fix is in the **source issue markdown**, not the outbox file. The outbox file is generated.
- The manager catch-all is the default. Disable with `--no-catchall` only when intentionally producing a partial view.
- Outbox files do NOT sync back to Linear — they are purely a local routing/staging surface for follow-up messages.

## Composes

```
outbox-refresh
└── (standalone — reads issues/*.md → writes planner/outbox/*.md)
```

**Called by:** `end-my-day` (refresh before EOD push), directly by user before backlog meetings or 1:1s. Companion to `waiting-ticket-followup` which drafts the actual Teams/email messages.


---
