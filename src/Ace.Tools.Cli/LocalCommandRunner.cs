using System.Diagnostics;

namespace Ace.Tools.Cli;

internal static class LocalCommandRunner
{
    public static async Task<int> RunAsync(
        string fileName,
        IReadOnlyList<string> arguments,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var psi = new ProcessStartInfo
        {
            FileName = fileName,
            WorkingDirectory = Directory.GetCurrentDirectory(),
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            UseShellExecute = false
        };

        foreach (var argument in arguments)
        {
            psi.ArgumentList.Add(argument);
        }

        using var process = new Process { StartInfo = psi };
        process.Start();

        var outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        await process.WaitForExitAsync(cancellationToken);

        var output = await outputTask;
        var error = await errorTask;

        if (!string.IsNullOrWhiteSpace(output))
        {
            await stdout.WriteAsync(output);
        }

        if (!string.IsNullOrWhiteSpace(error))
        {
            await stderr.WriteAsync(error);
        }

        return process.ExitCode;
    }
}
