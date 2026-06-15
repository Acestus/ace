namespace Ace.Tools.Cli;

internal static class DotEnvLoader
{
    private static bool _loaded;

    public static void LoadIfPresent()
    {
        if (_loaded)
        {
            return;
        }

        var envPath = RepoPaths.GetEnvPath();
        if (!File.Exists(envPath))
        {
            _loaded = true;
            return;
        }

        foreach (var rawLine in File.ReadLines(envPath))
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line) || line.StartsWith('#') || !line.Contains('='))
            {
                continue;
            }

            var separator = line.IndexOf('=');
            var key = line[..separator].Trim();
            var value = line[(separator + 1)..].Trim();

            if (string.IsNullOrWhiteSpace(key) || Environment.GetEnvironmentVariable(key) is not null)
            {
                continue;
            }

            Environment.SetEnvironmentVariable(key, value);
        }

        _loaded = true;
    }
}
