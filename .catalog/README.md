# Deterministic Local-First Day-End Path

## Overview

This feature implements a deterministic, local-first day-end flow that eliminates randomness from standup summaries and minimizes external API queries during end-of-day operations.

### Key Design Principles

1. **Deterministic** - No random data shuffling. Standup summaries are always identical when generated from the same snapshot.
2. **Local-first** - Prefer the local SQLite snapshot (.catalog/assigned-work.db) over live queries when available.
3. **Explicit boundaries** - Daily workflow has clear start and end points, no background syncs.
4. **Fast standup generation** - Query local snapshot instead of making live API calls to Linear/Notion/GitHub.

## Components

### Scripts

#### `scripts/planner-dayend.sh` (Bash)
Orchestrates the day-end flow:
```bash
bash scripts/planner-dayend.sh
```

Steps:
1. Runs `dotnet workflow end-my-day` to publish pending changes
2. Creates snapshot: `cp ~/.acestus/workflow.db .catalog/assigned-work.db`
3. Generates standup summary template
4. Shows day-end summary with database locations

#### `scripts/Planner-DayEnd.ps1` (PowerShell)
Windows equivalent with same functionality:
```powershell
./scripts/Planner-DayEnd.ps1
```

### C# Utility: `CatalogSnapshotReader`

Location: `src/Ace.Tools.Cli/CatalogSnapshotReader.cs`

Queries the local catalog snapshot for deterministic results:
```csharp
var reader = new CatalogSnapshotReader();

// Check if snapshot exists
if (reader.IsAvailable) { /* use local data */ }

// Get snapshot timestamp
var timestamp = reader.GetSnapshotTimestamp();

// Get today's tickets (deterministic ordering)
var tickets = await reader.GetTodaysTicketsAsync();

// Get completed work
var work = await reader.GetPendingWorkAsync();

// Get pending items to sync
var comments = await reader.GetPendingCommentsAsync();
var pages = await reader.GetPendingPagesAsync();

// Generate markdown standup
var markdown = await reader.GenerateStandupMarkdownAsync();
```

### CLI Commands

#### `workflow end-my-day`
Publishes changes to Linear/Notion/GitHub and prepares for sync.

#### `workflow standup`
Generates standup summary from local snapshot:
```bash
dotnet run --project src/Ace.Tools.Cli -- workflow standup
```

Output:
```
📋 Generating standup summary...
📸 Using local snapshot: 2026-06-18 19:03:04 UTC

# Daily Standup
**Generated:** 2026-06-18 19:04:20 UTC

📸 **From Local Snapshot:** 2026-06-18 19:03:04 UTC
*(Deterministic - no live queries)*

## Work Completed
- (items from work_logs table)

## Today's Tickets
- (items modified today from tickets table)

## Pending Syncs
- Comments: (count from comments_pending)
- Notion pages: (count from pages_pending)
```

## Database Files

### `.catalog/assigned-work.db`
Snapshot of `~/.acestus/workflow.db` created during end-my-day flow.

- **Location**: `.catalog/assigned-work.db` (in repository root)
- **Created**: `planner-dayend.sh` or workflow end-my-day
- **Size**: ~168 KB (same schema as main workflow database)
- **Tables**: 15+ (tickets, work_logs, comments_pending, pages_pending, etc.)
- **Updated**: Once per day at end-of-day flow
- **Use**: Fast, deterministic standup summaries

### `.catalog/standup-summary.txt`
Template for standup summary, created during end-my-day flow.

## Workflow: Daily Flow

### Morning (start-my-day)
```bash
dotnet run --project src/Ace.Tools.Cli -- workflow start-my-day
```
- Refreshes from Linear/Notion/GitHub
- Updates `~/.acestus/workflow.db`
- Shows today's dashboard

### During Day
Work from local database without external syncing:
```bash
dotnet run --project src/Ace.Tools.Cli -- workflow dispatch --lane 1
```
- All queries read from local SQLite
- No live API calls needed
- Can work offline

### Evening (end-my-day)
```bash
bash scripts/planner-dayend.sh
```
1. **Sync phase**: Publishes pending changes
   ```bash
   dotnet run --project src/Ace.Tools.Cli -- workflow end-my-day
   ```

2. **Snapshot phase**: Creates local copy
   ```bash
   cp ~/.acestus/workflow.db .catalog/assigned-work.db
   ```

