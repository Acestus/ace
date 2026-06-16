using System.Text;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal static class CommandHelpers
{
    public static string? GetOptionValue(string[] args, params string[] names)
    {
        for (var i = 0; i < args.Length - 1; i++)
        {
            foreach (var name in names)
            {
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase))
                {
                    return args[i + 1];
                }
            }
        }

        return null;
    }

    public static string GetRequiredOptionValue(string[] args, params string[] names)
    {
        var value = GetOptionValue(args, names);
        if (!string.IsNullOrWhiteSpace(value))
        {
            return value;
        }

        throw new InvalidOperationException($"Missing required option {names[0]}");
    }

    public static bool HasOption(string[] args, params string[] names)
    {
        foreach (var arg in args)
        {
            foreach (var name in names)
            {
                if (string.Equals(arg, name, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }
        }

        return false;
    }

    public static string[] GetPassthroughArguments(string[] args)
    {
        var passthroughIndex = Array.IndexOf(args, "--");
        return passthroughIndex >= 0 && passthroughIndex + 1 < args.Length
            ? args[(passthroughIndex + 1)..]
            : Array.Empty<string>();
    }

    public static IReadOnlyList<string> GetRepeatableOptionValues(string[] args, string optionName)
    {
        var values = new List<string>();
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (!string.Equals(args[i], optionName, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            values.Add(args[i + 1]);
        }

        return values;
    }

    public static string Truncate(string text, int limit)
    {
        var compact = Regex.Replace((text ?? string.Empty).Trim(), @"\s+", " ");
        if (compact.Length <= limit)
        {
            return compact.Length == 0 ? "—" : compact;
        }

        return compact[..(limit - 1)] + "…";
    }

    public static void PrintTable(TextWriter stdout, IReadOnlyList<string> headers, IReadOnlyList<IReadOnlyList<string>> rows)
    {
        var widths = headers.Select(header => header.Length).ToArray();
        foreach (var row in rows)
        {
            for (var i = 0; i < row.Count; i++)
            {
                widths[i] = Math.Max(widths[i], row[i].Length);
            }
        }

        stdout.WriteLine(string.Join("  ", headers.Select((header, index) => header.PadRight(widths[index]))));
        stdout.WriteLine(string.Join("  ", widths.Select(width => new string('-', width))));
        foreach (var row in rows)
        {
            stdout.WriteLine(string.Join("  ", row.Select((value, index) => value.PadRight(widths[index]))));
        }
    }

    public static string ResolveRepo(string? repo)
    {
        if (!string.IsNullOrWhiteSpace(repo))
        {
            return repo;
        }

        var envRepo = Environment.GetEnvironmentVariable("GH_REPO")?.Trim();
        if (!string.IsNullOrWhiteSpace(envRepo))
        {
            return envRepo;
        }

        var result = LocalCommandRunner.RunCaptureAsync(
            "git",
            ["remote", "get-url", "origin"],
            CancellationToken.None).GetAwaiter().GetResult();

        if (result.ExitCode != 0)
        {
            throw new InvalidOperationException("Unable to determine repo. Set GH_REPO or pass --repo.");
        }

        var remoteUrl = result.Stdout;
        var parsed = ParseRepoFromRemote(remoteUrl);
        if (!string.IsNullOrWhiteSpace(parsed))
        {
            return parsed;
        }

        throw new InvalidOperationException("Unable to parse owner/repo from git remote.");
    }

    private static string ParseRepoFromRemote(string remoteUrl)
    {
        var match = Regex.Match(remoteUrl.Trim(), @"github\.com[:/](?<repo>[^/]+/[^/.]+)(?:\.git)?$");
        if (match.Success)
        {
            return match.Groups["repo"].Value;
        }

        match = Regex.Match(remoteUrl.Trim(), @"^(?<repo>[^/]+/[^/]+)$");
        return match.Success ? match.Groups["repo"].Value : string.Empty;
    }
}
