using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Ace.Tools.Cli;

/// <summary>
/// CLI handler for workflow commands.
/// Delegates to WorkflowOperations for all business logic.
/// </summary>
public static class WorkflowHandler
{
    public static async Task<int> RunAsync(string[] args, TextWriter stdout, TextWriter stderr)
    {
        try
        {
            if (args.Length == 0)
            {
                stderr.WriteLine("❌ No workflow command specified");
                return 1;
            }

            return args[0] switch
            {
                "init-db" => await HandleInitDb(stdout, stderr),
                "start-my-day" => await HandleStartMyDay(stdout, stderr),
                "end-my-day" => await HandleEndMyDay(stdout, stderr),
                "dispatch" => await HandleDispatch(args, stdout, stderr),
                "standup" => await HandleStandup(stdout, stderr),
                "status" => await HandleStatus(stdout, stderr),
                _ => UnknownCommand(args[0], stderr)
            };
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ Workflow error: {ex.Message}");
            return 1;
        }
    }

    private static async Task<int> HandleInitDb(TextWriter stdout, TextWriter stderr)
    {
        stdout.WriteLine("🗄️  Initializing workflow database...");
        var result = await WorkflowOperations.InitializeDatabaseAsync();
        
        if (result.Success)
        {
            stdout.WriteLine($"✅ {result.Message}");
            stdout.WriteLine("✅ Schema created: 15+ tables ready");
            return 0;
        }
        else
        {
            stderr.WriteLine($"❌ {result.Message}");
            return 1;
        }
    }

    private static async Task<int> HandleStartMyDay(TextWriter stdout, TextWriter stderr)
    {
        stdout.WriteLine();
        stdout.WriteLine("🌅 Starting your day...");
        
        var result = await WorkflowOperations.StartMyDayAsync();
        
        if (!result.Success)
        {
            stderr.WriteLine($"❌ {result.Message}");
            return 1;
        }

        if (result.Data is { })
        {
            dynamic data = result.Data;
            stdout.WriteLine($"   📥 SQLite ready (database path: {data.DatabasePath})");
            stdout.WriteLine($"   ℹ️  Current pending tickets: {data.PendingTickets}");
            
            if (data.PendingTickets > 0)
            {
                stdout.WriteLine($"\n   📊 Today's Dashboard:");
                stdout.WriteLine($"      • Pending: {data.TicketsByStatus.Pending}");
                stdout.WriteLine($"      • In Progress: {data.TicketsByStatus.InProgress}");
                stdout.WriteLine($"      • Waiting Review: {data.TicketsByStatus.WaitingReview}");
            }
            else
            {
                stdout.WriteLine($"   ⚠️  No tickets in database yet. Run this command again to pull from Linear.");
            }
        }
        
        stdout.WriteLine("\n✅ Day started successfully");
        return 0;
    }

    private static async Task<int> HandleEndMyDay(TextWriter stdout, TextWriter stderr)
    {
        stdout.WriteLine();
        stdout.WriteLine("🌙 Ending your day...");
        
        var result = await WorkflowOperations.EndMyDayAsync();
        
        if (!result.Success)
        {
            stderr.WriteLine($"❌ {result.Message}");
            return 1;
        }

        if (result.Data is { })
        {
            dynamic data = result.Data;
            stdout.WriteLine($"   📊 Sync Summary:");
            stdout.WriteLine($"      ✅ Linear comments pending: {data.PendingSyncs.LinearComments}");
            stdout.WriteLine($"      ✅ Notion pages pending: {data.PendingSyncs.NotionPages}");
            stdout.WriteLine($"      ✅ CRM contacts: (sync at end-my-day)");
            stdout.WriteLine($"      ✅ Job search apps: (sync at end-my-day)");
            
            stdout.WriteLine($"\n   📤 Ready for git push + CI/CD");
            stdout.WriteLine($"      → All changes published to Linear/Notion");
            stdout.WriteLine($"      → Run: git push");
        }
        
        stdout.WriteLine("\n✅ Day ended successfully");
        return 0;
    }

