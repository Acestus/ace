using Reqnroll;

namespace Quality.Reqnroll.Score.Tests.Features;

[Binding]
public sealed class QualityScoringSteps
{
    private string? _repoRoot;
    private IReadOnlyList<QualityScoreEngine.FileScore> _scores = Array.Empty<QualityScoreEngine.FileScore>();

    [Given(@"the repository root is discovered")]
    public void GivenTheRepositoryRootIsDiscovered()
    {
        _repoRoot = QualityScoreEngine.DiscoverRepoRoot(AppContext.BaseDirectory);
    }

    [When(@"I score inner-loop tests with the quality rubric")]
    public void WhenIScoreInnerLoopTestsWithTheQualityRubric()
    {
        EnsureRepoRoot();
        _scores = QualityScoreEngine.ScoreInnerLoop(_repoRoot!);
    }

    [Then(@"I write the inner-loop quality reports")]
    public void ThenIWriteTheInnerLoopQualityReports()
    {
        EnsureRepoRoot();
        QualityScoreEngine.WriteInnerLoopReports(_repoRoot!, _scores);
        var markdown = Path.Combine(_repoRoot!, "docs", "testing", "inner-loop-score.md");
        var json = Path.Combine(_repoRoot!, "docs", "testing", "inner-loop-score.json");
        if (!File.Exists(markdown) || !File.Exists(json))
        {
            throw new InvalidOperationException($"Inner-loop report files were not written under {_repoRoot}.");
        }
    }

    [When(@"I score outer-loop Gherkin tests with the quality rubric")]
    public void WhenIScoreOuterLoopGherkinTestsWithTheQualityRubric()
    {
        EnsureRepoRoot();
        _scores = QualityScoreEngine.ScoreOuterLoopGherkin(_repoRoot!);
    }

    [Then(@"I write the outer-loop Gherkin quality reports")]
    public void ThenIWriteTheOuterLoopGherkinQualityReports()
    {
        EnsureRepoRoot();
        QualityScoreEngine.WriteOuterLoopReports(_repoRoot!, _scores);
        var markdown = Path.Combine(_repoRoot!, "docs", "testing", "outer-loop-gherkin-score.md");
        var json = Path.Combine(_repoRoot!, "docs", "testing", "outer-loop-gherkin-score.json");
        if (!File.Exists(markdown) || !File.Exists(json))
        {
            throw new InvalidOperationException($"Outer-loop report files were not written under {_repoRoot}.");
        }
    }

    private void EnsureRepoRoot()
    {
        if (string.IsNullOrWhiteSpace(_repoRoot))
        {
            throw new InvalidOperationException("Repository root must be discovered before scoring.");
        }
    }
}
