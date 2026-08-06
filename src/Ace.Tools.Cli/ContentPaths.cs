namespace Ace.Tools.Cli;

internal sealed class ContentPaths
{
    public ContentPaths(string? root = null)
    {
        Root = Path.GetFullPath(root ?? Environment.GetEnvironmentVariable("ACE_CONTENT_ROOT") ?? Path.Combine(RepoPaths.FindRepoRoot(), "content-growth"));
        Backlog = Path.Combine(Root, "backlog");
        Articles = Path.Combine(Root, "articles");
        Drafts = Path.Combine(Root, "drafts");
        Youtube = Path.Combine(Drafts, "youtube");
        Shorts = Path.Combine(Drafts, "shorts");
        Social = Path.Combine(Drafts, "social");
        Newsletters = Path.Combine(Drafts, "newsletter");
        Distribution = Path.Combine(Root, "distribution");
        Sources = Path.Combine(Root, "sources");
        Templates = Path.Combine(Root, "templates");
    }

    public string Root { get; }
    public string Backlog { get; }
    public string Articles { get; }
    public string Drafts { get; }
    public string Youtube { get; }
    public string Shorts { get; }
    public string Social { get; }
    public string Newsletters { get; }
    public string Distribution { get; }
    public string Sources { get; }
    public string Templates { get; }

    public string IdeaPath(string id) => Path.Combine(Backlog, $"{id}.json");
    public string DistributionPath(string id) => Path.Combine(Distribution, $"{DateTime.UtcNow:yyyyMMddHHmmss}-{id}.json");

    public void EnsureCreated()
    {
        foreach (var path in new[] { Root, Backlog, Articles, Youtube, Shorts, Social, Newsletters, Distribution, Sources, Templates })
        {
            Directory.CreateDirectory(path);
        }
    }
}
