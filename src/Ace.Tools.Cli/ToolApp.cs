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
            "rounds" => await RoundsCommands.RunAsync(args.Skip(1).ToArray(), stdout, stderr, cancellationToken),
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
        stdout.WriteLine("USAGE");
        stdout.WriteLine("  linear get-issue --key <KEY>");
        stdout.WriteLine("  linear search [--state <state>] [--label <label>] [--max <n>]");
        stdout.WriteLine("  linear set-flow --key <KEY> --flow <queue|active|waiting|done> [--transition]");
        stdout.WriteLine("  linear comment --key <KEY> --comment <text>");
        stdout.WriteLine("  linear create-issue --team <TEAM> --title <title> [--label <label>] [--priority <1-4>]");
        stdout.WriteLine("  linear dispatch-next [--activate] [--json]");
        stdout.WriteLine("  rounds start --lane <1-5> [--key <KEY>]");
        stdout.WriteLine("  rounds transition --lane <1-5> --flow <done|waiting|blocked|park>");
        stdout.WriteLine("  rounds clear-lane --lane <1-5>");
        stdout.WriteLine("  rounds status");
        stdout.WriteLine("  github issues [gh issue args...]");
        stdout.WriteLine("  github prs [gh pr args...]");
        stdout.WriteLine("  github review-pr [args...]");
        stdout.WriteLine("  github daily-summary [args...]");
        stdout.WriteLine("  legacy invoke --command <exe> -- [args...]");
        stdout.WriteLine();
        stdout.WriteLine("NOTES");
        stdout.WriteLine("  SQLite state:  ~/.ace/rounds.db  (survives reboots)");
        stdout.WriteLine("  Config:        .env in repo root  (auto-loaded)");
    }

    private static void PrintCommandHelp(string command, TextWriter stdout)
    {
        switch (command)
        {
            case "linear":
                stdout.WriteLine("linear — Linear issue management");
                stdout.WriteLine();
                stdout.WriteLine("SUBCOMMANDS");
                stdout.WriteLine("  get-issue       Fetch a single issue by key");
                stdout.WriteLine("  search          Search issues by state, label, or text");
                stdout.WriteLine("  set-flow        Transition issue to a flow state");
                stdout.WriteLine("  comment         Post a comment to an issue");
                stdout.WriteLine("  create-issue    Create a new Linear issue");
                stdout.WriteLine("  create-project  Create a new Linear project");
                stdout.WriteLine("  dispatch-next   Claim and activate the next unclaimed issue");
                stdout.WriteLine();
                stdout.WriteLine("EXAMPLES");
                stdout.WriteLine("  linear get-issue --key ACE-42");
                stdout.WriteLine("  linear search --state \"In Progress\"");
                stdout.WriteLine("  linear set-flow --key ACE-42 --flow done");
                stdout.WriteLine("  linear dispatch-next --activate --json");
                return;
            case "rounds":
                stdout.WriteLine("rounds — Work session lane management");
                stdout.WriteLine();
                stdout.WriteLine("SUBCOMMANDS");
                stdout.WriteLine("  start           Claim a lane and begin working a ticket");
                stdout.WriteLine("  transition      Move a ticket to done, waiting, blocked, or park");
                stdout.WriteLine("  clear-lane      Release a lane without transitioning the ticket");
                stdout.WriteLine("  status          Show all active lane claims");
                stdout.WriteLine();
                stdout.WriteLine("EXAMPLES");
                stdout.WriteLine("  rounds start --lane 1");
                stdout.WriteLine("  rounds start --lane 2 --key ACE-42");
                stdout.WriteLine("  rounds transition --lane 1 --flow done");
                stdout.WriteLine("  rounds status");
                stdout.WriteLine();
                stdout.WriteLine("NOTES");
                stdout.WriteLine("  Claims persist in ~/.ace/rounds.db. Stale claims (>4h) are auto-expired.");
                stdout.WriteLine("  WIP limit: 5 (one active ticket per lane).");
                return;
            case "github":
                stdout.WriteLine("github — GitHub operations via gh CLI");
                stdout.WriteLine();
                stdout.WriteLine("SUBCOMMANDS");
                stdout.WriteLine("  issues          List or view issues");
                stdout.WriteLine("  prs             List or view pull requests");
                stdout.WriteLine("  review-pr       Review a PR with automated checklist");
                stdout.WriteLine("  daily-summary   Generate yesterday's merged/opened PR digest");
                stdout.WriteLine();
                stdout.WriteLine("EXAMPLES");
                stdout.WriteLine("  github issues list --repo owner/repo");
                stdout.WriteLine("  github prs view 42 --repo owner/repo");
                stdout.WriteLine("  github review-pr --pr 42 --repo owner/repo");
                return;
            case "legacy":
                stdout.WriteLine("legacy — Run legacy scripts");
                stdout.WriteLine();
                stdout.WriteLine("EXAMPLES");
                stdout.WriteLine("  legacy invoke --command python3 -- scripts/my_script.py --key ACE-42");
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
