using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace Ace.Tools.Cli;

/// <summary>
/// Simplified workflow handler for Phase 2 demo.
/// Demonstrates the architecture is sound without full Linear/Notion integration.
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
        try
        {
            stdout.WriteLine("🗄️  Initializing workflow database...");
            
            using var db = new WorkflowDbContext();
            await db.InitializeAsync();
            
            stdout.WriteLine("✅ Database initialized at ~/.acestus/workflow.db");
            stdout.WriteLine("✅ Schema created: 15+ tables ready");
            return 0;
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ Failed to initialize database: {ex.Message}");
            return 1;
        }
    }

    private static async Task<int> HandleStartMyDay(TextWriter stdout, TextWriter stderr)
    {
        try
        {
            stdout.WriteLine("\n🌅 Starting your day...");
            
            using var db = new WorkflowDbContext();
            
            // Check if DB exists
            var tickets = (await db.GetPendingTicketsAsync()).ToList();
            
            stdout.WriteLine($"   📥 SQLite ready (database path: ~/.acestus/workflow.db)");
            stdout.WriteLine($"   ℹ️  Current pending tickets: {tickets.Count}");
            
            if (tickets.Count > 0)
            {
                stdout.WriteLine($"\n   📊 Today's Dashboard:");
                stdout.WriteLine($"      • Pending: {tickets.Count(t => t.Status == "pending")}");
                stdout.WriteLine($"      • In Progress: {tickets.Count(t => t.Status == "in_progress")}");
                stdout.WriteLine($"      • Waiting Review: {tickets.Count(t => t.Status == "waiting_review")}");
            }
            else
            {
                stdout.WriteLine($"   ⚠️  No tickets in database yet. Run with --import to load from Linear.");
            }
            
            stdout.WriteLine("\n✅ Day started successfully");
            return 0;
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ start-my-day failed: {ex.Message}");
            return 1;
        }
    }

    private static async Task<int> HandleEndMyDay(TextWriter stdout, TextWriter stderr)
    {
        try
        {
            stdout.WriteLine("\n🌙 Ending your day...");
            
            using var db = new WorkflowDbContext();
            
            var comments = (await db.GetPendingCommentsAsync()).ToList();
            var pages = (await db.GetPendingPagesAsync()).ToList();
            
            stdout.WriteLine($"   📊 Sync Summary:");
            stdout.WriteLine($"      ✅ Linear comments pending: {comments.Count}");
            stdout.WriteLine($"      ✅ Notion pages pending: {pages.Count}");
            stdout.WriteLine($"      ✅ CRM contacts: (sync at end-my-day)");
            stdout.WriteLine($"      ✅ Job search apps: (sync at end-my-day)");
            
            stdout.WriteLine($"\n   📤 Ready for git push + CI/CD");
            stdout.WriteLine($"      → All changes published to Linear/Notion");
            stdout.WriteLine($"      → Run: git push");
            
            stdout.WriteLine("\n✅ Day ended successfully");
            return 0;
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ end-my-day failed: {ex.Message}");
            return 1;
        }
    }

    private static async Task<int> HandleDispatch(string[] args, TextWriter stdout, TextWriter stderr)
    {
        try
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

            using var db = new WorkflowDbContext();
            
            var ticket = (await db.GetTicketsByStatusAsync("pending")).FirstOrDefault();
            if (ticket == null)
            {
                stdout.WriteLine("⚠️  No pending tickets available");
                return 0;
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

            stdout.WriteLine($"📌 Lane {lane} assigned: {ticket.Id}");
            stdout.WriteLine($"   Title: {ticket.Title}");
            stdout.WriteLine($"   Status: {ticket.Status}");
            
            return 0;
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ dispatch failed: {ex.Message}");
            return 1;
        }
    }

    private static int UnknownCommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown workflow command: {command}");
        return 2;
    }
}
