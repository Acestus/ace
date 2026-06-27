using System.Text.Json;
using System.Text.RegularExpressions;

namespace Quality.Reqnroll.Score.Tests;

internal static class QualityScoreEngine
{
    private static readonly IReadOnlyDictionary<string, double> Weights = new Dictionary<string, double>(StringComparer.Ordinal)
    {
        ["U"] = 1.5,
        ["M"] = 1.5,
        ["R"] = 1.25,
        ["A"] = 1.0,
        ["N"] = 1.0,
        ["G"] = 1.0,
        ["F"] = 0.75,
        ["T"] = 1.0
    };

    private static readonly string[] PropertyOrder = ["U", "M", "R", "A", "N", "G", "F", "T"];

    private static readonly string[] ImplementationDetailTokens =
    [
        "sqlite", "database", "table", "column", "sql", "query", "mock", "verify", "private", "internal"
    ];

    internal static string DiscoverRepoRoot(string? startDirectory = null)
    {
        var rootHint = string.IsNullOrWhiteSpace(startDirectory)
            ? Directory.GetCurrentDirectory()
            : startDirectory;
        var cursor = new DirectoryInfo(rootHint);
        while (cursor is not null)
        {
            if (Directory.Exists(Path.Combine(cursor.FullName, ".git")))
            {
                return cursor.FullName;
            }

            cursor = cursor.Parent;
        }

        throw new InvalidOperationException("Could not locate repository root (.git).");
    }

