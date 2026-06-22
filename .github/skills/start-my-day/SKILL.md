---
name: start-my-day
description: 'Create today''s daily planning note and load active tickets. Use when the user says "start my day", "morning setup", "create today''s note", or "what am I working on today?"'
argument-hint: 'Say "start my day" to create the daily note and load the board'
---

# Start My Day Skill

Load the environment and initialize the workflow database state:

```bash
source .env.local.sh
dotnet run --project src/Ace.Tools.Cli -- workflow start-my-day
```

Then call the linear command to create today's daily planning note:

```bash
source .env.local.sh
dotnet run --project src/Ace.Tools.Cli -- linear start-my-day
```

Report the workflow state (database path, pending ticket counts), and the created daily note path with active tickets loaded.
