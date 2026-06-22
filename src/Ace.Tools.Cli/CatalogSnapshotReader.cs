using System;
using System.Collections.Generic;
using System.Data;
using System.Linq;
using System.Threading.Tasks;
using Dapper;
using Microsoft.Data.Sqlite;

namespace Ace.Tools.Cli;

/// <summary>
/// Queries the local catalog snapshot (.catalog/assigned-work.db) for deterministic standup summaries.
/// Prefers local snapshot over live queries when present.
/// </summary>
public class CatalogSnapshotReader
{
    private readonly string _catalogPath;
    private const string CatalogDb = ".catalog/assigned-work.db";

    public CatalogSnapshotReader(string repoRoot = null)
    {
        var root = repoRoot ?? Environment.CurrentDirectory;
        _catalogPath = Path.Combine(root, CatalogDb);
    }

    public bool IsAvailable => File.Exists(_catalogPath);

    /// <summary>
    /// Gets the snapshot timestamp (when it was created).
    /// </summary>
    public DateTime? GetSnapshotTimestamp()
    {
        if (!IsAvailable) return null;
        try
        {
            return File.GetLastWriteTimeUtc(_catalogPath);
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Gets today's assigned tickets from the local snapshot.
    /// </summary>
    public async Task<IEnumerable<dynamic>> GetTodaysTicketsAsync()
    {
        if (!IsAvailable) return Array.Empty<dynamic>();

        try
        {
            using var connection = new SqliteConnection($"Data Source={_catalogPath};");
            await connection.OpenAsync();

            // Query tickets modified today, ordered by priority
            var today = DateTime.UtcNow.Date;
            var tickets = await connection.QueryAsync<dynamic>(
                @"SELECT id, title, status, priority, swimlane, updated_at
                  FROM tickets
                  WHERE DATE(updated_at) = @Today
                  ORDER BY priority DESC, status DESC, updated_at DESC",
                new { Today = today }
            );

            return tickets.ToList();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"⚠️  Error reading catalog snapshot: {ex.Message}");
            return Array.Empty<dynamic>();
        }
    }

    /// <summary>
    /// Gets pending work logs for standup summary.
    /// </summary>
    public async Task<IEnumerable<dynamic>> GetPendingWorkAsync()
    {
        if (!IsAvailable) return Array.Empty<dynamic>();

        try
        {
            using var connection = new SqliteConnection($"Data Source={_catalogPath};");
            await connection.OpenAsync();

            var today = DateTime.UtcNow.Date.ToString("yyyy-MM-dd");
            var work = await connection.QueryAsync<dynamic>(
                @"SELECT ticket_id, duration_minutes, notes, created_at
                  FROM work_logs
                  WHERE date = @Today
                  ORDER BY created_at DESC",
                new { Today = today }
            );

            return work.ToList();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"⚠️  Error reading work logs: {ex.Message}");
            return Array.Empty<dynamic>();
        }
    }

