---
name: start-my-day
description: 'Create today''s daily planning note and load active tickets. Use when the user says "start my day", "morning setup", "create today''s note", or "what am I working on today?"'
argument-hint: 'Say "start my day" to create the daily note and load the board'
---

# Start My Day Skill

Use the .NET CLI to do the work deterministically:

```bash
dotnet run --project src/Ace.Tools.Cli -- linear start-my-day
```

Then report the created note path, the active tickets loaded, and any empty lanes.
