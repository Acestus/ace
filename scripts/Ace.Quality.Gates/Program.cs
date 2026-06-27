using System.Diagnostics;

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
        return RunPipeline($"Promote ({environment})", PostflightCommands);
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
        var exitCode = RunCommand(publishCommand);
        if (exitCode != 0)
        {
            return Fail($"Publish failed for environment '{environment}'.");
        }

        Console.WriteLine($"✅ Published artifact to {outputDir}");
        return 0;
    }

    private static int RunPipeline(string name, IEnumerable<string> commands)
    {
        Console.WriteLine($"🚦 {name} quality gate started.");
        foreach (var command in commands)
        {
            var exitCode = RunCommand(command);
            if (exitCode != 0)
            {
                return Fail($"{name} failed while running: {command}");
            }
        }

        Console.WriteLine($"✅ {name} quality gate passed.");
        return 0;
    }

    private static int RunCommand(string command)
    {
        Console.WriteLine($"> {command}");

        var startInfo = CreateShellStartInfo(command);
        using var process = Process.Start(startInfo);
        if (process is null)
        {
            return Fail("Failed to start child process.");
        }

        process.WaitForExit();
        return process.ExitCode;
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
}