    /// <summary>
    /// Gets pending comments awaiting publication.
    /// </summary>
    public async Task<IEnumerable<dynamic>> GetPendingCommentsAsync()
    {
        if (!IsAvailable) return Array.Empty<dynamic>();

        try
        {
            using var connection = new SqliteConnection($"Data Source={_catalogPath};");
            await connection.OpenAsync();

            var comments = await connection.QueryAsync<dynamic>(
                @"SELECT id, target_id, content, status, created_at
                  FROM comments_pending
                  WHERE status = 'pending'
                  ORDER BY created_at DESC"
            );

            return comments.ToList();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"⚠️  Error reading pending comments: {ex.Message}");
            return Array.Empty<dynamic>();
        }
    }

    /// <summary>
    /// Gets pending Notion pages awaiting publication.
    /// </summary>
    public async Task<IEnumerable<dynamic>> GetPendingPagesAsync()
    {
        if (!IsAvailable) return Array.Empty<dynamic>();

        try
        {
            using var connection = new SqliteConnection($"Data Source={_catalogPath};");
            await connection.OpenAsync();

            var pages = await connection.QueryAsync<dynamic>(
                @"SELECT id, title, page_type, status, created_at
                  FROM pages_pending
                  WHERE status = 'pending'
                  ORDER BY created_at DESC"
            );

            return pages.ToList();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"⚠️  Error reading pending pages: {ex.Message}");
            return Array.Empty<dynamic>();
        }
    }

    /// <summary>
    /// Gets standup summary from local snapshot (deterministic, no live queries).
    /// </summary>
    public async Task<StandupSummary> GetStandupSummaryAsync()
    {
        var summary = new StandupSummary
        {
            SnapshotTimestamp = GetSnapshotTimestamp(),
            IsFromLocalSnapshot = IsAvailable,
            GeneratedAt = DateTime.UtcNow
        };

        if (!IsAvailable)
        {
            summary.WarningMessage = "⚠️  No local snapshot found. Run 'planner end-my-day' to create one.";
            return summary;
        }

        try
        {
            var tickets = (await GetTodaysTicketsAsync()).ToList();
            var work = (await GetPendingWorkAsync()).ToList();
            var comments = (await GetPendingCommentsAsync()).ToList();
            var pages = (await GetPendingPagesAsync()).ToList();

            summary.TodaysTickets = tickets;
            summary.CompletedWork = work;
            summary.PendingComments = comments;
            summary.PendingPages = pages;

            summary.TicketCount = tickets.Count;
            summary.WorkLogCount = work.Count;
            summary.PendingCommentCount = comments.Count;
            summary.PendingPageCount = pages.Count;
        }
        catch (Exception ex)
        {
            summary.WarningMessage = $"❌ Error reading snapshot: {ex.Message}";
        }

        return summary;
    }

    /// <summary>
    /// Generates a markdown standup summary from the local snapshot.
    /// </summary>
    public async Task<string> GenerateStandupMarkdownAsync()
    {
        var summary = await GetStandupSummaryAsync();

        var lines = new List<string>
        {
            "# Daily Standup",
            $"**Generated:** {summary.GeneratedAt:yyyy-MM-dd HH:mm:ss UTC}",
            ""
        };

        if (summary.IsFromLocalSnapshot)
        {
            lines.Add($"📸 **From Local Snapshot:** {summary.SnapshotTimestamp:yyyy-MM-dd HH:mm:ss UTC}");
            lines.Add("*(Deterministic - no live queries)*");
            lines.Add("");
        }
        else
        {
            lines.Add("⚠️  **No local snapshot** - using live queries (slower)");
            lines.Add("");
        }

        // Work completed
        lines.Add("## Work Completed");
        if (summary.CompletedWork.Any())
        {
            foreach (var work in summary.CompletedWork.Take(10))
            {
                var duration = work.duration_minutes != null ? $"{((int)work.duration_minutes / 60)}h{(int)work.duration_minutes % 60}m" : "0m";
                lines.Add($"- {work.ticket_id}: {work.notes} ({duration})");
            }
        }
        else
        {
            lines.Add("- (no work logged today)");
        }
        lines.Add("");

        // Today's tickets
        lines.Add("## Today's Tickets");
        if (summary.TodaysTickets.Any())
        {
            foreach (var ticket in summary.TodaysTickets.Take(10))
            {
                lines.Add($"- [{ticket.status}] {ticket.id}: {ticket.title}");
            }
        }
        else
        {
            lines.Add("- (no tickets modified today)");
        }
        lines.Add("");

        // Pending syncs
        lines.Add("## Pending Syncs");
        lines.Add($"- Comments: {summary.PendingCommentCount}");
        lines.Add($"- Notion pages: {summary.PendingPageCount}");
        lines.Add("");

        return string.Join("\n", lines);
    }
}

/// <summary>
/// Container for standup summary data.
/// </summary>
public class StandupSummary
{
    public DateTime GeneratedAt { get; set; }
    public DateTime? SnapshotTimestamp { get; set; }
    public bool IsFromLocalSnapshot { get; set; }
    public string? WarningMessage { get; set; }

    public IEnumerable<dynamic> TodaysTickets { get; set; } = Array.Empty<dynamic>();
    public IEnumerable<dynamic> CompletedWork { get; set; } = Array.Empty<dynamic>();
    public IEnumerable<dynamic> PendingComments { get; set; } = Array.Empty<dynamic>();
    public IEnumerable<dynamic> PendingPages { get; set; } = Array.Empty<dynamic>();

    public int TicketCount { get; set; }
    public int WorkLogCount { get; set; }
    public int PendingCommentCount { get; set; }
    public int PendingPageCount { get; set; }
}
