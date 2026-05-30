---
name: weekly-summary
description: 'Generate a weekly status report or brag document. Pulls flow:done tickets from Jira, calculates hours by swimlane from planner org files, and drafts a markdown summary. Use when the user says "weekly summary", "brag doc", "what did I do this week", "weekly status", or "sprint summary".'
argument-hint: 'Optionally specify a week start date (YYYY-MM-DD) or output format (report/markdown)'
---

# Weekly Summary Skill

Generate the weekly status report first. Review it. Then generate markdown once the numbers look right. Don't skip straight to the brag doc.

## When to Use

- User says "weekly summary", "weekly status", "what did I do this week", or "sprint summary"
- User wants a brag doc for leadership, review notes, or a personal accomplishment log
- User wants swimlane hours for the week, not just a list of tickets

---

## Workflow

### Step 1 — Run the report

```bash
cd /home/wweeks/git/projects
python3 scripts/weekly_summary.py --report
```

That pulls:
- `flow:done` tickets completed this week from Jira
- `flow:waiting` tickets moved to waiting this week
- planner worklog hours from `planner/MM-DD.org`
- swimlane totals using the scoring labels

If the user names a week, pass it directly:

```bash
python3 scripts/weekly_summary.py --report --week 2026-05-19
```

The script normalizes that date to the Monday of the same week.

### Step 2 — Review the output

Check three things before you draft markdown:

1. Completed tickets look right
2. Waiting tickets look right
3. Planner hours are sane and the lane totals add up

If the planner files are missing, fix that first. The summary is only as good as the local org files.

### Step 3 — Generate markdown

Once the report looks right:

```bash
cd /home/wweeks/git/projects
python3 scripts/weekly_summary.py --markdown
```

If the user wants a file you can paste into email, Teams, or the brag doc:

```bash
python3 scripts/weekly_summary.py --markdown --output weekly-status.md
```

### Step 4 — Post or reuse it

From there you can:
- paste it into a weekly status email
- append the highlights into `planner/brag-document26.md`
- drop it into a leadership update
- trim it down for a standup or sprint closeout

---

## CLI Reference

```bash
python3 scripts/weekly_summary.py --report
python3 scripts/weekly_summary.py --markdown
python3 scripts/weekly_summary.py --week 2026-05-19
python3 scripts/weekly_summary.py --markdown --output weekly-status.md
```

### Modes

- `--report` — plain stdout tables for quick review
- `--markdown` — markdown brag doc / status update format
- `--week YYYY-MM-DD` — any date in the target week; script rolls back to Monday
- `--output FILE` — write the rendered output to a file

---

## Example Output

```markdown
# Weekly Status — May 18–22, 2026

## Completed (flow:done)

| Key | Summary | Lane | Hours |
|-----|---------|------|-------|
| <PROJECT>-366 | Fabric - Pipeline Schedule - Fix Schedule Loss During CI-CD Deployment | 🔴 Urgent | 1.5h |
| <PROJECT>-360 | Five9 - Graph API - Add Sites Selected Permission to UMI | 🔵 Manual | 1.0h |

## Shipped to Review (flow:waiting)

| Key | Summary | Waiting On |
|-----|---------|------------|
| <PROJECT>-344 | Fabric - Pipeline Triggers - Modernize Execution Triggers and Scheduling | AppDev team review and decision to proceed |
| <PROJECT>-343 | GitHub - Governance - Establish Source of Truth Drift Management | team review and adoption of governance recommendations |

## Time by Swimlane

| Lane | Hours | % |
|------|-------|---|
| 🔴 Urgent | 3.5h | 25% |
| 🔵 Manual | 8.0h | 57% |
| 🟢 Background | 2.5h | 18% |
| **Total** | **14.0h** | |

## Highlights

- <PROJECT>-366 — Closed Fabric pipeline schedule fix. Logged 1.5h in 🔴 Urgent work.
- <PROJECT>-360 — Closed Sites.Selected permission change for the UMI. Logged 1.0h in 🔵 Manual work.
```

---

## Notes

- The script reads planner org files from `planner/MM-DD.org`
- Those planner files need to exist locally and be committed if you want the week to be reproducible later
- Waiting-on notes are best-effort. They come from the local issue markdown when it exists
- Swimlane rules are fixed:
  - 🔴 Urgent: `urgency <= 2`
  - 🔵 Manual: `agentic >= 4` and `importance <= 3`
  - 🟢 Background: `agentic <= 2`
  - default: Manual

---

## Kaizen Review (Process Improvement)

After generating the weekly summary, run a kaizen pass over the completed tickets. This is the retrospective trigger that identifies process improvements.

### When to Run

