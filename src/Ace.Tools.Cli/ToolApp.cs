namespace Ace.Tools.Cli;

public static class ToolApp
{
    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        DotEnvLoader.LoadIfPresent();

        if (args.Length == 0 || IsHelpRequest(args))
        {
            PrintHelp(stdout);
            return 0;
        }

        if (args.Length > 1 && IsHelpRequest(args.Skip(1).ToArray()))
        {
            PrintCommandHelp(args[0], stdout);
            return 0;
        }

        return args[0] switch
        {
            "linear" => await LinearCommands.RunAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "github" => await GitHubCommands.RunAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "legacy" => await LegacyCommands.RunAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "workflow" => await WorkflowHandler.RunAsync(args.Skip(1).ToArray(), stdout, stderr),
            _ => UnknownCommand(args[0], stderr)
        };
    }

    private static bool IsHelpRequest(string[] args) => args.Length > 0 && args[0] is "help" or "--help" or "-h";

    private static void PrintHelp(TextWriter stdout)
    {
        stdout.WriteLine("Ace.Tools.Cli");
        stdout.WriteLine();
        stdout.WriteLine("Usage:");
        stdout.WriteLine("  linear get-issue --key <KEY>");
        stdout.WriteLine("  linear search [args...]");
        stdout.WriteLine("  linear set-flow --key <KEY> --flow <queue|active|waiting|done> [--transition]");
        stdout.WriteLine("  linear comment --key <KEY> --comment <text>");
        stdout.WriteLine("  linear create-issue|create-project|dispatch-next [args...]");
        stdout.WriteLine("  linear start-my-day");
        stdout.WriteLine("  github issues [gh issue args...]");
        stdout.WriteLine("  github prs [gh pr args...]");
        stdout.WriteLine("  github review-pr [args...]");
        stdout.WriteLine("  github daily-summary [args...]");
        stdout.WriteLine("  workflow init-db");
        stdout.WriteLine("  workflow start-my-day");
        stdout.WriteLine("  workflow end-my-day");
        stdout.WriteLine("  workflow dispatch --lane <1-5>");
        stdout.WriteLine("  workflow standup");
        stdout.WriteLine("  legacy invoke --command <exe> -- [args...]");
    }

    private static void PrintCommandHelp(string command, TextWriter stdout)
    {
        switch (command)
        {
            case "workflow":
                stdout.WriteLine("Workflow Commands");
                stdout.WriteLine("Initialize local SQLite database for work management:");
                stdout.WriteLine("  workflow init-db");
                stdout.WriteLine("Refresh database from Linear/Notion/GitHub and show today's dashboard:");
                stdout.WriteLine("  workflow start-my-day");
                stdout.WriteLine("Publish pending changes back to Linear/Notion:");
                stdout.WriteLine("  workflow end-my-day");
                stdout.WriteLine("Dispatch next pending ticket to a lane:");
                stdout.WriteLine("  workflow dispatch --lane <1-5>");
                stdout.WriteLine("Generate standup summary from local snapshot (deterministic, no live queries):");
                stdout.WriteLine("  workflow standup");
                break;
            default:
                stdout.WriteLine($"Unknown command: {command}");
                break;
        }
    }

    private static int UnknownCommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown command: {command}");
        stderr.WriteLine("   Run with 'help' to see available commands");
        return 2;
    }
}
