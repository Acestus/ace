namespace Ace.Tools.Cli;

public static class JellyfinCommands
{
    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || CommandHelpers.HasOption(args, "--help", "-h") || args[0] is "help")
        {
            PrintHelp(stdout);
            return 0;
        }

        try
        {
            var client = CreateClient();
            return args[0] switch
            {
                "status" => await StatusAsync(client, stdout, cancellationToken),
                "libraries" => await LibrariesAsync(client, stdout, cancellationToken),
                "update-paths" => await UpdatePathsAsync(client, stdout, cancellationToken),
                "remove-library" => await RemoveLibraryAsync(client, args[1..], stdout, cancellationToken),
                "scan" => await ScanAsync(client, stdout, cancellationToken),
                "search" => await SearchAsync(client, args[1..], stdout, cancellationToken),
                "tag" => await TagAsync(client, args[1..], stdout, cancellationToken),
                "collection" => await CollectionAsync(client, args[1..], stdout, cancellationToken),
                _ => Unknown(args[0], stderr)
            };
        }
        catch (Exception ex) when (ex is HttpRequestException or InvalidOperationException or ArgumentException)
        {
            stderr.WriteLine($"Jellyfin error: {ex.Message}");
            return 1;
        }
    }

    public static void PrintHelp(TextWriter stdout)
    {
        stdout.WriteLine("jellyfin — Jellyfin API operations (.NET 11)");
        stdout.WriteLine();
        stdout.WriteLine("Environment:");
        stdout.WriteLine("  JELLYFIN_URL    Server URL (default: http://127.0.0.1:8096)");
        stdout.WriteLine("  JELLYFIN_TOKEN  API token for authenticated operations");
        stdout.WriteLine();
        stdout.WriteLine("Subcommands:");
        stdout.WriteLine("  status");
        stdout.WriteLine("  libraries");
        stdout.WriteLine("  update-paths");
        stdout.WriteLine("  remove-library --name <library-name>");
        stdout.WriteLine("  scan");
        stdout.WriteLine("  search --term <text> [--types Movie,Series]");
        stdout.WriteLine("  tag --id <item-id> --tag <tag> [--tag <tag> ...]");
        stdout.WriteLine("  collection create --name <name>");
        stdout.WriteLine("  collection add --id <collection-id> --item <item-id> [--item <item-id> ...]");
        stdout.WriteLine();
        stdout.WriteLine("Examples:");
        stdout.WriteLine("  jellyfin status");
        stdout.WriteLine("  jellyfin search --term \"Studio Ghibli\" --types Movie");
        stdout.WriteLine("  jellyfin tag --id <id> --tag \"Studio Ghibli\"");
    }

    private static JellyfinClient CreateClient()
    {
        var url = Environment.GetEnvironmentVariable("JELLYFIN_URL") ?? "http://127.0.0.1:8096";
        var token = Environment.GetEnvironmentVariable("JELLYFIN_TOKEN");
        return new JellyfinClient(url, token);
    }

    private static async Task<int> StatusAsync(JellyfinClient client, TextWriter stdout, CancellationToken cancellationToken)
    {
        var info = await client.GetPublicSystemInfoAsync(cancellationToken);
        stdout.WriteLine($"{info.ProductName} {info.Version} — {info.ServerName}");
        stdout.WriteLine($"Local address: {info.LocalAddress}");
        stdout.WriteLine($"Startup wizard completed: {info.StartupWizardCompleted}");
        return 0;
    }

    private static async Task<int> LibrariesAsync(JellyfinClient client, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        foreach (var library in await client.GetLibrariesAsync(cancellationToken))
        {
            stdout.WriteLine($"{library.Name} [{library.CollectionType}]");
            foreach (var location in library.Locations)
            {
                stdout.WriteLine($"  {location}");
            }
        }
        return 0;
    }

    private static async Task<int> UpdatePathsAsync(JellyfinClient client, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        var libraries = await client.GetLibrariesAsync(cancellationToken);
        var updated = 0;
        foreach (var library in libraries)
        {
            foreach (var location in library.Locations)
            {
                if (!location.Contains("/Volumes/movies01", StringComparison.Ordinal))
                {
                    continue;
                }
                var replacement = location.Replace("/Volumes/movies01", "/Volumes/media01", StringComparison.Ordinal);
                await client.UpdateMediaPathAsync(library.Name, replacement, cancellationToken);
                stdout.WriteLine($"Updated {library.Name}: {replacement}");
                updated++;
            }
        }
        stdout.WriteLine($"Updated {updated} library path(s).");
        return 0;
    }

    private static async Task<int> RemoveLibraryAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        var name = CommandHelpers.GetRequiredOptionValue(args, "--name");
        await client.RemoveLibraryAsync(name, refreshLibrary: false, cancellationToken);
        stdout.WriteLine($"Removed Jellyfin library: {name}");
        return 0;
    }

    private static async Task<int> ScanAsync(JellyfinClient client, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        await client.RefreshLibraryAsync(cancellationToken);
        stdout.WriteLine("Jellyfin library refresh requested.");
        return 0;
    }

    private static async Task<int> SearchAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        var term = CommandHelpers.GetRequiredOptionValue(args, "--term");
        var types = CommandHelpers.GetOptionValue(args, "--types");
        foreach (var item in await client.SearchAsync(term, types, cancellationToken))
        {
            stdout.WriteLine($"{item.Id}\t{item.Type}\t{item.Name}");
        }
        return 0;
    }

    private static async Task<int> TagAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var tags = CommandHelpers.GetRepeatableOptionValues(args, "--tag");
        if (tags.Count == 0)
        {
            throw new ArgumentException("At least one --tag is required.");
        }
        await client.UpdateTagsAsync(id, tags, cancellationToken);
        stdout.WriteLine($"Updated tags for {id}: {string.Join(", ", tags)}");
        return 0;
    }

    private static async Task<int> CollectionAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        RequireToken();
        if (args.Length == 0)
        {
            throw new ArgumentException("Use collection create or collection add.");
        }

        return args[0] switch
        {
            "create" => await CreateCollectionAsync(client, args[1..], stdout, cancellationToken),
            "add" => await AddCollectionItemsAsync(client, args[1..], stdout, cancellationToken),
            _ => throw new ArgumentException($"Unknown collection operation: {args[0]}")
        };
    }

    private static async Task<int> CreateCollectionAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        var name = CommandHelpers.GetRequiredOptionValue(args, "--name");
        var collection = await client.CreateCollectionAsync(name, cancellationToken);
        stdout.WriteLine($"{collection.Id}\t{collection.Name}");
        return 0;
    }

    private static async Task<int> AddCollectionItemsAsync(JellyfinClient client, string[] args, TextWriter stdout, CancellationToken cancellationToken)
    {
        var id = CommandHelpers.GetRequiredOptionValue(args, "--id");
        var items = CommandHelpers.GetRepeatableOptionValues(args, "--item");
        if (items.Count == 0)
        {
            throw new ArgumentException("At least one --item is required.");
        }
        await client.AddItemsToCollectionAsync(id, items, cancellationToken);
        stdout.WriteLine($"Added {items.Count} item(s) to collection {id}.");
        return 0;
    }

    private static void RequireToken()
    {
        if (string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("JELLYFIN_TOKEN")))
        {
            throw new InvalidOperationException("Set JELLYFIN_TOKEN for this authenticated Jellyfin operation.");
        }
    }

    private static int Unknown(string command, TextWriter stderr)
    {
        stderr.WriteLine($"Unknown jellyfin command: {command}");
        return 2;
    }
}