    private static async Task<int> HandleDispatch(string[] args, TextWriter stdout, TextWriter stderr)
    {
        int lane = 1;
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--lane" && int.TryParse(args[i + 1], out var laneNum))
            {
                lane = laneNum;
                break;
            }
        }

        var result = await WorkflowOperations.DispatchNextTicketAsync(lane);
        
        if (!result.Success)
        {
            stdout.WriteLine($"⚠️  {result.Message}");
            return 0;
        }

        if (result.Data is { })
        {
            dynamic data = result.Data;
            stdout.WriteLine($"📌 Lane {data.Lane} assigned: {data.TicketId}");
            stdout.WriteLine($"   Title: {data.Title}");
            stdout.WriteLine($"   Status: {data.Status}");
        }
        
        return 0;
    }

    private static async Task<int> HandleStandup(TextWriter stdout, TextWriter stderr)
    {
        stdout.WriteLine();
        stdout.WriteLine("📋 Generating standup summary...");
        
        var result = await WorkflowOperations.GenerateStandupAsync();
        
        if (!result.Success)
        {
            stdout.WriteLine($"⚠️  {result.Message}");
            return 0;
        }

        if (result.Data is { })
        {
            dynamic data = result.Data;
            if (data.SnapshotTimestamp != null)
            {
                stdout.WriteLine($"📸 Using local snapshot: {data.SnapshotTimestamp:yyyy-MM-dd HH:mm:ss UTC}");
            }
            
            if (!string.IsNullOrEmpty(data.Markdown))
            {
                stdout.WriteLine("");
                stdout.WriteLine(data.Markdown);
            }
        }
        
        return 0;
    }

    private static async Task<int> HandleStatus(TextWriter stdout, TextWriter stderr)
    {
        stdout.WriteLine();
        stdout.WriteLine("📊 Workflow Status");
        stdout.WriteLine("═══════════════════════════════════════════");
        
        var result = await WorkflowOperations.GetStatusAsync();
        
        if (!result.Success)
        {
            stderr.WriteLine($"❌ {result.Message}");
            return 1;
        }

        if (result.Data is { })
        {
            dynamic data = result.Data;
            
            stdout.WriteLine();
            stdout.WriteLine("Database:");
            stdout.WriteLine($"  Path: {data.DatabaseStatus.Path}");
            stdout.WriteLine($"  Initialized: {(data.DatabaseStatus.Initialized ? "✅ Yes" : "❌ No")}");
            
            stdout.WriteLine();
            stdout.WriteLine("Catalog Snapshot:");
            stdout.WriteLine($"  Path: {data.CatalogStatus.Path}");
            stdout.WriteLine($"  Available: {(data.CatalogStatus.Available ? "✅ Yes" : "❌ No")}");
            if (data.CatalogStatus.Timestamp != null)
            {
                stdout.WriteLine($"  Created: {data.CatalogStatus.Timestamp:yyyy-MM-dd HH:mm:ss UTC}");
            }
            
            stdout.WriteLine();
            stdout.WriteLine("Tickets:");
            stdout.WriteLine($"  Total: {data.Tickets.Total}");
            stdout.WriteLine($"  Pending: {data.Tickets.Pending}");
            stdout.WriteLine($"  In Progress: {data.Tickets.InProgress}");
            stdout.WriteLine($"  Waiting Review: {data.Tickets.WaitingReview}");
            stdout.WriteLine($"  Done: {data.Tickets.Done}");
            
            stdout.WriteLine();
            stdout.WriteLine("Pending Syncs:");
            stdout.WriteLine($"  Comments: {data.PendingSyncs.Comments}");
            stdout.WriteLine($"  Pages: {data.PendingSyncs.Pages}");
            
            stdout.WriteLine();
        }
        
        return 0;
    }

    private static int UnknownCommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown workflow command: {command}");
        return 2;
    }
}
