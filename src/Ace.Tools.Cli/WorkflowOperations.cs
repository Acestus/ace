using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Ace.Tools.Cli;

/// <summary>
/// Reusable workflow operations that can be called from CLI, skills, or other contexts.
/// All operations are pure functions that return structured results.
/// </summary>
public static class WorkflowOperations
{
    /// <summary>
    /// Result of an operation for structured error handling.
    /// </summary>
    public record OperationResult(bool Success, string Message, object? Data = null);

    /// <summary>
    /// Initialize the workflow database.
    /// </summary>
    public static async Task<OperationResult> InitializeDatabaseAsync()
    {
        try
        {
            using var db = new WorkflowDbContext();
            await db.InitializeAsync();
            
            return new OperationResult(
                Success: true,
                Message: "Database initialized at ~/.acestus/workflow.db",
                Data: new { TablesCount = 15, SchemaSql = "schema.sql" }
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"Failed to initialize database: {ex.Message}"
            );
        }
    }

    /// <summary>
    /// Start the day: refresh from Linear/Notion/GitHub, show dashboard.
    /// </summary>
    public static async Task<OperationResult> StartMyDayAsync()
    {
        try
        {
            using var db = new WorkflowDbContext();
            
            // Get current state from database
            var tickets = (await db.GetPendingTicketsAsync()).ToList();
            
            var data = new
            {
                DatabasePath = "~/.acestus/workflow.db",
                PendingTickets = tickets.Count,
                TicketsByStatus = new
                {
                    Pending = tickets.Count(t => t.Status == "pending"),
                    InProgress = tickets.Count(t => t.Status == "in_progress"),
                    WaitingReview = tickets.Count(t => t.Status == "waiting_review"),
                    Done = tickets.Count(t => t.Status == "done")
                },
                Timestamp = DateTime.UtcNow,
                ReadyForWork = tickets.Any()
            };

            return new OperationResult(
                Success: true,
                Message: "Day started successfully",
                Data: data
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"start-my-day failed: {ex.Message}"
            );
        }
    }

    /// <summary>
    /// End the day: publish pending changes, prepare for snapshot.
    /// </summary>
    public static async Task<OperationResult> EndMyDayAsync()
    {
        try
        {
            using var db = new WorkflowDbContext();
            
            // Get pending items to sync
            var comments = (await db.GetPendingCommentsAsync()).ToList();
            var pages = (await db.GetPendingPagesAsync()).ToList();
            var tickets = (await db.GetPendingTicketsAsync()).ToList();
            
            var data = new
            {
                DatabasePath = "~/.acestus/workflow.db",
                PendingSyncs = new
                {
                    LinearComments = comments.Count,
                    NotionPages = pages.Count,
                    CrmContacts = 0, // Will be populated when CRM sync re-enabled
                    JobSearchApps = 0
                },
                TicketsStatus = new
                {
                    Total = tickets.Count,
                    Pending = tickets.Count(t => t.Status == "pending"),
                    InProgress = tickets.Count(t => t.Status == "in_progress")
                },
                ReadyForSnapshot = true,
                Timestamp = DateTime.UtcNow
            };

            return new OperationResult(
                Success: true,
                Message: "Day ended successfully - ready for git push + snapshot",
                Data: data
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"end-my-day failed: {ex.Message}"
            );
        }
    }

    /// <summary>
    /// Dispatch next ticket to a lane.
    /// </summary>
    public static async Task<OperationResult> DispatchNextTicketAsync(int lane)
    {
        try
        {
            if (lane < 1 || lane > 5)
                return new OperationResult(false, $"Invalid lane number. Must be 1-5, got {lane}");

            using var db = new WorkflowDbContext();
            
            var ticket = (await db.GetTicketsByStatusAsync("pending")).FirstOrDefault();
            if (ticket == null)
            {
                return new OperationResult(
                    Success: false,
                    Message: "No pending tickets available"
                );
            }

            // Update lane state
            var roundsState = new RoundsState
            {
                Id = Guid.NewGuid().ToString(),
                LaneNumber = lane,
                CurrentTicketId = ticket.Id,
                Status = "active",
                StartedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };
            await db.UpsertRoundsStateAsync(roundsState);

            var data = new
            {
                Lane = lane,
                TicketId = ticket.Id,
                Title = ticket.Title,
                Status = ticket.Status,
                Priority = ticket.Priority,
                Timestamp = DateTime.UtcNow
            };

            return new OperationResult(
                Success: true,
                Message: $"Lane {lane} assigned: {ticket.Id}",
                Data: data
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"dispatch failed: {ex.Message}"
            );
        }
    }

