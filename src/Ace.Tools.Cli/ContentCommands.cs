namespace Ace.Tools.Cli;

public static class ContentCommands
{
    public static Task<int> RunAsync(string[] args, TextWriter stdout, TextWriter stderr)
    {
        try
        {
            return Task.FromResult(Run(args, stdout, stderr));
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ Content error: {ex.Message}");
            return Task.FromResult(1);
        }
    }

    private static int Run(string[] args, TextWriter stdout, TextWriter stderr)
    {
        if (args.Length == 0 || args[0] is "help" or "--help" or "-h")
        {
            PrintHelp(stdout);
            return 0;
        }

        var paths = new ContentPaths();
        var store = new ContentStore(paths);

        return args[0] switch
        {
            "init" => Init(paths, store, stdout),
            "health" => Health(paths, stdout),
            "idea" => Idea(args.Skip(1).ToArray(), store, stdout, stderr),
            "icahn" => Icahn(args.Skip(1).ToArray(), store, stdout, stderr),
            "draft" => Draft(args.Skip(1).ToArray(), store, stdout),
            "distribute" => Distribute(args.Skip(1).ToArray(), store, stdout),
            "self-test" => ContentSelfTest.Run(stdout, stderr),
            _ => Unknown(args[0], stderr)
        };
    }

    private static int Init(ContentPaths paths, ContentStore store, TextWriter stdout)
    {
        store.Initialize();
        stdout.WriteLine("✅ Practical Cloud Systems content workspace initialized");
        stdout.WriteLine($"   Root: {paths.Root}");
        return 0;
    }

    private static int Health(ContentPaths paths, TextWriter stdout)
    {
        var backlogCount = Directory.Exists(paths.Backlog) ? Directory.GetFiles(paths.Backlog, "pcs-*.json").Length : 0;
        var draftCount = Directory.Exists(paths.Drafts) ? Directory.GetFiles(paths.Drafts, "*.md", SearchOption.AllDirectories).Length : 0;
        var distributionCount = Directory.Exists(paths.Distribution) ? Directory.GetFiles(paths.Distribution, "*.json").Length : 0;

        stdout.WriteLine("📣 Practical Cloud Systems Content Health");
        stdout.WriteLine($"  Root: {paths.Root}");
        stdout.WriteLine($"  Backlog ideas: {backlogCount}");
        stdout.WriteLine($"  Draft files: {draftCount}");
        stdout.WriteLine($"  Distribution records: {distributionCount}");
        stdout.WriteLine($"  Initialized: {(Directory.Exists(paths.Backlog) ? "✅ Yes" : "❌ No")}");
        return 0;
    }

    private static int Idea(string[] args, ContentStore store, TextWriter stdout, TextWriter stderr)
    {
        if (args.Length == 0)
        {
            stderr.WriteLine("❌ Missing idea command: add|list|show");
            return 2;
        }

        return args[0] switch
        {
            "add" => AddIdea(args, store, stdout),
            "list" => ListIdeas(store, stdout),
            "show" => ShowIdea(args, store, stdout),
            _ => Unknown($"idea {args[0]}", stderr)
        };
    }

    private static int AddIdea(string[] args, ContentStore store, TextWriter stdout)
    {
        var title = CommandHelpers.GetOptionValue(args, "--title")
            ?? string.Join(' ', args.Skip(1).Where(arg => !arg.StartsWith("--", StringComparison.Ordinal)));
        if (string.IsNullOrWhiteSpace(title))
        {
            throw new InvalidOperationException("Pass a title, for example: content idea add --title \"Cloud engineer roadmap\"");
        }

        var pillar = CommandHelpers.GetOptionValue(args, "--pillar") ?? "Unassigned";
        var viewer = CommandHelpers.GetOptionValue(args, "--viewer") ?? "cloud-curious professional";
        var idea = store.AddIdea(title, pillar, viewer);
        stdout.WriteLine($"✅ Added {idea.Id}: {idea.Title}");
        return 0;
    }

    private static int ListIdeas(ContentStore store, TextWriter stdout)
    {
        var rows = store.ListIdeas()
            .Select(idea => (IReadOnlyList<string>)[idea.Id, idea.Status, idea.Pillar, idea.Icahn.TotalSnapshot.ToString(), CommandHelpers.Truncate(idea.Title, 54)])
            .ToList();
        CommandHelpers.PrintTable(stdout, ["ID", "Status", "Pillar", "Icahn", "Title"], rows);
        return 0;
    }

    private static int ShowIdea(string[] args, ContentStore store, TextWriter stdout)
    {
        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var idea = store.GetIdea(id);
        stdout.WriteLine($"{idea.Id}: {idea.Title}");
        stdout.WriteLine($"Pillar: {idea.Pillar}");
        stdout.WriteLine($"Viewer: {idea.Viewer}");
        stdout.WriteLine($"Hook: {idea.Hook}");
        stdout.WriteLine($"Icahn: {idea.Icahn.TotalSnapshot}/60 ({idea.Icahn.Recommendation})");
        return 0;
    }