3. **Summary phase**: Prepares standup
   - Generates `.catalog/standup-summary.txt`
   - Ready for `workflow standup` queries

### Standup Generation (deterministic)
```bash
dotnet run --project src/Ace.Tools.Cli -- workflow standup
```
- Queries `.catalog/assigned-work.db` (frozen at end-of-day)
- No live queries to Linear/Notion/GitHub
- Results are identical every time from same snapshot
- Fast (local database, no network latency)

## Implementation Details

### Snapshot Creation
```powershell
# Bash
cp ~/.acestus/workflow.db .catalog/assigned-work.db

# PowerShell
Copy-Item $WorkflowDb $CatalogDb -Force
```

### Query Ordering (Deterministic)
All queries use explicit ORDER BY clauses:
- Tickets: by priority DESC, status DESC, updated_at DESC
- Work logs: by created_at DESC
- Comments/Pages: by created_at DESC

### Catalog Reader Architecture
```
CatalogSnapshotReader
├── IsAvailable → Check if .catalog/assigned-work.db exists
├── GetSnapshotTimestamp() → File's last modified time (UTC)
├── GetTodaysTicketsAsync() → Query tickets table
├── GetPendingWorkAsync() → Query work_logs table
├── GetPendingCommentsAsync() → Query comments_pending table
├── GetPendingPagesAsync() → Query pages_pending table
└── GenerateStandupMarkdownAsync() → Render markdown summary
```

### Fallback Behavior
If snapshot missing: `GetStandupSummaryAsync()` shows warning:
```
⚠️  No local snapshot found. Run 'planner end-my-day' to create one.
```

## Benefits

| Aspect | Traditional | Local-First |
|--------|------------|------------|
| **Randomness** | May re-query APIs, different results each time | Frozen snapshot, identical results |
| **Latency** | API calls + network overhead | Local SQLite (< 100ms) |
| **Availability** | Fails if Linear/Notion down | Works offline |
| **Data Consistency** | May see in-flight changes | Fixed point-in-time snapshot |
| **Audit Trail** | No record of what snapshot was used | Timestamp in summary (.catalog/assigned-work.db) |

## Future Enhancements

- [ ] Compress snapshots for faster copying
- [ ] Archive snapshots by date: `.catalog/2026-06-18.db`
- [ ] Schema migrations if workflow.db schema changes
- [ ] Backup snapshots before overwriting
- [ ] Export snapshot to CSV/JSON for reports
- [ ] Standup summary email template
- [ ] Git history of snapshots (track daily changes)

## Troubleshooting

### Snapshot not created
- Ensure `.catalog/` directory exists and is writable
- Check `.acestus/workflow.db` exists at `~/.acestus/workflow.db`
- Run `workflow init-db` if database missing

### Standup shows no data
- Run `workflow end-my-day` first to create snapshot
- Verify `.catalog/assigned-work.db` exists: `ls -lh .catalog/assigned-work.db`
- Ensure workflow database has data (tickets, work logs, etc.)

### Queries fail with schema errors
- Snapshot may be from old schema version
- Delete snapshot and run `workflow end-my-day` again
- Schema auto-initializes on `workflow init-db`

## Related Commands

```bash
# Initialize workflow database
dotnet run --project src/Ace.Tools.Cli -- workflow init-db

# Refresh database from live systems
dotnet run --project src/Ace.Tools.Cli -- workflow start-my-day

# Publish pending changes and create snapshot
bash scripts/planner-dayend.sh

# Generate deterministic standup summary
dotnet run --project src/Ace.Tools.Cli -- workflow standup

# Dispatch next ticket (reads from local database)
dotnet run --project src/Ace.Tools.Cli -- workflow dispatch --lane 1
```

## Files Modified/Created

**New Files:**
- `scripts/planner-dayend.sh` - Bash day-end orchestration
- `scripts/Planner-DayEnd.ps1` - PowerShell day-end orchestration
- `src/Ace.Tools.Cli/CatalogSnapshotReader.cs` - Snapshot query utility

**Modified Files:**
- `src/Ace.Tools.Cli/WorkflowHandler.cs` - Added standup command
- `src/Ace.Tools.Cli/ToolApp.cs` - Added standup to help text

**Generated at Runtime:**
- `.catalog/assigned-work.db` - Daily snapshot (168 KB)
- `.catalog/standup-summary.txt` - Standup template
