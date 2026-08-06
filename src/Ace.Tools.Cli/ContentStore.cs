using System.Text.Json;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal sealed class ContentStore
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly ContentPaths paths;

    public ContentStore(ContentPaths paths) => this.paths = paths;

    public void Initialize()
    {
        paths.EnsureCreated();
        WriteIfMissing(Path.Combine(paths.Templates, "article.md"), ArticleTemplate());
        WriteIfMissing(Path.Combine(paths.Templates, "youtube-script.md"), YoutubeTemplate());
        WriteIfMissing(Path.Combine(paths.Root, "README.md"), Readme());
    }

    public ContentIdea AddIdea(string title, string pillar, string viewer)
    {
        paths.EnsureCreated();
        var nextId = GetNextId();
        var idea = new ContentIdea
        {
            Id = nextId,
            Title = title.Trim(),
            Slug = Slugify(title),
            Pillar = string.IsNullOrWhiteSpace(pillar) ? "Unassigned" : pillar.Trim(),
            Viewer = viewer.Trim(),
            PrimaryKeyword = title.Trim(),
            Hook = title.Trim(),
            ArticleAngle = $"Explain {title.Trim()} in five practical paragraphs.",
            YoutubeAngle = $"Make {title.Trim()} clear with a practical cloud systems example.",
            ShortsAngle = $"One clear mistake or insight from: {title.Trim()}",
            LinkedinAngle = $"A practical architecture lesson about {title.Trim()}.",
            NewsletterAngle = $"A short field note on {title.Trim()}.",
        };
        SaveIdea(idea);
        return idea;
    }

    public IReadOnlyList<ContentIdea> ListIdeas()
    {
        paths.EnsureCreated();
        return Directory.EnumerateFiles(paths.Backlog, "pcs-*.json")
            .Select(ReadIdeaFile)
            .OrderBy(idea => idea.Priority)
            .ThenByDescending(idea => idea.Icahn.TotalSnapshot)
            .ThenBy(idea => idea.Id)
            .ToList();
    }

    public ContentIdea GetIdea(string id)
    {
        var path = paths.IdeaPath(id);
        if (!File.Exists(path))
        {
            throw new InvalidOperationException($"Content idea not found: {id}");
        }

        return ReadIdeaFile(path);
    }

    public void SaveIdea(ContentIdea idea)
    {
        paths.EnsureCreated();
        idea.UpdatedAt = DateTime.UtcNow;
        idea.Icahn.TotalSnapshot = idea.Icahn.Total;
        idea.Icahn.Recommendation = Recommend(idea.Icahn.TotalSnapshot);
        File.WriteAllText(paths.IdeaPath(idea.Id), JsonSerializer.Serialize(idea, JsonOptions));
    }

    public string DraftBundle(ContentIdea idea)
    {
        paths.EnsureCreated();
        var articlePath = Path.Combine(paths.Articles, $"{idea.Slug}.md");
        var youtubePath = Path.Combine(paths.Youtube, $"{idea.Slug}.md");
        var shortPath = Path.Combine(paths.Shorts, $"{idea.Slug}.md");
        var socialPath = Path.Combine(paths.Social, $"{idea.Slug}.md");
        var newsletterPath = Path.Combine(paths.Newsletters, $"{idea.Slug}.md");

        File.WriteAllText(articlePath, BuildArticle(idea));
        File.WriteAllText(youtubePath, BuildYoutubeScript(idea));
        File.WriteAllText(shortPath, BuildShortScript(idea));
        File.WriteAllText(socialPath, BuildSocialDrafts(idea));
        File.WriteAllText(newsletterPath, BuildNewsletter(idea));

        idea.Status = "drafted";
        SaveIdea(idea);
        return articlePath;
    }

    public DistributionRecord PlanDistribution(ContentIdea idea, string channel, string sourceUrl, string notes)
    {
        paths.EnsureCreated();
        var record = new DistributionRecord
        {
            Id = $"dist-{Guid.NewGuid():N}"[..18],
            IdeaId = idea.Id,
            Channel = channel,
            SourceUrl = sourceUrl,
            Notes = notes,
        };
        File.WriteAllText(paths.DistributionPath(idea.Id), JsonSerializer.Serialize(record, JsonOptions));
        return record;
    }

    private ContentIdea ReadIdeaFile(string path)
    {
        var idea = JsonSerializer.Deserialize<ContentIdea>(File.ReadAllText(path))
            ?? throw new InvalidOperationException($"Invalid content idea JSON: {path}");
        idea.Icahn.TotalSnapshot = idea.Icahn.TotalSnapshot == 0 ? idea.Icahn.Total : idea.Icahn.TotalSnapshot;
        return idea;
    }

    private string GetNextId()
    {
        var max = ListIdeas()
            .Select(idea => int.TryParse(idea.Id.Replace("pcs-", string.Empty), out var number) ? number : 0)
            .DefaultIfEmpty(0)
            .Max();
        return $"pcs-{max + 1:000}";
    }

    private static string Slugify(string title)
    {
        var lower = title.Trim().ToLowerInvariant();
        var slug = Regex.Replace(lower, @"[^a-z0-9]+", "-").Trim('-');
        return string.IsNullOrWhiteSpace(slug) ? $"idea-{Guid.NewGuid():N}"[..13] : slug;
    }

    private static string Recommend(int score) => score switch
    {
        >= 50 => "publish first",
        >= 40 => "strong backlog",
        >= 30 => "needs better hook or packaging",
        > 0 => "skip or merge",
        _ => "unscored"
    };

    private static void WriteIfMissing(string path, string content)
    {
        if (!File.Exists(path))
        {
            File.WriteAllText(path, content);
        }
    }

    private static string ArticleTemplate() => """
# {{title}}

Thesis: {{hook}}

1. Problem / why this matters.
2. What this actually is.
3. Practical architecture decision.
4. Tradeoffs and common mistakes.
5. Recommendation and CTA.
""";

    private static string YoutubeTemplate() => """
# {{title}}

Hook:
Context:
Practical example:
Mistake to avoid:
Recommendation:
CTA:
""";

    private static string Readme() => """
# Practical Cloud Systems Content Growth Engine

File-driven source of truth for content ideas, drafts, newsletter copy, social distribution, and funnel records.

Use `dotnet run --project src/Ace.Tools.Cli -- content help` from the repo root.
""";

    private static string BuildArticle(ContentIdea idea) => $"""
# {idea.Title}

> {idea.Hook}

The practical problem is simple: {Fallback(idea.ArticleAngle, idea.Title)} Cloud teams do not need another abstract overview; they need a clear decision they can use in a real environment.

In practice, this topic matters to {Fallback(idea.Viewer, "cloud engineers and architects")} because it affects reliability, cost, governance, and delivery speed. The useful question is not “what is it?” but “when should I use it, what can go wrong, and what guardrail should I put around it?”

My recommendation is to treat this as an architecture decision, not trivia. Start with the business constraint, choose the simplest cloud pattern that satisfies it, and document the tradeoff so the next engineer can understand why it exists.

The common failure mode is copying a reference architecture without understanding the operational burden. A practical cloud system should be explainable, observable, repeatable, and boring enough to run on a bad Tuesday.

If you want more field notes like this, join the Practical Cloud Systems newsletter. {idea.MonetizationCta}
""";

    private static string BuildYoutubeScript(ContentIdea idea) => $"""
# YouTube Script — {idea.Title}

## Hook
{idea.Hook}

## Setup
Today I’m going to explain {idea.Title} without the vendor fog.

## Main Points
1. What problem this solves.
2. Where teams usually overcomplicate it.
3. The practical cloud systems recommendation.

## Example
Use a small Azure example and show the decision boundary: when this pattern helps, and when it is too much.

## CTA
Subscribe for practical cloud systems: Azure, architecture, DevOps, reliability, and cost control.
""";

    private static string BuildShortScript(ContentIdea idea) => $"""
# Short Script — {idea.Title}

{idea.ShortsAngle}

The mistake: treating this like a tool choice instead of an architecture decision.

The practical rule: if it does not improve reliability, governance, cost, or delivery speed, it is probably complexity.
""";

    private static string BuildSocialDrafts(ContentIdea idea) => $"""
# Social Drafts — {idea.Title}

## LinkedIn
{idea.LinkedinAngle}

{idea.Hook}

The practical test: can the next engineer understand the tradeoff and operate it safely?

## X / Mastodon
{idea.Hook}

Practical cloud rule: architecture is the tradeoff you can still operate during an incident.
""";

    private static string BuildNewsletter(ContentIdea idea) => $"""
# Newsletter — {idea.Title}

This week’s Practical Cloud Systems note: {idea.NewsletterAngle}

{idea.Hook}

The short version: choose the pattern that makes the system easier to operate, not the one that looks most impressive in a diagram.

— Practical Cloud Systems
""";

    private static string Fallback(string value, string fallback) => string.IsNullOrWhiteSpace(value) ? fallback : value;
}