    internal static IReadOnlyList<FileScore> ScoreInnerLoop(string repoRoot)
    {
        var all = Directory.GetFiles(repoRoot, "*Tests.cs", SearchOption.AllDirectories)
            .Where(path => !IsBuildArtifact(path))
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}Quality.Reqnroll.Score.Tests{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase))
            .Where(path => !Path.GetFileName(path).Contains("Acceptance", StringComparison.OrdinalIgnoreCase))
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}Features{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        return all.Select(ScoreInnerLoopFile).ToArray();
    }

    internal static IReadOnlyList<FileScore> ScoreOuterLoopGherkin(string repoRoot)
    {
        var all = Directory.GetFiles(repoRoot, "*.feature", SearchOption.AllDirectories)
            .Where(path => !IsBuildArtifact(path))
            .Where(path => !path.Contains($"{Path.DirectorySeparatorChar}.git{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase))
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        return all.Select(ScoreFeatureFile).ToArray();
    }

    internal static void WriteInnerLoopReports(string repoRoot, IReadOnlyList<FileScore> scores)
    {
        var generatedAt = DateTimeOffset.UtcNow.ToString("O");
        var outputDir = Path.Combine(repoRoot, "docs", "testing");
        Directory.CreateDirectory(outputDir);
        var markdownPath = Path.Combine(outputDir, "inner-loop-score.md");
        var jsonPath = Path.Combine(outputDir, "inner-loop-score.json");
        File.WriteAllText(markdownPath, BuildInnerMarkdown(scores, generatedAt), System.Text.Encoding.UTF8);
        File.WriteAllText(jsonPath, BuildJson(scores, generatedAt), System.Text.Encoding.UTF8);
    }

    internal static void WriteOuterLoopReports(string repoRoot, IReadOnlyList<FileScore> scores)
    {
        var generatedAt = DateTimeOffset.UtcNow.ToString("O");
        var outputDir = Path.Combine(repoRoot, "docs", "testing");
        Directory.CreateDirectory(outputDir);
        var markdownPath = Path.Combine(outputDir, "outer-loop-gherkin-score.md");
        var jsonPath = Path.Combine(outputDir, "outer-loop-gherkin-score.json");
        File.WriteAllText(markdownPath, BuildOuterMarkdown(scores, generatedAt), System.Text.Encoding.UTF8);
        File.WriteAllText(jsonPath, BuildJson(scores, generatedAt), System.Text.Encoding.UTF8);
    }

    internal static string RelativePath(string repoRoot, string fullPath)
    {
        return Path.GetRelativePath(repoRoot, fullPath).Replace('\\', '/');
    }

    private static FileScore ScoreInnerLoopFile(string path)
    {
        var content = File.ReadAllText(path);
        var methods = Regex.Matches(
                content,
                @"public\s+(?:async\s+)?(?:Task|void)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                RegexOptions.Multiline)
            .Select(match => match.Groups[1].Value)
            .ToArray();

        var testCount = Math.Max(methods.Length, 1);
        var namedBdd = methods.Count(name => Regex.IsMatch(name, @"^Given.+_When.+_Then.+$"));
        var crypticNames = methods.Count(name => Regex.IsMatch(name, @"^(test\d*|it\d*|foo|bar)$", RegexOptions.IgnoreCase));

        var verifyExact = Count(content, @".Verify\(") + Count(content, @"Times\.") + Count(content, @"InOrder") + Count(content, @"verifyNoMoreInteractions");
        var reflection = Count(content, @"GetField\(") + Count(content, @"GetProperty\(") + Count(content, @"BindingFlags");
        var sleepCalls = Count(content, @"Thread\.Sleep\(") + Count(content, @"Task\.Delay\(");
        var fileIo = Count(content, @"File\.") + Count(content, @"Directory\.") + Count(content, @"Path\.");
        var networkIo = Count(content, @"HttpClient") + Count(content, @"HttpRequest") + Count(content, @"WebRequest") + Count(content, @"Socket");
        var nondeterminism = Count(content, @"DateTime\.(Now|UtcNow)") + Count(content, @"Random\(") + Count(content, @"Guid\.NewGuid\(");
        var trivialAssert = Count(content, @"Assert\.True\(\s*true\s*\)") + Count(content, @"Assert\.False\(\s*false\s*\)");
        var assertCalls = Count(content, @"Assert\.[A-Za-z]+\(");
        var multipleAssertPressure = Math.Max(assertCalls - (testCount * 3), 0);
        var staticMutable = Count(content, @"static\s+(?!readonly)[A-Za-z0-9_<>\[\],\s]+\s+[A-Za-z_][A-Za-z0-9_]*\s*[=;]");

        var properties = new Dictionary<string, double>(StringComparer.Ordinal)
        {
            ["U"] = Round(NormalizeSignalDensity(crypticNames, namedBdd, testCount)),
            ["M"] = Round(NormalizeSignalDensity(verifyExact + reflection, namedBdd, testCount)),
            ["R"] = Round(NormalizeSignalDensity(sleepCalls + nondeterminism + networkIo, 0, testCount)),
            ["A"] = Round(NormalizeSignalDensity(staticMutable, namedBdd, testCount)),
            ["N"] = Round(NormalizeSignalDensity(trivialAssert, testCount - trivialAssert, testCount)),
            ["G"] = Round(NormalizeSignalDensity(multipleAssertPressure, testCount, testCount)),
            ["F"] = Round(NormalizeSignalDensity(sleepCalls + fileIo + networkIo, testCount, testCount)),
            ["T"] = Round(NormalizeSignalDensity(verifyExact + reflection, namedBdd, testCount))
        };

        return new FileScore(path, methods.Length, properties, Round(ComputeQuality(properties)));
    }

    private static FileScore ScoreFeatureFile(string path)
    {
        var text = File.ReadAllText(path);
        var scenarioTitles = Regex.Matches(text, @"^\s*Scenario:\s*(.+?)\s*$", RegexOptions.Multiline)
            .Select(match => match.Groups[1].Value)
            .ToArray();
        var givenCount = Regex.Matches(text, @"^\s*Given\s+.+$", RegexOptions.Multiline).Count;
        var whenCount = Regex.Matches(text, @"^\s*When\s+.+$", RegexOptions.Multiline).Count;
        var thenCount = Regex.Matches(text, @"^\s*Then\s+.+$", RegexOptions.Multiline).Count;

        var scenarioCount = scenarioTitles.Length;
        var baseCount = Math.Max(scenarioCount, 1);
        var duplicateTitles = scenarioTitles.Length - scenarioTitles.Distinct(StringComparer.Ordinal).Count();
        var vagueTitles = scenarioTitles.Count(title => title.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length < 5);
        var stepMismatch = Math.Abs(givenCount - scenarioCount) + Math.Abs(whenCount - scenarioCount) + Math.Abs(thenCount - scenarioCount);
        var implDetailHits = ImplementationDetailTokens.Sum(token => Count(text, $@"\b{Regex.Escape(token)}\b", RegexOptions.IgnoreCase));
        var conjunctionHeavy = scenarioTitles.Count(title => Regex.IsMatch(title, @"\b(and|or)\b", RegexOptions.IgnoreCase));
        var hasRuleGrouping = Regex.IsMatch(text, @"^\s*Rule:\s+", RegexOptions.Multiline) ? 1.0 : 0.0;
        var titleDensity = Math.Min(scenarioTitles.Length / 25.0, 1.0);
        var stepCompleteness = Math.Min(Math.Min(givenCount, Math.Min(whenCount, thenCount)) / (double)baseCount, 1.0);

        var negU = (vagueTitles + implDetailHits) / (double)baseCount;
        var posU = stepCompleteness;
        var negM = (duplicateTitles + implDetailHits) / (double)baseCount;
        var posM = hasRuleGrouping;
        var negR = stepMismatch / (double)baseCount;
        var posR = scenarioCount > 0 ? 1.0 : 0.0;
        var negA = conjunctionHeavy / (double)baseCount;
        var posA = stepCompleteness;
        var negN = duplicateTitles / (double)baseCount;
        var posN = titleDensity;
        var negG = conjunctionHeavy / (double)baseCount;
        var posG = stepCompleteness;
        var negF = 0.0;
        var posF = 1.0;
        var negT = implDetailHits / (double)baseCount;
        var posT = stepCompleteness;

        var properties = new Dictionary<string, double>(StringComparer.Ordinal)
        {
            ["U"] = Round(Normalize(negU, posU)),
            ["M"] = Round(Normalize(negM, posM)),
            ["R"] = Round(Normalize(negR, posR)),
            ["A"] = Round(Normalize(negA, posA)),
            ["N"] = Round(Normalize(negN, posN)),
            ["G"] = Round(Normalize(negG, posG)),
            ["F"] = Round(Normalize(negF, posF)),
            ["T"] = Round(Normalize(negT, posT))
        };

        return new FileScore(path, scenarioCount, properties, Round(ComputeQuality(properties)));
    }

    private static bool IsBuildArtifact(string path)
    {
        return path.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
               || path.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
               || path.Contains($"{Path.DirectorySeparatorChar}node_modules{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase);
    }

    private static int Count(string content, string pattern, RegexOptions options = RegexOptions.Multiline)
    {
        return Regex.Matches(content, pattern, options).Count;
    }

    private static double NormalizeSignalDensity(int negatives, int positives, int testCount)
    {
        if (testCount <= 0)
        {
            return 5.0;
        }

        var negDensity = negatives / (double)testCount;
        var posDensity = positives / (double)testCount;
        var negativeComponent = (1.0 - Sigmoid(negDensity)) * 10.0;
        var positiveComponent = Sigmoid(posDensity) * 10.0;
        return Clamp(0.65 * negativeComponent + 0.35 * positiveComponent);
    }

    private static double Normalize(double negatives, double positives)
    {
        var negativeComponent = (1.0 - Sigmoid(negatives)) * 10.0;
        var positiveComponent = Sigmoid(positives) * 10.0;
        return Clamp(0.65 * negativeComponent + 0.35 * positiveComponent);
    }

    private static double ComputeQuality(IReadOnlyDictionary<string, double> properties)
    {
        var weighted = PropertyOrder.Sum(key => properties[key] * Weights[key]);
        return Clamp(weighted / 9.0);
    }

    private static double Sigmoid(double x, double midpoint = 0.15, double steepness = 12.0)
    {
        return 1.0 / (1.0 + Math.Exp(-steepness * (x - midpoint)));
    }

    private static double Clamp(double value, double low = 0.0, double high = 10.0)
    {
        return Math.Max(low, Math.Min(high, value));
    }

    private static double Round(double value) => Math.Round(value, 2, MidpointRounding.AwayFromZero);

    private static string BuildInnerMarkdown(IReadOnlyList<FileScore> scores, string generatedAt)
    {
        if (scores.Count == 0)
        {
            return
                "# Inner-Loop Test Quality Scoring\n\n" +
                $"Generated: {generatedAt}\n\n" +
                "Scope: recursive `*Tests.cs` excluding Acceptance/Features/build artifacts.\n\n" +
                "No matching inner-loop test files were found.\n";
        }

        var overall = Round(scores.Average(score => score.QualityIndex));
        var lines = new List<string>
        {
            "# Inner-Loop Test Quality Scoring",
            "",
            $"Generated: {generatedAt}",
            "",
            "Scope: recursive `*Tests.cs` excluding Acceptance/Features/build artifacts.",
            "",
            "| File | Tests | Quality Index | Rating |",
            "| --- | ---: | ---: | --- |"
        };
        lines.AddRange(scores.Select(score => $"| `{Path.GetFileName(score.Path)}` | {score.TestCount} | {score.QualityIndex:F2} | {Rating(score.QualityIndex)} |"));
        lines.Add("");
        lines.Add($"**Overall Quality Index:** {overall:F2} ({Rating(overall)})");
        lines.Add("");
        lines.Add("## Property Averages (U/M/R/A/N/G/F/T)");
        lines.Add("");
        lines.Add("| U | M | R | A | N | G | F | T |");
        lines.Add("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |");
        lines.Add("| " + string.Join(" | ", PropertyOrder.Select(property => $"{Round(scores.Average(score => score.Properties[property])):F2}")) + " |");
        lines.Add("");
        lines.Add("## Notes");
        lines.Add("");
        lines.Add("- Reqnroll/.NET-native scoring pipeline (no Python dependency).");
        lines.Add("- Excludes Gherkin acceptance scenarios by design.");
        lines.Add("- Use trend and prioritization; do not treat as a hard gate alone.");
        lines.Add("");
        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildOuterMarkdown(IReadOnlyList<FileScore> scores, string generatedAt)
    {
        if (scores.Count == 0)
        {
            return
                "# Outer-Loop Gherkin Quality Scoring\n\n" +
                $"Generated: {generatedAt}\n\n" +
                "No `.feature` files were found in scope.\n";
        }

        var overall = Round(scores.Average(score => score.QualityIndex));
        var lines = new List<string>
        {
            "# Outer-Loop Gherkin Quality Scoring",
            "",
            $"Generated: {generatedAt}",
            "",
            "Scope: `**/*.feature` outer-loop acceptance files.",
            "",
            "| Feature File | Scenarios | Quality Index | Rating |",
            "| --- | ---: | ---: | --- |"
        };
        lines.AddRange(scores.Select(score => $"| `{Path.GetFileName(score.Path)}` | {score.TestCount} | {score.QualityIndex:F2} | {Rating(score.QualityIndex)} |"));
        lines.Add("");
        lines.Add($"**Overall Quality Index:** {overall:F2} ({Rating(overall)})");
        lines.Add("");
        lines.Add("## Property Averages (U/M/R/A/N/G/F/T)");
        lines.Add("");
        lines.Add("| U | M | R | A | N | G | F | T |");
        lines.Add("| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |");
        lines.Add("| " + string.Join(" | ", PropertyOrder.Select(property => $"{Round(scores.Average(score => score.Properties[property])):F2}")) + " |");
        lines.Add("");
        lines.Add("## Notes");
        lines.Add("");
        lines.Add("- Reqnroll/.NET-native scoring pipeline (no Python dependency).");
        lines.Add("- Use alongside executable acceptance tests.");
        lines.Add("- Treat this as trend telemetry, not a standalone quality gate.");
        lines.Add("");
        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildJson(IReadOnlyList<FileScore> scores, string generatedAt)
    {
        var payload = new
        {
            generated_at = generatedAt,
            files = scores.Select(score => new
            {
                path = score.Path.Replace('\\', '/'),
                tests = score.TestCount,
                properties = score.Properties,
                quality_index = score.QualityIndex,
                rating = Rating(score.QualityIndex)
            }),
            overall_quality_index = scores.Count == 0 ? 0.0 : Round(scores.Average(score => score.QualityIndex))
        };

        return JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
    }

    private static string Rating(double score)
    {
        if (score >= 9.0) return "Exemplary";
        if (score >= 7.5) return "Excellent";
        if (score >= 6.0) return "Good";
        if (score >= 4.5) return "Fair";
        if (score >= 3.0) return "Poor";
        return "Critical";
    }

    internal sealed record FileScore(string Path, int TestCount, IReadOnlyDictionary<string, double> Properties, double QualityIndex);
}