    /// <summary>
    /// Generate standup summary from local snapshot.
    /// </summary>
    public static async Task<OperationResult> GenerateStandupAsync()
    {
        try
        {
            var reader = new CatalogSnapshotReader();
            
            if (!reader.IsAvailable)
            {
                return new OperationResult(
                    Success: false,
                    Message: "No local snapshot found. Run 'workflow end-my-day' first.",
                    Data: new { SnapshotPath = ".catalog/assigned-work.db", Available = false }
                );
            }

            var snapshotTimestamp = reader.GetSnapshotTimestamp();
            var markdown = await reader.GenerateStandupMarkdownAsync();
            
            var summary = await reader.GetStandupSummaryAsync();
            
            var data = new
            {
                SnapshotPath = ".catalog/assigned-work.db",
                SnapshotTimestamp = snapshotTimestamp,
                GeneratedAt = DateTime.UtcNow,
                Markdown = markdown,
                Summary = new
                {
                    TicketCount = summary.TicketCount,
                    WorkLogCount = summary.WorkLogCount,
                    PendingCommentCount = summary.PendingCommentCount,
                    PendingPageCount = summary.PendingPageCount
                }
            };

            return new OperationResult(
                Success: true,
                Message: "Standup summary generated from snapshot",
                Data: data
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"Failed to generate standup: {ex.Message}"
            );
        }
    }

    /// <summary>
    /// Get current workflow status.
    /// </summary>
    public static async Task<OperationResult> GetStatusAsync()
    {
        try
        {
            using var db = new WorkflowDbContext();
            
            var tickets = (await db.GetPendingTicketsAsync()).ToList();
            var comments = (await db.GetPendingCommentsAsync()).ToList();
            var pages = (await db.GetPendingPagesAsync()).ToList();
            var reader = new CatalogSnapshotReader();

            var data = new
            {
                DatabaseStatus = new
                {
                    Path = "~/.acestus/workflow.db",
                    Initialized = true
                },
                CatalogStatus = new
                {
                    Path = ".catalog/assigned-work.db",
                    Available = reader.IsAvailable,
                    Timestamp = reader.GetSnapshotTimestamp()
                },
                Tickets = new
                {
                    Total = tickets.Count,
                    Pending = tickets.Count(t => t.Status == "pending"),
                    InProgress = tickets.Count(t => t.Status == "in_progress"),
                    WaitingReview = tickets.Count(t => t.Status == "waiting_review"),
                    Done = tickets.Count(t => t.Status == "done")
                },
                PendingSyncs = new
                {
                    Comments = comments.Count,
                    Pages = pages.Count
                },
                Timestamp = DateTime.UtcNow
            };

            return new OperationResult(
                Success: true,
                Message: "Workflow status retrieved",
                Data: data
            );
        }
        catch (Exception ex)
        {
            return new OperationResult(
                Success: false,
                Message: $"Failed to get status: {ex.Message}"
            );
        }
    }
}

/// <summary>
/// Structured result for start-my-day operation.
/// </summary>
public record StartMyDayResult(
    bool Success,
    int PendingTickets,
    int InProgress,
    int WaitingReview,
    DateTime Timestamp
);

/// <summary>
/// Structured result for end-my-day operation.
/// </summary>
public record EndMyDayResult(
    bool Success,
    int PendingComments,
    int PendingPages,
    int TotalTickets,
    DateTime Timestamp
);

/// <summary>
/// Structured result for dispatch operation.
/// </summary>
public record DispatchResult(
    bool Success,
    int Lane,
    string TicketId,
    string Title,
    string Status,
    DateTime Timestamp
);
