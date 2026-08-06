using System.Text.Json.Serialization;

namespace Ace.Tools.Cli;

public sealed class ContentIdea
{
    public string Id { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Slug { get; set; } = string.Empty;
    public string Pillar { get; set; } = "Unassigned";
    public string PrimaryKeyword { get; set; } = string.Empty;
    public List<string> SecondaryKeywords { get; set; } = [];
    public string Viewer { get; set; } = string.Empty;
    public string Offer { get; set; } = string.Empty;
    public string AuthoritySignal { get; set; } = string.Empty;
    public string Hook { get; set; } = string.Empty;
    public string MonetizationCta { get; set; } = "Join the Practical Cloud Systems newsletter.";
    public string ArticleAngle { get; set; } = string.Empty;
    public string YoutubeAngle { get; set; } = string.Empty;
    public string ShortsAngle { get; set; } = string.Empty;
    public string LinkedinAngle { get; set; } = string.Empty;
    public string NewsletterAngle { get; set; } = string.Empty;
    public List<string> SourceMaterial { get; set; } = [];
    public int Priority { get; set; } = 3;
    public string Status { get; set; } = "backlog";
    public IcahnScore Icahn { get; set; } = new();
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}

public sealed class IcahnScore
{
    public int SubscriberCount { get; set; }
    public int ViewCount { get; set; }
    public decimal ViewsPerSubscriber { get; set; }
    public int Demand { get; set; }
    public int Pain { get; set; }
    public int ContentDrivenSignal { get; set; }
    public int PackagingUpside { get; set; }
    public int Monetization { get; set; }
    public int Repurposing { get; set; }

    [JsonIgnore]
    public int Total => Demand + Pain + ContentDrivenSignal + PackagingUpside + Monetization + Repurposing;

    public int TotalSnapshot { get; set; }
    public string Recommendation { get; set; } = "unscored";
}

public sealed class DistributionRecord
{
    public string Id { get; set; } = string.Empty;
    public string IdeaId { get; set; } = string.Empty;
    public string Channel { get; set; } = string.Empty;
    public string Status { get; set; } = "planned";
    public string SourceUrl { get; set; } = string.Empty;
    public string TargetUrl { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? PostedAt { get; set; }
    public string Notes { get; set; } = string.Empty;
}
