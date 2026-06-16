namespace Ace.Tools.Cli;

internal static class LegacyCommands
{
    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0 || !string.Equals(args[0], "invoke", StringComparison.OrdinalIgnoreCase))
        {
            return Fail("Unknown command: legacy", stderr);
        }

        var command = CommandHelpers.GetOptionValue(args[1..], "--command", "--script");
        if (string.IsNullOrWhiteSpace(command))
        {
            return Fail("Missing required option --command", stderr);
        }

        var passthrough = CommandHelpers.GetPassthroughArguments(args[1..]);
        return await LocalCommandRunner.RunAsync(command, passthrough, stdout, stderr, cancellationToken);
    }

    private static int Fail(string message, TextWriter stderr)
    {
        stderr.WriteLine($"❌ {message}");
        return 1;
    }
}
