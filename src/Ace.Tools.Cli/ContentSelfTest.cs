namespace Ace.Tools.Cli;

internal static class ContentSelfTest
{
    public static int Run(TextWriter stdout, TextWriter stderr)
    {
        var tempRoot = Path.Combine(Path.GetTempPath(), $"ace-content-test-{Guid.NewGuid():N}");
        try
        {
            var paths = new ContentPaths(tempRoot);
            var store = new ContentStore(paths);

            store.Initialize();
            Assert(Directory.Exists(paths.Backlog), "init creates backlog directory");
            Assert(File.Exists(Path.Combine(paths.Templates, "article.md")), "init writes article template");

            var idea = store.AddIdea("What does a cloud engineer actually do?", "Cloud Careers", "cloud beginner");
            Assert(idea.Id == "pcs-001", "first idea id is pcs-001");
            Assert(File.Exists(paths.IdeaPath(idea.Id)), "idea is persisted as text-backed JSON");

            idea.Icahn.ViewCount = 100_000;
            idea.Icahn.SubscriberCount = 1_000;
            idea.Icahn.ViewsPerSubscriber = 100;
            idea.Icahn.Demand = 9;
            idea.Icahn.Pain = 8;
            idea.Icahn.ContentDrivenSignal = 10;
            idea.Icahn.PackagingUpside = 8;
            idea.Icahn.Monetization = 7;
            idea.Icahn.Repurposing = 9;
            store.SaveIdea(idea);

            var scored = store.GetIdea(idea.Id);
            Assert(scored.Icahn.TotalSnapshot == 51, "Icahn score totals six factors");
            Assert(scored.Icahn.Recommendation == "publish first", "high score gets publish-first recommendation");

            var articlePath = store.DraftBundle(scored);
            Assert(File.Exists(articlePath), "draft creates article");
            Assert(File.Exists(Path.Combine(paths.Youtube, $"{scored.Slug}.md")), "draft creates YouTube script");
            Assert(File.Exists(Path.Combine(paths.Social, $"{scored.Slug}.md")), "draft creates social copy");

            var record = store.PlanDistribution(scored, "linkedin", "https://youtube.example/video", "dry run");
            Assert(record.Channel == "linkedin", "distribution records target channel");
            Assert(Directory.GetFiles(paths.Distribution, "*.json").Length == 1, "distribution record is persisted");

            stdout.WriteLine("✅ Content self-test passed");
            stdout.WriteLine("   Tests: init, add idea, Icahn scoring, draft bundle, distribution record");
            return 0;
        }
        catch (Exception ex)
        {
            stderr.WriteLine($"❌ Content self-test failed: {ex.Message}");
            return 1;
        }
        finally
        {
            if (Directory.Exists(tempRoot))
            {
                Directory.Delete(tempRoot, recursive: true);
            }
        }
    }

    private static void Assert(bool condition, string message)
    {
        if (!condition)
        {
            throw new InvalidOperationException(message);
        }
    }
}
