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
            "linear" => await RunLinearAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "github" => await RunGitHubAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "legacy" => await RunLegacyAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
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
        stdout.WriteLine("  linear create-issue|create-project|sync|dispatch-next [args...]");
        stdout.WriteLine("  github issues [gh issue args...]");
        stdout.WriteLine("  github prs [gh pr args...]");
        stdout.WriteLine("  github review-pr [args...]");
        stdout.WriteLine("  github daily-summary [args...]");
        stdout.WriteLine("  legacy invoke --script <file.py> -- [args...]");
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
                stdout.WriteLine("  linear create-issue|create-project|sync|dispatch-next [args...]");
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
                stdout.WriteLine("  legacy invoke --script <file.py> -- [args...]");
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

    private static async Task<int> RunLinearAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            return UnknownCommand("linear", stderr);
        }

        return args[0] switch
        {
            "get-issue" => await RunPythonScriptAsync("linear_fetch_issue.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "search" => await RunPythonScriptAsync("linear_search.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "set-flow" => await RunPythonScriptAsync("linear_set_flow.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "comment" => await RunPythonScriptAsync("linear_comment.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "create-issue" => await RunPythonScriptAsync("linear_create_issue.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "create-project" => await RunPythonScriptAsync("linear_create_project.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "sync" => await RunPythonScriptAsync("linear_sync.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "dispatch-next" => await RunPythonScriptAsync("linear_dispatch_next.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            _ => UnknownCommand($"linear {args[0]}", stderr)
        };
    }

    private static async Task<int> RunGitHubAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            return UnknownCommand("github", stderr);
        }

        return args[0] switch
        {
            "issues" => await LocalCommandRunner.RunAsync("gh", ["issue", .. args.Skip(1)], stdout, stderr, cancellationToken),
            "prs" => await LocalCommandRunner.RunAsync("gh", ["pr", .. args.Skip(1)], stdout, stderr, cancellationToken),
            "review-pr" => await RunPythonScriptAsync("pr_review.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            "daily-summary" => await RunPythonScriptAsync("gh_pr_daily.py", args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
            _ => UnknownCommand($"github {args[0]}", stderr)
        };
    }

    private static async Task<int> RunLegacyAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length < 2 || !string.Equals(args[0], "invoke", StringComparison.OrdinalIgnoreCase))
        {
            return UnknownCommand("legacy", stderr);
        }

        var script = GetRequiredOptionValue(args.Skip(1).ToArray(), "--script");
        var passthroughIndex = Array.IndexOf(args, "--");
        var passthrough = passthroughIndex >= 0 ? args[(passthroughIndex + 1)..] : Array.Empty<string>();
        return await RunPythonScriptAsync(script, passthrough, stdout, stderr, cancellationToken);
    }

    private static async Task<int> RunPythonScriptAsync(
        string scriptName,
        string[] scriptArgs,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var scriptPath = RepoPaths.GetScriptPath(scriptName);
        if (!File.Exists(scriptPath))
        {
            throw new InvalidOperationException($"Script not found: scripts/{scriptName}");
        }

        return await LocalCommandRunner.RunAsync("python3", [scriptPath, .. scriptArgs], stdout, stderr, cancellationToken);
    }

    private static string GetRequiredOptionValue(string[] args, string optionName)
    {
        for (var i = 0; i < args.Length; i++)
        {
            if (!string.Equals(args[i], optionName, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (i + 1 >= args.Length)
            {
                throw new InvalidOperationException($"Missing value for {optionName}");
            }

            return args[i + 1];
        }

        throw new InvalidOperationException($"Missing required option {optionName}");
    }
}