    private static int Icahn(string[] args, ContentStore store, TextWriter stdout, TextWriter stderr)
    {
        if (args.Length == 0 || args[0] != "score")
        {
            stderr.WriteLine("❌ Usage: content icahn score --id <pcs-001> [--views N --subs N --demand 1-10 ...]");
            return 2;
        }

        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var idea = store.GetIdea(id);
        idea.Icahn.ViewCount = GetInt(args, "--views", idea.Icahn.ViewCount);
        idea.Icahn.SubscriberCount = GetInt(args, "--subs", idea.Icahn.SubscriberCount);
        idea.Icahn.ViewsPerSubscriber = idea.Icahn.SubscriberCount <= 0 ? 0 : Math.Round((decimal)idea.Icahn.ViewCount / idea.Icahn.SubscriberCount, 2);
        idea.Icahn.Demand = GetScore(args, "--demand", idea.Icahn.Demand);
        idea.Icahn.Pain = GetScore(args, "--pain", idea.Icahn.Pain);
        idea.Icahn.ContentDrivenSignal = GetScore(args, "--content-signal", idea.Icahn.ContentDrivenSignal);
        idea.Icahn.PackagingUpside = GetScore(args, "--packaging-upside", idea.Icahn.PackagingUpside);
        idea.Icahn.Monetization = GetScore(args, "--monetization", idea.Icahn.Monetization);
        idea.Icahn.Repurposing = GetScore(args, "--repurposing", idea.Icahn.Repurposing);
        store.SaveIdea(idea);

        stdout.WriteLine($"✅ Icahn score updated for {idea.Id}");
        stdout.WriteLine($"  Views/subscriber: {idea.Icahn.ViewsPerSubscriber}");
        stdout.WriteLine($"  Total: {idea.Icahn.TotalSnapshot}/60");
        stdout.WriteLine($"  Recommendation: {idea.Icahn.Recommendation}");
        return 0;
    }

    private static int Draft(string[] args, ContentStore store, TextWriter stdout)
    {
        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var idea = store.GetIdea(id);
        var articlePath = store.DraftBundle(idea);
        stdout.WriteLine($"✅ Draft bundle created for {idea.Id}");
        stdout.WriteLine($"   Article: {articlePath}");
        return 0;
    }

    private static int Distribute(string[] args, ContentStore store, TextWriter stdout)
    {
        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var channel = CommandHelpers.GetRequiredOptionValue(args, "--channel");
        var idea = store.GetIdea(id);
        var sourceUrl = CommandHelpers.GetOptionValue(args, "--source-url") ?? string.Empty;
        var notes = CommandHelpers.GetOptionValue(args, "--notes") ?? "planned by CLI";
        var record = store.PlanDistribution(idea, channel, sourceUrl, notes);
        stdout.WriteLine($"✅ Distribution planned: {record.Channel} for {record.IdeaId}");
        stdout.WriteLine("   External posting is intentionally explicit; wire API clients behind this command per channel.");
        return 0;
    }

    private static int GetScore(string[] args, string optionName, int current)
    {
        var value = GetInt(args, optionName, current);
        if (value is < 0 or > 10)
        {
            throw new InvalidOperationException($"{optionName} must be between 0 and 10");
        }

        return value;
    }

    private static int GetInt(string[] args, string optionName, int current)
    {
        var value = CommandHelpers.GetOptionValue(args, optionName);
        return int.TryParse(value, out var parsed) ? parsed : current;
    }

    private static void PrintHelp(TextWriter stdout)
    {
        stdout.WriteLine("Practical Cloud Systems content commands");
        stdout.WriteLine();
        stdout.WriteLine("Usage:");
        stdout.WriteLine("  content init");
        stdout.WriteLine("  content health");
        stdout.WriteLine("  content idea add --title <title> [--pillar <pillar>] [--viewer <viewer>]");
        stdout.WriteLine("  content idea list");
        stdout.WriteLine("  content idea show --id <pcs-001>");
        stdout.WriteLine("  content icahn score --id <pcs-001> --views <n> --subs <n> --demand 1-10 --pain 1-10 --content-signal 1-10 --packaging-upside 1-10 --monetization 1-10 --repurposing 1-10");
        stdout.WriteLine("  content draft --id <pcs-001>");
        stdout.WriteLine("  content distribute --id <pcs-001> --channel <youtube|substack|x|mastodon|linkedin|instagram>");
        stdout.WriteLine("  content self-test");
    }

    private static int Unknown(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown content command: {command}");
        return 2;
    }
}
