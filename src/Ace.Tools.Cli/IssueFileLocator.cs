namespace Ace.Tools.Cli;

internal static class IssueFileLocator
{
    public static string? FindIssueFilePath(string repoRoot, string key)
    {
        var issuesRoot = Path.Combine(repoRoot, "issues");
        if (!Directory.Exists(issuesRoot) || string.IsNullOrWhiteSpace(key))
        {
            return null;
        }

        return Directory.EnumerateFiles(issuesRoot, "*.md", SearchOption.AllDirectories)
            .Select(path => new { Path = path, Score = ScoreIssuePath(path, key) })
            .Where(item => item.Score > 0)
            .OrderByDescending(item => item.Score)
            .ThenBy(item => item.Path.Length)
            .Select(item => item.Path)
            .FirstOrDefault();
    }

    private static int ScoreIssuePath(string path, string key)
    {
        var fileName = Path.GetFileName(path);
        if (string.Equals(Path.GetFileName(Path.GetDirectoryName(path)), key, StringComparison.OrdinalIgnoreCase))
        {
            return 3;
        }

        if (fileName.StartsWith(key, StringComparison.OrdinalIgnoreCase))
        {
            return 2;
        }

        return path.Contains($"{Path.DirectorySeparatorChar}{key}{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase) ? 1 : 0;
    }
}