- Automatically at the end of `--markdown` generation (appended as a separate section)
- On explicit request: "weekly kaizen", "what should I improve", "process review"

### What It Checks

For each `flow:done` ticket completed this week, examine:

1. **Cycle time** — days from `flow:active` to `flow:done`. Flag anything >5 days:
   ```
   ⏱  Slow: <PROJECT>-366 — 7 days active (expected: 2-3 days for 🔴 Urgent)
      Why: Waited 4 days for vendor response mid-ticket without parking
   ```

2. **Constraint patterns** — which constraints appeared most:
   ```
   🔒 Constraint summary: technician 3/4 | vendor:MS 1/4
      → 75% of completed work was you-only. Documentation gap?
   ```

3. **Reflection themes** — scan issue file `**Reflection:**` entries for repeated themes:
   ```bash
   grep -h "Reflection:" /home/wweeks/git/projects/issues/*//*.md | tail -20
   ```
   Group by theme and surface patterns:
   ```
   🪞 Reflection themes this week:
      • "Check Azure state first" (×2) — consider adding to investigation checklist
      • "Should have set a deadline" (×1)
   ```

4. **Pattern candidates** — tickets closed this week that had `constraint:technician` but NO pattern entry in `planner/patterns/`:
   ```
   📝 Undocumented technician work:
      • <PROJECT>-360: UMI Graph permission — pattern exists ✓
      • <PROJECT>-363: Five9 engine scaffold — NO pattern. Document?
   ```

5. **WIP violations** — any time 4+ tickets were `flow:active` simultaneously (check changelog):
   ```
   ⚠  WIP breach: May 20, 4 tickets active for 2 hours (<PROJECT>-363 wasn't parked before pulling <PROJECT>-401)
   ```

### Output Format

Append to the weekly summary markdown:

```markdown
## 🔄 Kaizen — Process Observations

### Cycle Time
| Key | Days Active | Lane | Flag |
|-----|------------|------|------|
| <PROJECT>-366 | 7d | 🔴 | ⚠ Slow — vendor wait not parked |
| <PROJECT>-360 | 1d | 🔵 | ✓ |

### Constraints
- Technician: 3/4 completed tickets (75%) — high bus factor
- Vendor: 1/4 — acceptable

### Reflection Themes
- "Check Azure state first" appeared 2× — **Action:** Add to ticket-investigator Phase 3 checklist?

### Pattern Gaps
- <PROJECT>-363: Five9 engine scaffold — undocumented, technician-only

### Improvement Candidates
1. Park tickets immediately when waiting >24h on vendor (avoids inflated cycle time)
2. Add "verify Azure current state" as first investigation step
3. Document Five9 engine pattern before next similar ticket
```

### What Happens with Improvements

- Surface them to the user at the end of the weekly summary
- If the user says "yes" to an improvement, create a `way:kaizen` backlog item via `backlog` skill
- These items get `urgency:5, importance:2, agentic:2` (🟢 Background lane) — they're process debt, not urgent work
- Tag with `kaizen:{week-start-date}` for traceability

---

## Composes

```
weekly-summary
└── backlog              (Kaizen section — create way:kaizen backlog items)
```

**Called by:** user directly, or `end-my-day` (suggested on Fridays)


---

## SDP Awareness (Lanes 4–6)

ServiceDesk Plus work runs as a parallel set of three swimlanes (Lane 4 🔴 SDP-Urgent, Lane 5 🟠 SDP-Approval, Lane 6 🟢 SDP-Background). SDP case files live under `cases/{display_id}/`. The header `OWNER: jira | sdp` decides which side holds the WIP slot:

- `OWNER: sdp` (default) — the SDP case is the WIP owner; counts against the SDP lane cap
- `OWNER: jira` — the SDP case is a **shadow** of a linked <PROJECT>-XXX issue; does NOT count against any SDP lane cap

When this skill needs to enumerate or render the operator's work, it MUST union both sources (`issues/` + `cases/`) and dedupe by cross-link (`JIRA:` header in cases, `SDP:` header in issues). Shadows are surfaced as "(shadow of <PROJECT>-XXX)" annotations, not as independent slots.

For lane-routing and rounds claims, see `rounds` and `sdp-dispatcher`. The shared `/tmp/rounds-claims.json` uses keys `lane1`–`lane5` shared across Jira and SDP tickets (single ticket per lane, regardless of system).

Voice wall: SDP `COMMENT:` lines are **end-user voice** (plain language). Jira COMMENT lines are internal investigative voice. This skill must preserve that distinction wherever it emits or summarizes comments.

For SDP-specific dispatch, render, or close-out, hand off to: `rounds`, `sdp-dispatcher`, `sdp-investigator`, `sdp-worklog`, `sdp-router`.
