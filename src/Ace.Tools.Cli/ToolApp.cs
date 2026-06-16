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
        stdout.WriteLine("  github issues [gh issue args...]");
        stdout.WriteLine("  github prs [gh pr args...]");
        stdout.WriteLine("  github review-pr [args...]");
        stdout.WriteLine("  github daily-summary [args...]");
        stdout.WriteLine("  legacy invoke --command <exe> -- [args...]");
    }

    private static void PrintCommandHelp(string command, TextWriter stdout)
    {
        switch (command)
        {
            case "linear":
                stdout.WriteLine("linear");
                stdout.WriteLine();
                stdout.WriteLine("Usage:");
                stdout.WriteLine("  linear get-issue --key <KEY>");
                stdout.WriteLine("  linear search [args...]");
                stdout.WriteLine("  linear set-flow --key <KEY> --flow <queue|active|waiting|done> [--transition]");
                stdout.WriteLine("  linear comment --key <KEY> --comment <text>");
                stdout.WriteLine("  linear create-issue|create-project|dispatch-next [args...]");
                return;
            case "github":
                stdout.WriteLine("github");
                stdout.WriteLine();
                stdout.WriteLine("Usage:");
                stdout.WriteLine("  github issues [gh issue args...]");
                stdout.WriteLine("  github prs [gh pr args...]");
                stdout.WriteLine("  github review-pr [args...]");
                stdout.WriteLine("  github daily-summary [args...]");
                return;
            case "legacy":
                stdout.WriteLine("legacy");
                stdout.WriteLine();
                stdout.WriteLine("Usage:");
                stdout.WriteLine("  legacy invoke --command <exe> -- [args...]");
                return;
            default:
                PrintHelp(stdout);
                return;
        }
    }

    private static int UnknownCommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown command: {command}");
        return 2;
    }

}
