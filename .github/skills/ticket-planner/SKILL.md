---
name: ticket-planner
description: 'Interview the user until 95% confident, then draft an Atlassian-style user story and implementation plan for a NEW piece of work — before any Linear ticket exists. Use when the user says "plan a new ticket", "help me scope this feature", "I want to plan out a new ticket", or wants to think through a feature before filing it in Linear. Produces a local draft only; never calls the Linear API.'
argument-hint: 'Describe the feature or problem you want to plan a ticket for'
---

# Ticket Planner Skill

Turn a rough idea into a well-formed Atlassian user story + implementation plan,
saved as a local draft — with **no Linear ticket created yet**. This is the
pre-ticket counterpart to `ticket-investigator` (which works a ticket that
already exists) and hands off to `linear-backlog` (which files the real ticket).

**You never create a Linear issue in this skill. You never write implementation
code in this skill. The only output is a draft markdown file.**

## When to Use

- User wants to plan/scope a new feature before it's a Linear ticket
- User says "plan a new ticket", "help me think through this feature", "draft a user story for..."
- User wants an implementation plan attached to a story before filing work

## Workflow

### Phase 1 — The Interview

Open with:
> "I'm about to plan this out. Interview me until you have 95% confidence about
> what I actually want — not what I think I should want."

Ask **one question at a time** with the `ask_user` tool. Push back gently on
vague answers. Surface, in order:

1. **Intent** — what problem does this solve, in one sentence? Who benefits?
2. **Prior art** — is there an existing doc, ticket, or pattern this should anchor to?
3. **Scope boundary** — where should this new subcommand/feature live? Should it
   change any existing command's behavior, or stand alone?
4. **Mechanics** — how should the CLI/feature actually work end-to-end? Walk the
   happy path and at least one failure/edge case.
5. **Output shape** — what does "done" look like? What artifact or behavior proves it works?

Keep asking until you can state the problem back and the user confirms it's right.
Document any remaining uncertainty explicitly rather than guessing.

### Phase 2 — Draft the User Story (Atlassian model)

Format: `As a [user], I want [goal], so that [reason].`
Add **Acceptance Criteria** as a bullet list (the "Confirmation" of the 3 C's —
Card, Conversation, Confirmation). Each criterion must be testable/observable.

Write this to a temp file, e.g. `/tmp/{slug}-story.md`.

### Phase 3 — Draft the Implementation Plan

A numbered, incremental list of concrete steps (name the pattern if one applies —
Strangler Fig, thin new command, etc.). Call out what stays untouched. Keep it
scoped to what was actually discussed in the interview — no speculative extras.

Write this to a temp file, e.g. `/tmp/{slug}-plan.md`.

### Phase 4 — Present and Confirm

State back to the user, in the same shape as `ticket-investigator` Phase 4:
1. The problem, in plain terms
2. The user story
3. The implementation plan
4. What "done" looks like

<HARD-GATE>
Do not save the draft until the user explicitly approves it via `ask_user`
("yes", "approved", "looks good", or equivalent).
</HARD-GATE>

### Phase 5 — Save the Draft

Once approved, save the draft using the CLI — this is the only state-changing
action this skill takes, and it only touches the local filesystem:

```bash
cd /home/acestus/git/ace
dotnet run --project src/Ace.Tools.Cli -- linear plan-issue \
  --title "{Short Title}" \
  --story-file /tmp/{slug}-story.md \
  --plan-file /tmp/{slug}-plan.md
```

This writes `issues/_drafts/{slug}.md` (front matter: `title`, `created`,
`status: draft`). It **fails if a draft with that slug already exists** — pick
a different `--slug` or ask the user whether to replace the existing one first.

Report the result:
```
✓ Draft saved: issues/_drafts/{slug}.md
```

Clean up the temp story/plan files after a successful save.

### Phase 6 — Hand Off

Tell the user this draft is ready to become a real ticket whenever they want,
via the `linear-backlog` skill:

> "This is saved as a draft, not a Linear ticket. When you're ready to file it,
> say 'create the Linear ticket from issues/_drafts/{slug}.md' and I'll pull the
> story/plan into `linear create-issue`, ask you for team/priority/labels, and
> file it for real."

Do not proceed to create the Linear issue yourself in this skill, even if asked
mid-conversation — redirect to `linear-backlog` so ticket creation stays a
distinct, explicit step.

## Tone and Communication Style

Same as `ticket-investigator`: methodical, evidence-based, separates problem
from solution, incremental by default. Push back on vague scope before writing
anything down.

## Important Notes

- This skill never calls the Linear API and never edits application code.
- If the user already has a Linear key in mind, redirect to `ticket-investigator`
  instead — this skill is strictly for work that isn't a ticket yet.
- Reuse `dotnet run --project src/Ace.Tools.Cli -- linear plan-issue --help`
  if you need to confirm current CLI flags.

**Called by:** user directly, or `rounds` when a new idea surfaces mid-session
that isn't yet a ticket.
