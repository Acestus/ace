namespace Ace.Tools.Cli;

internal static class RepoPaths
{
    public static string FindRepoRoot()
    {
        var overrideRoot = Environment.GetEnvironmentVariable("ACE_REPO_ROOT");
        if (!string.IsNullOrWhiteSpace(overrideRoot) && Directory.Exists(overrideRoot))
        {
            return Path.GetFullPath(overrideRoot);
        }

        foreach (var start in CandidateStartDirectories())
        {
            var resolved = WalkUpForRepoRoot(start);
            if (resolved is not null)
            {
                return resolved;
            }
        }

        return Directory.GetCurrentDirectory();
    }

    public static string GetScriptPath(string scriptName) => Path.Combine(FindRepoRoot(), "scripts", scriptName);

    public static string GetEnvPath() => Path.Combine(FindRepoRoot(), ".env");

    private static IEnumerable<string> CandidateStartDirectories()
    {
        yield return AppContext.BaseDirectory;
        yield return Directory.GetCurrentDirectory();
    }

    private static string? WalkUpForRepoRoot(string start)
    {
        if (string.IsNullOrWhiteSpace(start))
        {
            return null;
        }

        var dir = new DirectoryInfo(Path.GetFullPath(start));
        while (dir is not null)
        {
            var hasScripts = Directory.Exists(Path.Combine(dir.FullName, "scripts"));
            var hasGit = Directory.Exists(Path.Combine(dir.FullName, ".git"));
            var hasReadme = File.Exists(Path.Combine(dir.FullName, "README.md"));
            if (hasScripts && hasGit && hasReadme)
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        return null;
    }
}
