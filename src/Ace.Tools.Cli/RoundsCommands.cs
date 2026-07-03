namespace Ace.Tools.Cli;

internal static class RoundsCommands
{
    private static readonly string[] LaneEmojis = ["", "🟣", "🔵", "🟡", "🟠", "🔴"];

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

        return args[0] switch
        {
            "start" => await StartAsync(args[1..], stdout, stderr, cancellationToken),
            "transition" => await TransitionAsync(args[1..], stdout, stderr, cancellationToken),
            "clear-lane" => await ClearLaneAsync(args[1..], stdout, stderr, cancellationToken),
            "status" => await StatusAsync(stdout, cancellationToken),
            _ => Fail($"Unknown rounds subcommand: {args[0]}", stderr)
        };
    }

    // ---------------------------------------------------------------------------
    // start
    // ---------------------------------------------------------------------------

    private static async Task<int> StartAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || args[0] is "--help" or "-h")
        {
            PrintStartHelp(stdout);
            return 0;
        }

        var laneStr = CommandHelpers.GetOptionValue(args, "--lane");
        var key = CommandHelpers.GetOptionValue(args, "--key");

        if (!int.TryParse(laneStr, out var lane) || lane < 1 || lane > 5)
        {
            return Fail("--lane must be 1–5", stderr);
        }

        var claims = await RoundsDb.GetClaimsAsync(cancellationToken);
        if (claims.TryGetValue(lane, out var existing))
        {
            await stderr.WriteLineAsync($"⛔ {LaneEmojis[lane]} Lane {lane} already claimed ({existing.Key}, since {existing.ClaimedAt}).");
            await stderr.WriteLineAsync($"   Close that tab first, or pick a different lane.");
            return 1;
        }

        // If no key provided, dispatch next
        if (string.IsNullOrWhiteSpace(key))
        {
            var dispatchResult = await LinearCommands.RunAsync(
                ["dispatch-next", "--activate", "--json"],
                TextWriter.Null,
                stderr,
                cancellationToken);

            if (dispatchResult != 0)
            {
                return dispatchResult;
            }

            await stderr.WriteLineAsync("ℹ  Use 'rounds start --lane N --key <KEY>' to claim a specific ticket.");
            return 0;
        }

        var upperKey = key.ToUpperInvariant();
        await RoundsDb.SetClaimAsync(lane, upperKey, cancellationToken);
        await RoundsDb.AppendWorklogAsync(lane, upperKey, "start", null, cancellationToken);

        await stdout.WriteLineAsync($"✓ {LaneEmojis[lane]} Lane {lane} claimed → {upperKey}");
        return 0;
    }

    // ---------------------------------------------------------------------------
    // transition
    // ---------------------------------------------------------------------------

    private static async Task<int> TransitionAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || args[0] is "--help" or "-h")
        {
            PrintTransitionHelp(stdout);
            return 0;
        }

        var laneStr = CommandHelpers.GetOptionValue(args, "--lane");
        var flow = CommandHelpers.GetOptionValue(args, "--flow");

        if (!int.TryParse(laneStr, out var lane) || lane < 1 || lane > 5)
        {
            return Fail("--lane must be 1–5", stderr);
        }

        if (string.IsNullOrWhiteSpace(flow))
        {
            return Fail("--flow is required (done|waiting|blocked|park)", stderr);
        }

        var claims = await RoundsDb.GetClaimsAsync(cancellationToken);
        if (!claims.TryGetValue(lane, out var claim))
        {
            return Fail($"Lane {lane} is not claimed.", stderr);
        }

        var key = claim.Key;

        // Transition the Linear issue state
        if (flow is "done" or "waiting")
        {
            await LinearCommands.RunAsync(
                ["set-flow", "--key", key, "--flow", flow, "--transition"],
                stdout,
                stderr,
                cancellationToken);
        }

        // Release the lane
        await RoundsDb.ClearClaimAsync(lane, cancellationToken);
        await RoundsDb.AppendWorklogAsync(lane, key, $"transition:{flow}", null, cancellationToken);

        await stdout.WriteLineAsync($"✓ {LaneEmojis[lane]} Lane {lane} released. {key} → {flow}");
        return 0;
    }

    // ---------------------------------------------------------------------------
    // clear-lane
    // ---------------------------------------------------------------------------

    private static async Task<int> ClearLaneAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var laneStr = CommandHelpers.GetOptionValue(args, "--lane");
        if (!int.TryParse(laneStr, out var lane) || lane < 1 || lane > 5)
        {
            return Fail("--lane must be 1–5", stderr);
        }

        var claims = await RoundsDb.GetClaimsAsync(cancellationToken);
        var key = claims.TryGetValue(lane, out var claim) ? claim.Key : "?";

        await RoundsDb.ClearClaimAsync(lane, cancellationToken);
        await stdout.WriteLineAsync($"✓ {LaneEmojis[lane]} Lane {lane} cleared ({key}).");
        return 0;
    }

    // ---------------------------------------------------------------------------
    // status
    // ---------------------------------------------------------------------------

    private static async Task<int> StatusAsync(TextWriter stdout, CancellationToken cancellationToken)
    {
        var claims = await RoundsDb.GetClaimsAsync(cancellationToken);

        await stdout.WriteLineAsync("Rounds Status");
        await stdout.WriteLineAsync();

        for (var lane = 1; lane <= 5; lane++)
        {
            if (claims.TryGetValue(lane, out var claim))
            {
                await stdout.WriteLineAsync($"  {LaneEmojis[lane]} Lane {lane}  {claim.Key,-12}  since {claim.ClaimedAt}");
            }
            else
            {
                await stdout.WriteLineAsync($"  {LaneEmojis[lane]} Lane {lane}  (empty)");
            }
        }

        await stdout.WriteLineAsync();
        await stdout.WriteLineAsync($"  Active: {claims.Count}/5  |  WIP limit: 5");
        return 0;
    }

    // ---------------------------------------------------------------------------
    // Help
    // ---------------------------------------------------------------------------

    private static void PrintHelp(TextWriter stdout)
    {
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
        stdout.WriteLine("  rounds clear-lane --lane 3");
        stdout.WriteLine("  rounds status");
        stdout.WriteLine();
        stdout.WriteLine("NOTES");
        stdout.WriteLine("  Claims persist in ~/.ace/rounds.db (survives reboots).");
        stdout.WriteLine("  Stale claims older than 4 hours are auto-expired on read.");
        stdout.WriteLine("  WIP limit: 5 — one active ticket per lane (1–5).");
    }

    private static void PrintStartHelp(TextWriter stdout)
    {
        stdout.WriteLine("rounds start — Claim a lane and activate a ticket");
        stdout.WriteLine();
        stdout.WriteLine("USAGE");
        stdout.WriteLine("  rounds start --lane <1-5> [--key <KEY>]");
        stdout.WriteLine();
        stdout.WriteLine("OPTIONS");
        stdout.WriteLine("  --lane <1-5>   Required. The lane number to claim.");
        stdout.WriteLine("  --key  <KEY>   Optional. Ticket key (e.g., ACE-42). If omitted, dispatches next.");
        stdout.WriteLine();
        stdout.WriteLine("EXAMPLES");
        stdout.WriteLine("  rounds start --lane 1               # auto-dispatch next ticket into lane 1");
        stdout.WriteLine("  rounds start --lane 2 --key ACE-42  # claim lane 2 with a specific ticket");
    }

    private static void PrintTransitionHelp(TextWriter stdout)
    {
        stdout.WriteLine("rounds transition — Move a ticket to a new flow state and release the lane");
        stdout.WriteLine();
        stdout.WriteLine("USAGE");
        stdout.WriteLine("  rounds transition --lane <1-5> --flow <done|waiting|blocked|park>");
        stdout.WriteLine();
        stdout.WriteLine("OPTIONS");
        stdout.WriteLine("  --lane <1-5>                        Required. Lane to transition.");
        stdout.WriteLine("  --flow <done|waiting|blocked|park>  Required. Target flow state.");
        stdout.WriteLine();
        stdout.WriteLine("EXAMPLES");
        stdout.WriteLine("  rounds transition --lane 1 --flow done");
        stdout.WriteLine("  rounds transition --lane 2 --flow waiting");
    }

    private static int Fail(string message, TextWriter stderr)
    {
        stderr.WriteLine($"❌ {message}");
        return 1;
    }
}
