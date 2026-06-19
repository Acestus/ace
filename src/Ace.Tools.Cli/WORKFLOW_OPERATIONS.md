# Workflow Operations Reference

This document describes the reusable workflow operations in the Ace CLI. All operations are implemented in `WorkflowOperations.cs` as pure, testable, async functions.

---

## Overview

The `WorkflowOperations` class provides a clean, functional API for workflow management:
- **Pure functions**: No side effects except database I/O
- **Structured results**: Every operation returns `OperationResult` with success flag, message, and data
- **Reusable**: Can be called from CLI, skills, CI/CD, or programmatically
- **Deterministic**: Same inputs produce identical outputs

All operations are `async Task<OperationResult>` for easy composition.

---

## Operations Reference

### 1. InitializeDatabaseAsync()

Initialize the workflow SQLite database with the complete schema.

```csharp
var result = await WorkflowOperations.InitializeDatabaseAsync();
if (result.Success) { /* database ready */ }
```

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Database initialized at ~/.acestus/workflow.db",
  Data: {
    TablesCount: 15,
    SchemaSql: "schema.sql"
  }
)
```

**CLI usage:**
```bash
dotnet run -- workflow init-db
```

---

### 2. StartMyDayAsync()

Refresh workflow state from local SQLite. Called at the start of each day to initialize the workspace.

```csharp
var result = await WorkflowOperations.StartMyDayAsync();
if (result.Success) { /* day started */ }
```

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Day started successfully",
  Data: {
    DatabasePath: "~/.acestus/workflow.db",
    PendingTickets: 5,
    TicketsByStatus: {
      Pending: 2,
      InProgress: 2,
      WaitingReview: 1,
      Done: 0
    },
    ReadyForWork: true,
    Timestamp: DateTime.UtcNow
  }
)
```

**What it does:**
1. Connects to local SQLite database
2. Queries pending tickets from all statuses
3. Counts tickets by status
4. Returns formatted dashboard

**CLI usage:**
```bash
dotnet run -- workflow start-my-day
```

**Called by:**
- `start-my-day` skill
- `planner-daystart.sh` script
- User at 9 AM

---

### 3. EndMyDayAsync()

Prepare for end-of-day snapshot and sync. Summarizes pending changes before git push.

```csharp
var result = await WorkflowOperations.EndMyDayAsync();
if (result.Success) { /* ready for snapshot */ }
```

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Day ended successfully - ready for git push + snapshot",
  Data: {
    DatabasePath: "~/.acestus/workflow.db",
    PendingSyncs: {
      LinearComments: 2,
      NotionPages: 1,
      CrmContacts: 0,
      JobSearchApps: 0
    },
    TicketsStatus: {
      Total: 5,
      Pending: 1,
      InProgress: 2
    },
    ReadyForSnapshot: true,
    Timestamp: DateTime.UtcNow
  }
)
```

**What it does:**
1. Connects to local SQLite database
2. Counts pending comments and pages (not yet synced to Linear/Notion)
3. Counts tickets in each status
4. Signals readiness for snapshot creation

**CLI usage:**
```bash
dotnet run -- workflow end-my-day
```

**Called by:**
- `end-my-day` skill
- `planner-dayend.sh` script (before snapshot)
- User at 5 PM

**Note:** The actual sync to Linear/Notion happens via CI/CD after git push, not locally.

---

### 4. DispatchNextTicketAsync(int lane)

Assign the next pending ticket to a lane (for rounds/kanban workflow).

```csharp
var result = await WorkflowOperations.DispatchNextTicketAsync(laneNumber);
if (result.Success) { /* ticket assigned */ }
```

**Parameters:**
- `lane` (1-5): Kanban lane number for rounds workflow

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Lane 1 assigned: ENG-123",
  Data: {
    Lane: 1,
    TicketId: "ENG-123",
    Title: "Implement auth flow",
    Status: "pending",
    Priority: "high",
    Timestamp: DateTime.UtcNow
  }
)
```

**What it does:**
1. Queries next pending ticket from database
2. Updates rounds_state table with lane assignment
3. Returns ticket details

**CLI usage:**
```bash
dotnet run -- workflow dispatch --lane 1
dotnet run -- workflow dispatch --lane 2
```

**Called by:**
- `dispatch` skill (reads from SQLite)
- `rounds` skill (when lane is empty)
- Manual lane management

---

### 5. GenerateStandupAsync()

Generate deterministic standup summary from frozen `.catalog/assigned-work.db` snapshot.

