using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal static class TranscriptCommands
{
    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || args[0] is "--help" or "-h" or "help")
        {
            PrintHelp(stdout);
            return 0;
        }

        var subcommand = args[0].ToLowerInvariant();
        var options = args.Skip(1).ToArray();
        var dbPath = ResolveCatalogDbPath(CommandHelpers.GetOptionValue(options, "--db"));

        return subcommand switch
        {
            "sync" => await SyncAsync(dbPath, options, stdout, cancellationToken),
            "show-ticket" => await ShowTicketAsync(dbPath, options, stdout, cancellationToken),
            "save" or "append-issue" => await SaveAsync(dbPath, options, stdout, cancellationToken),
            _ => Fail($"Unknown transcript subcommand: {subcommand}", stderr)
        };
    }

    internal static void PrintHelp(TextWriter stdout)
    {
        stdout.WriteLine("transcript — Sync and route Copilot transcript context into issue actions");
        stdout.WriteLine();
        stdout.WriteLine("SUBCOMMANDS");
        stdout.WriteLine("  sync           Sync transcript turns from session-store.db into .catalog/catalog.db");
        stdout.WriteLine("  show-ticket    Show transcript turns linked to a ticket key");
        stdout.WriteLine("  save           Append same-day transcript excerpts to issue ## Actions");
        stdout.WriteLine("  append-issue   Alias for save");
        stdout.WriteLine();
        stdout.WriteLine("EXAMPLES");
        stdout.WriteLine("  transcript sync --since 2026-07-01");
        stdout.WriteLine("  transcript show-ticket --key ACE-22 --limit 20");
        stdout.WriteLine("  transcript save --lane 2 --date 2026-07-02");
        stdout.WriteLine("  transcript save --key ACE-24 --dry-run");
    }

    private static async Task<int> SyncAsync(
        string dbPath,
        string[] options,
        TextWriter stdout,
        CancellationToken cancellationToken)
    {
        var since = ParseOptionalDate(CommandHelpers.GetOptionValue(options, "--since"));
        var store = CommandHelpers.GetOptionValue(options, "--session-store");
        var result = await TranscriptService.SyncAsync(dbPath, store, since, cancellationToken);
        await stdout.WriteLineAsync($"✓ Transcript sync complete: {result.TurnCount} turn(s), {result.LinkCount} link(s), {result.SessionCount} session(s).");
        return 0;
    }

    private static async Task<int> ShowTicketAsync(
        string dbPath,
        string[] options,
        TextWriter stdout,
        CancellationToken cancellationToken)
    {
        var key = CommandHelpers.GetRequiredOptionValue(options, "--key").Trim().ToUpperInvariant();
        var limit = ParsePositiveInt(CommandHelpers.GetOptionValue(options, "--limit"), 20, "--limit");
        var turns = await TranscriptService.ListByTicketAsync(dbPath, key, limit, cancellationToken);

        if (turns.Count == 0)
        {
            await stdout.WriteLineAsync($"No transcript turns found for {key}.");
            return 0;
        }

        foreach (var turn in turns)
        {
            var sessionTag = turn.SessionId.Length > 8 ? turn.SessionId[..8] : turn.SessionId;
            var user = CommandHelpers.Truncate(Flatten(turn.UserMessage), 120);
            var assistant = CommandHelpers.Truncate(Flatten(turn.AssistantResponse), 140);
            await stdout.WriteLineAsync($"[{turn.SessionDate:yyyy-MM-dd} {sessionTag} t{turn.TurnIndex}] USER: {user}");
            await stdout.WriteLineAsync($"  ASST: {assistant}");
        }

        return 0;
    }

    private static async Task<int> SaveAsync(
        string dbPath,
        string[] options,
        TextWriter stdout,
        CancellationToken cancellationToken)
    {
        if (CommandHelpers.HasOption(options, "--help", "-h"))
        {
            PrintHelp(stdout);
            return 0;
        }

        var key = await ResolveTargetKeyAsync(options, cancellationToken);
        var date = ParseOptionalDate(CommandHelpers.GetOptionValue(options, "--date")) ?? DateOnly.FromDateTime(DateTime.Today);
        var sessionId = CommandHelpers.GetOptionValue(options, "--session-id");
        var worklogTime = CommandHelpers.GetOptionValue(options, "--worklog") ?? "15m";
        var limit = ParsePositiveInt(CommandHelpers.GetOptionValue(options, "--limit"), 12, "--limit");
        var dryRun = CommandHelpers.HasOption(options, "--dry-run");
        var noSync = CommandHelpers.HasOption(options, "--no-sync");

        if (!noSync)
        {
            var store = CommandHelpers.GetOptionValue(options, "--session-store");
            var syncResult = await TranscriptService.SyncAsync(dbPath, store, date, cancellationToken);
            await stdout.WriteLineAsync($"✓ Transcript sync complete: {syncResult.TurnCount} turn(s), {syncResult.LinkCount} link(s).");
        }

        var turns = await TranscriptService.ListByTicketForDateAsync(dbPath, key, date, limit, sessionId, cancellationToken);
        if (turns.Count == 0)
        {
            await stdout.WriteLineAsync($"No transcript turns found for {key} on {date:yyyy-MM-dd}.");
            return 0;
        }

        var issuePath = ResolveIssuePath(key);
        var entry = BuildActionEntry(key, date, worklogTime, turns);

        if (dryRun)
        {
            await stdout.WriteLineAsync($"[dry-run] Would append transcript context to {issuePath}");
            await stdout.WriteLineAsync(entry);
            return 0;
        }

        var markdown = await File.ReadAllTextAsync(issuePath, cancellationToken);
        var updated = PrependIssueActionEntry(markdown, entry);
        await File.WriteAllTextAsync(issuePath, updated, cancellationToken);
        var relative = Path.GetRelativePath(RepoPaths.FindRepoRoot(), issuePath);
        await stdout.WriteLineAsync($"✓ Appended transcript context to {relative}");
        return 0;
    }

    private static async Task<string> ResolveTargetKeyAsync(string[] options, CancellationToken cancellationToken)
    {
        var key = CommandHelpers.GetOptionValue(options, "--key")?.Trim().ToUpperInvariant();
        if (!string.IsNullOrWhiteSpace(key))
        {
            return key;
        }

        var laneText = CommandHelpers.GetOptionValue(options, "--lane");
        var lane = ParsePositiveInt(laneText, 0, "--lane");
        if (lane < 1 || lane > 5)
        {
            throw new InvalidOperationException("transcript save requires --key <ACE-123> or --lane <1-5>.");
        }

        var claims = await RoundsDb.GetClaimsAsync(cancellationToken);
        if (!claims.TryGetValue(lane, out var claim))
        {
            throw new InvalidOperationException($"No claimed ticket found for lane {lane}.");
        }

        return claim.Key.Trim().ToUpperInvariant();
    }

    private static string ResolveIssuePath(string key)
    {
        var repoRoot = RepoPaths.FindRepoRoot();
        var path = IssueFileLocator.FindIssueFilePath(repoRoot, key);
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            throw new InvalidOperationException($"Issue markdown file not found for {key}.");
        }

        return path;
    }

    private static string ResolveCatalogDbPath(string? value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            return Path.GetFullPath(value);
        }

        return Path.Combine(RepoPaths.FindRepoRoot(), ".catalog", "catalog.db");
    }

    private static int ParsePositiveInt(string? value, int fallback, string optionName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return fallback;
        }

        if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed) && parsed > 0)
        {
            return parsed;
        }

        throw new InvalidOperationException($"{optionName} must be a positive integer.");
    }

    private static DateOnly? ParseOptionalDate(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        if (DateOnly.TryParseExact(value, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var parsed))
        {
            return parsed;
        }

        throw new InvalidOperationException("--date/--since must use YYYY-MM-DD format.");
    }

    private static string BuildActionEntry(string key, DateOnly date, string worklogTime, IReadOnlyList<TranscriptTurn> turns)
    {
        var timestamp = DateTime.Now.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture);
        var sessionCount = turns.Select(turn => turn.SessionId).Distinct(StringComparer.OrdinalIgnoreCase).Count();
        var excerpts = BuildExcerptLines(turns, 8);

        var builder = new StringBuilder();
        builder.AppendLine($"### {timestamp}");
        builder.AppendLine($"WORKLOG ({worklogTime}): Captured Copilot transcript context for {key} ({date:yyyy-MM-dd}).");
        builder.AppendLine($"COMMENT: Captured {turns.Count} transcript turn(s) across {sessionCount} session(s).");
        builder.AppendLine("COMMENT: Transcript excerpts:");
        foreach (var line in excerpts)
        {
            builder.AppendLine(line);
        }

        return builder.ToString().TrimEnd();
    }

    private static IEnumerable<string> BuildExcerptLines(IReadOnlyList<TranscriptTurn> turns, int maxCount)
    {
        return turns
            .Take(maxCount)
            .Select(turn =>
            {
                var sessionTag = turn.SessionId.Length > 8 ? turn.SessionId[..8] : turn.SessionId;
                var user = CommandHelpers.Truncate(Flatten(turn.UserMessage), 140);
                var assistant = CommandHelpers.Truncate(Flatten(turn.AssistantResponse), 180);
                return $"- [{sessionTag} t{turn.TurnIndex}] USER: {user} | ASST: {assistant}";
            });
    }

    private static string PrependIssueActionEntry(string markdown, string actionEntry)
    {
        var sectionPattern = new Regex(@"(^##\s+Actions\s*$\r?\n)", RegexOptions.Multiline);
        if (!sectionPattern.IsMatch(markdown))
        {
            throw new InvalidOperationException("Issue markdown is missing an '## Actions' section.");
        }

        return sectionPattern.Replace(markdown, $"$1{Environment.NewLine}{actionEntry}{Environment.NewLine}{Environment.NewLine}", 1);
    }

    private static string Flatten(string? text) =>
        string.IsNullOrWhiteSpace(text) ? "—" : Regex.Replace(text, @"\s+", " ").Trim();

    private static int Fail(string message, TextWriter stderr)
    {
        stderr.WriteLine($"❌ {message}");
        return 1;
    }
}
