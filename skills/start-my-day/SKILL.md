---
name: start-my-day
description: 'Create today''s daily planning note, load active tickets from Linear, and present the day''s board. Use when the user says "start my day", "morning setup", "create today''s note", or "what am I working on today?"'
argument-hint: 'Say "start my day" to create the daily note and load the board'
---

# Start My Day Skill

## Role

This skill is a thin collar over the daily morning setup command set.
SQLite-backed local databases are the source of truth for operational state.

## Command Surface

- `dotnet run --project src/Ace.Tools.Cli -- planner start-my-day` — load Linear
  active+queue tickets, merge live rounds lane claims, persist a snapshot into
  `~/.ace/rounds.db` (`daily_snapshot` table), and write/skip today's
  `planner/<MM-dd>.org` note. Skips rebuild if the note already has content.
- `dotnet run --project src/Ace.Tools.Cli -- planner start-my-day --force` —
  force-rebuild today's note even if it already exists.
- `dotnet run --project src/Ace.Tools.Cli -- planner daily-note` — alias for
  the same operation, always force-rebuilds.
- `dotnet run --project src/Ace.Tools.Cli -- linear start-my-day [--force]` —
  same implementation, invoked via the `linear` verb.

## Operating Contract

1. Route user intent to `planner start-my-day` (or `linear start-my-day`;
   same underlying implementation in `LinearCommands.StartMyDayAsync`).
2. Data flow: Linear GraphQL (`state=In Progress` for active, `flow:queue`
   label for queue) → merged with `~/.ace/rounds.db` lane claims → written to
   `daily_snapshot` table → rendered into `planner/<MM-dd>.org`.
3. The note's Kanban board reflects live rounds claims (`:ROUNDS:` field per
   lane entry — `claimed:lane-N` or `unclaimed-in-rounds`), not just Linear
   state, so drift between Linear and rounds is visible instead of silent.
4. Use `--help` for full syntax and examples.
5. Keep this skill short and maintainable (<200 lines).

## Notes

- Previously this skill pointed at a dead `WorkflowHandler`/`workflow.db` code
  path that was never wired into `ToolApp.cs` after a CLI rewrite. That code
  still exists but is unused; do not resurrect it. The live implementation is
  entirely in `LinearCommands.cs` + `RoundsDb.cs`.
- If active tickets stop showing up, check `linear search --label "flow:queue"`
  and confirm the Linear workflow state names match `ResolveFlowState` in
  `LinearCommands.cs` (`LINEAR_STATE_ACTIVE` env override available).
