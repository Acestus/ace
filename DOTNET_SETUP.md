# .NET CLI Setup for Ace.Tools.Cli on macOS ARM64

## Status: ✅ Working

### What was fixed
- Replaced `System.Data.SQLite.Core` (incompatible with ARM64) with `Microsoft.Data.Sqlite` (managed, cross-platform)
- Updated `WorkflowDbContext.cs` and `CatalogSnapshotReader.cs` to use `SqliteConnection`
- Updated connection strings to work with the new provider

### Database location
```
~/.acestus/workflow.db
```

### Quick start
Source the environment first:
```bash
source .env.local.sh
```

Then use any of these:
```bash
# Initialize the database schema
dotnet run --project src/Ace.Tools.Cli -- workflow init-db

# Start your day (snapshot from Linear to SQLite)
dotnet run --project src/Ace.Tools.Cli -- workflow start-my-day

# End your day (snapshot current state to SQLite before git push)
dotnet run --project src/Ace.Tools.Cli -- workflow end-my-day

# Generate standup from snapshot
dotnet run --project src/Ace.Tools.Cli -- workflow standup

# Dispatch next ticket to a lane
dotnet run --project src/Ace.Tools.Cli -- workflow dispatch --lane 1
```

### Verified working
✅ `workflow init-db` — creates ~/.acestus/workflow.db with 15+ tables  
✅ `workflow start-my-day` — queries pending tickets, shows count  
✅ `workflow end-my-day` — checks for pending Linear comments/Notion pages, ready for push  
✅ All workflow commands show structured output ready for parsing  

### Integration with OpenClaw skills
- `start-my-day` skill now calls: `workflow start-my-day` + `linear start-my-day`
- `end-my-day` skill now calls: `workflow end-my-day` + Python daily_note.py

Both skills source `.env.local.sh` before running dotnet commands.

### Next steps
- Test Ainsley agent activation via Telegram/chat
- Wire skills to call the CLI through the OpenClaw gateway
- Set up proper environment passing for Linear API keys in skill context
