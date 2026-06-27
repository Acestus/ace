using System.Diagnostics;
using System.Text;

namespace Ace.Quality.Gates;

internal static class Program
{
    private static readonly string[] PreflightCommands =
    [
        "dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj --filter \"TestCategory=inner-loop-score|Category=inner-loop-score\"",
        "dotnet build src/Ace.Tools.Cli/Ace.Tools.Cli.csproj --configuration Release"
    ];

    private static readonly string[] PostflightCommands =
    [
        "dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj --filter \"TestCategory=inner-loop-score|Category=inner-loop-score\"",
        "dotnet test tests/Quality.Reqnroll.Score.Tests/Quality.Reqnroll.Score.Tests.csproj --filter \"TestCategory=outer-loop-gherkin-score|Category=outer-loop-gherkin-score\"",
        "dotnet build src/Ace.Tools.Cli/Ace.Tools.Cli.csproj --configuration Release"
    ];

    public static int Main(string[] args)
    {
        if (args.Length == 0)
        {
            PrintUsage();
            return 2;
        }

        var command = args[0].Trim().ToLowerInvariant();
        var environment = ReadOption(args, "--environment");

        return command switch
        {
            "preflight" => RunPipeline("Preflight", PreflightCommands),
            "postflight" => RunPipeline("Postflight", PostflightCommands),
            "promote" => RunPromote(environment),
            "deploy-net-app" => RunDeploy(environment),
            _ => Fail($"Unknown command: {command}")
        };
    }

    private static int RunPromote(string? environment)
    {
        if (string.IsNullOrWhiteSpace(environment))
        {
            return Fail("promote requires --environment <dev|stg|prd>.");
        }

        Console.WriteLine($"🚦 Running promote gate checks for '{environment}'...");
        return RunPipeline($"Promote ({environment})", PostflightCommands, environment);
    }

    private static int RunDeploy(string? environment)
    {
        if (string.IsNullOrWhiteSpace(environment))
        {
            return Fail("deploy-net-app requires --environment <dev|stg|prd>.");
        }

        var outputDir = $"artifacts/ace-tools-cli/{environment}";
        var publishCommand =
            $"dotnet publish src/Ace.Tools.Cli/Ace.Tools.Cli.csproj --configuration Release --output \"{outputDir}\"";

        Console.WriteLine($"🚀 Publishing .NET app artifact for '{environment}'...");
        var result = RunCommand(publishCommand);
        if (result.ExitCode != 0)
        {
            WriteGitHubSummary(
                title: "Deploy .NET App",
                environment: environment,
                results: [result],
                overallExitCode: 1,
                details: $"Artifact output directory: `{outputDir}`");
            return Fail($"Publish failed for environment '{environment}'.");
        }

        Console.WriteLine($"✅ Published artifact to {outputDir}");
        WriteGitHubSummary(
            title: "Deploy .NET App",
            environment: environment,
            results: [result],
            overallExitCode: 0,
            details: $"Artifact output directory: `{outputDir}`");
        return 0;
    }

    private static int RunPipeline(string name, IEnumerable<string> commands, string? environment = null)
    {
        Console.WriteLine($"🚦 {name} quality gate started.");
        var results = new List<CommandResult>();

        foreach (var command in commands)
        {
            var result = RunCommand(command);
            results.Add(result);

            if (result.ExitCode != 0)
            {
                WriteGitHubSummary(
                    title: $"{name} Quality Gate",
                    environment: environment,
                    results: results,
                    overallExitCode: 1);
                return Fail($"{name} failed while running: {command}");
            }
        }

        Console.WriteLine($"✅ {name} quality gate passed.");
        WriteGitHubSummary(
            title: $"{name} Quality Gate",
            environment: environment,
            results: results,
            overallExitCode: 0);
        return 0;
    }

    private static CommandResult RunCommand(string command)
    {
        Console.WriteLine($"> {command}");

        var startedAt = DateTimeOffset.UtcNow;
        var startInfo = CreateShellStartInfo(command);
        using var process = Process.Start(startInfo);
        if (process is null)
        {
            return new CommandResult(command, 1, DateTimeOffset.UtcNow - startedAt);
        }

        process.WaitForExit();
        return new CommandResult(command, process.ExitCode, DateTimeOffset.UtcNow - startedAt);
    }

    private static ProcessStartInfo CreateShellStartInfo(string command)
    {
        if (OperatingSystem.IsWindows())
        {
            return new ProcessStartInfo("cmd", $"/c {command}")
            {
                RedirectStandardOutput = false,
                RedirectStandardError = false,
                UseShellExecute = false
            };
        }

        return new ProcessStartInfo("bash", $"-lc \"{command.Replace("\"", "\\\"")}\"")
        {
            RedirectStandardOutput = false,
            RedirectStandardError = false,
            UseShellExecute = false
        };
    }

    private static string? ReadOption(IReadOnlyList<string> args, string optionName)
    {
        for (var i = 0; i < args.Count - 1; i++)
        {
            if (string.Equals(args[i], optionName, StringComparison.OrdinalIgnoreCase))
            {
                return args[i + 1];
            }
        }

        return null;
    }

    private static void PrintUsage()
    {
        Console.WriteLine("Ace.Quality.Gates");
        Console.WriteLine("Usage:");
        Console.WriteLine("  dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- preflight");
        Console.WriteLine("  dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- postflight");
        Console.WriteLine("  dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- promote --environment <dev|stg|prd>");
        Console.WriteLine("  dotnet run --project scripts/Ace.Quality.Gates/Ace.Quality.Gates.csproj -- deploy-net-app --environment <dev|stg|prd>");
    }

    private static int Fail(string message)
    {
        Console.Error.WriteLine($"❌ {message}");
        return 1;
    }

    private static void WriteGitHubSummary(
        string title,
        string? environment,
        IReadOnlyList<CommandResult> results,
        int overallExitCode,
        string? details = null)
    {
        var summaryPath = Environment.GetEnvironmentVariable("GITHUB_STEP_SUMMARY");
        if (string.IsNullOrWhiteSpace(summaryPath))
        {
            return;
        }

        var branch = Environment.GetEnvironmentVariable("GITHUB_REF_NAME") ?? "local";
        var status = overallExitCode == 0 ? "✅ Passed" : "❌ Failed";
        var markdown = new StringBuilder()
            .AppendLine($"## {title}")
            .AppendLine()
            .AppendLine($"- **Status:** {status}")
            .AppendLine($"- **Branch:** `{branch}`");

        if (!string.IsNullOrWhiteSpace(environment))
        {
            markdown.AppendLine($"- **Environment:** `{environment}`");
        }

        markdown.AppendLine()
            .AppendLine("| Step | Exit | Duration | Command |")
            .AppendLine("| --- | ---: | ---: | --- |");

        for (var i = 0; i < results.Count; i++)
        {
            var result = results[i];
            var stepName = $"Step {i + 1}";
            var duration = $"{result.Duration.TotalSeconds:F1}s";
            var command = EscapePipes(result.Command);
            markdown.AppendLine($"| {stepName} | `{result.ExitCode}` | {duration} | `{command}` |");
        }

        if (!string.IsNullOrWhiteSpace(details))
        {
            markdown.AppendLine()
                .AppendLine($"**Details:** {details}");
        }

        markdown.AppendLine();
        File.AppendAllText(summaryPath, markdown.ToString());
    }

    private static string EscapePipes(string value) => value.Replace("|", "\\|", StringComparison.Ordinal);

    private sealed record CommandResult(string Command, int ExitCode, TimeSpan Duration);
}