```csharp
var result = await WorkflowOperations.GenerateStandupAsync();
if (result.Success) { /* standup ready */ }
```

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Standup summary generated from snapshot",
  Data: {
    SnapshotPath: ".catalog/assigned-work.db",
    SnapshotTimestamp: DateTime("2026-06-18 17:30:00 UTC"),
    GeneratedAt: DateTime.UtcNow,
    Markdown: "## Standup 2026-06-18\n\n### Today's Tickets\n...",
    Summary: {
      TicketCount: 5,
      WorkLogCount: 3,
      PendingCommentCount: 2,
      PendingPageCount: 1
    }
  }
)
```

**What it does:**
1. Opens frozen snapshot at `.catalog/assigned-work.db`
2. Runs deterministic queries (all results ordered by priority/timestamp)
3. Generates markdown standup template
4. Returns summary statistics

**CLI usage:**
```bash
dotnet run -- workflow standup
```

**Called by:**
- `weekly-summary` skill (to get standup template)
- User for manual standup review
- CI/CD (if publishing standup to Notion)

**Why snapshot-based?**
- Guarantees identical output from same snapshot
- Enables offline standup generation
- No race conditions with live system changes

---

### 6. GetStatusAsync()

Get current workflow status: database initialized, snapshot available, ticket counts, pending syncs.

```csharp
var result = await WorkflowOperations.GetStatusAsync();
if (result.Success) { /* status available */ }
```

**Returns:**
```
OperationResult(
  Success: true,
  Message: "Workflow status retrieved",
  Data: {
    DatabaseStatus: {
      Path: "~/.acestus/workflow.db",
      Initialized: true
    },
    CatalogStatus: {
      Path: ".catalog/assigned-work.db",
      Available: true,
      Timestamp: DateTime("2026-06-18 17:30:00 UTC")
    },
    Tickets: {
      Total: 5,
      Pending: 1,
      InProgress: 2,
      WaitingReview: 1,
      Done: 1
    },
    PendingSyncs: {
      Comments: 2,
      Pages: 1
    },
    Timestamp: DateTime.UtcNow
  }
)
```

**CLI usage:**
```bash
dotnet run -- workflow status
```

**Called by:**
- User for diagnostics
- Health check scripts
- Morning dashboard

---

## Usage Patterns

### Pattern 1: CLI Command Handler

```csharp
var result = await WorkflowOperations.StartMyDayAsync();
if (result.Success) {
    Console.WriteLine($"✅ {result.Message}");
    Console.WriteLine($"   Tickets: {result.Data.PendingTickets}");
} else {
    Console.Error.WriteLine($"❌ {result.Message}");
}
```

### Pattern 2: Skill Integration

```csharp
// In a skill handler
var result = await WorkflowOperations.GenerateStandupAsync();
if (!result.Success) {
    throw new Exception(result.Message);
}
var markdown = result.Data.Markdown;
// ... publish to Notion or output
```

### Pattern 3: Chained Operations

```csharp
// Morning routine
await WorkflowOperations.InitializeDatabaseAsync();
var startResult = await WorkflowOperations.StartMyDayAsync();
if (startResult.Success) {
    var statusResult = await WorkflowOperations.GetStatusAsync();
    // ... show dashboard
}
```

### Pattern 4: CI/CD Integration

```bash
#!/bin/bash
set -e

# After git pull
dotnet run -- workflow start-my-day

# Do work

# Before git push
dotnet run -- workflow end-my-day

# Push triggers CI/CD (which handles Linear/Notion publishing)
git push
```

---

## Error Handling

All operations return structured `OperationResult` objects. No exceptions are thrown except for unexpected system errors.

```csharp
var result = await WorkflowOperations.DispatchNextTicketAsync(99); // Invalid lane
if (!result.Success) {
    // result.Message: "Invalid lane number. Must be 1-5, got 99"
}

var result = await WorkflowOperations.GenerateStandupAsync(); // No snapshot
if (!result.Success) {
    // result.Message: "No local snapshot found. Run 'workflow end-my-day' first."
}
```

---

## Database Paths

- **Main database:** `~/.acestus/workflow.db` (persists across days)
- **Snapshot:** `.catalog/assigned-work.db` (created daily at end-of-day)

---

## Related Files

- **`WorkflowOperations.cs`** - All operations (pure functions)
- **`WorkflowHandler.cs`** - CLI command handlers (thin wrappers around operations)
- **`WorkflowDbContext.cs`** - SQLite ORM layer (Dapper-based queries)
- **`schema.sql`** - Database schema definition

---

## Future Enhancements

1. **Conflict detection**: `StartMyDayAsync()` could detect conflicts between local and remote
2. **Batch operations**: Sync multiple tickets/comments in single transaction
3. **Metrics**: Track operation duration and success rates
4. **Hooks**: Pre/post operation callbacks for extensibility
5. **Dry-run mode**: Test operations without persisting changes
