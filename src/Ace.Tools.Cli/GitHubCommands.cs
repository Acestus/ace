using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace Ace.Tools.Cli;

internal static class GitHubCommands
{
    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            return Fail("Unknown command: github", stderr);
        }

        return args[0] switch
        {
            "issues" => await LocalCommandRunner.RunAsync("gh", ["issue", .. args[1..]], stdout, stderr, cancellationToken),
            "prs" => await LocalCommandRunner.RunAsync("gh", ["pr", .. args[1..]], stdout, stderr, cancellationToken),
            "review-pr" => await RunReviewHelperAsync(args[1..], stdout, stderr, cancellationToken),
            "daily-summary" => await RunDailySummaryAsync(args[1..], stdout, stderr, cancellationToken),
            _ => Fail($"Unknown command: github {args[0]}", stderr)
        };
    }

    private static async Task<int> RunReviewHelperAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var repo = CommandHelpers.ResolveRepo(CommandHelpers.GetOptionValue(args, "--repo"));
        var body = CommandHelpers.GetOptionValue(args, "--body");
        var squash = CommandHelpers.HasOption(args, "--squash");

        if (CommandHelpers.HasOption(args, "--list"))
        {
            return await ListPrsAsync(repo, stdout, stderr, cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--view"), out var viewNumber))
        {
            return await ViewPrAsync(repo, viewNumber, stdout, stderr, cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--checks"), out var checksNumber))
        {
            return await RunPassthroughAsync(new[] { "gh", "pr", "checks", checksNumber.ToString(), "--repo", repo }, "Checks displayed", stdout, stderr, cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--approve"), out var approveNumber))
        {
            var command = new List<string> { "gh", "pr", "review", approveNumber.ToString(), "--repo", repo, "--approve" };
            if (!string.IsNullOrWhiteSpace(body))
            {
                command.AddRange(new[] { "--body", body });
            }
            return await RunPassthroughAsync(command, "Review submitted", stdout, stderr, cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--request-changes"), out var changesNumber))
        {
            if (string.IsNullOrWhiteSpace(body))
            {
                return Fail("--request-changes requires --body", stderr);
            }

            return await RunPassthroughAsync(
                new[] { "gh", "pr", "review", changesNumber.ToString(), "--repo", repo, "--request-changes", "--body", body },
                "Changes requested",
                stdout,
                stderr,
                cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--comment"), out var commentNumber))
        {
            if (string.IsNullOrWhiteSpace(body))
            {
                return Fail("--comment requires --body", stderr);
            }

            return await RunPassthroughAsync(
                new[] { "gh", "pr", "review", commentNumber.ToString(), "--repo", repo, "--comment", "--body", body },
                "Comment submitted",
                stdout,
                stderr,
                cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--diff"), out var diffNumber))
        {
            return await RunPassthroughAsync(new[] { "gh", "pr", "diff", diffNumber.ToString(), "--repo", repo }, "Diff displayed", stdout, stderr, cancellationToken);
        }

        if (int.TryParse(CommandHelpers.GetOptionValue(args, "--merge"), out var mergeNumber))
        {
            var command = new List<string> { "gh", "pr", "merge", mergeNumber.ToString(), "--repo", repo };
            command.Add(squash ? "--squash" : "--merge");
            return await RunPassthroughAsync(command, "Merge requested", stdout, stderr, cancellationToken);
        }

        await stdout.WriteLineAsync("Usage: github review-pr [--list|--view N|--checks N|--approve N|--request-changes N|--comment N|--diff N|--merge N]");
        return 1;
    }

    private static async Task<int> ListPrsAsync(string repo, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var (exitCode, output, error) = await LocalCommandRunner.RunCaptureAsync(
            "gh",
            ["pr", "list", "--repo", repo, "--json", "number,title,state,author,headRefName,reviewDecision,statusCheckRollup"],
            cancellationToken);
        if (exitCode != 0)
        {
            return Fail(FirstNonEmpty(error, output, "gh pr list failed"), stderr);
        }

        var data = JsonDocument.Parse(output).RootElement;
        var rows = new List<IReadOnlyList<string>>();
        foreach (var item in data.EnumerateArray())
        {
            rows.Add(
                [
                    GetNumber(item, "number").ToString(),
                    GetString(item, "state"),
                    ReviewSymbol(GetString(item, "reviewDecision")),
                    SummarizeChecks(item.GetProperty("statusCheckRollup")),
                    CommandHelpers.Truncate(GetString(item.GetProperty("author"), "login"), 16),
                    CommandHelpers.Truncate(GetString(item, "headRefName"), 24),
                    CommandHelpers.Truncate(GetString(item, "title"), 70)
                ]);
        }

        if (rows.Count == 0)
        {
            await stdout.WriteLineAsync("⚠ No pull requests found");
            return 0;
        }

        CommandHelpers.PrintTable(stdout, ["NUMBER", "STATE", "REVIEW", "CI", "AUTHOR", "BRANCH", "TITLE"], rows);
        await stdout.WriteLineAsync($"✓ Listed {rows.Count} pull request(s)");
        return 0;
    }

    private static async Task<int> ViewPrAsync(string repo, int number, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var (exitCode, output, error) = await LocalCommandRunner.RunCaptureAsync(
            "gh",
            ["pr", "view", number.ToString(), "--repo", repo, "--json", "number,title,body,state,author,commits,files,reviewDecision,statusCheckRollup,comments"],
            cancellationToken);
        if (exitCode != 0)
        {
            return Fail(FirstNonEmpty(error, output, "gh pr view failed"), stderr);
        }

        var item = JsonDocument.Parse(output).RootElement;
        await stdout.WriteLineAsync($"Title           : {GetString(item, "title")}");
        await stdout.WriteLineAsync($"State           : {GetString(item, "state")}");
        await stdout.WriteLineAsync($"Author          : {GetString(item.GetProperty("author"), "login")}");
        var reviewDecision = GetString(item, "reviewDecision");
        await stdout.WriteLineAsync($"Review decision : {(string.IsNullOrWhiteSpace(reviewDecision) ? "—" : reviewDecision)} ({ReviewSymbol(reviewDecision)})");
        await stdout.WriteLineAsync($"CI status       : {SummarizeChecks(item.GetProperty("statusCheckRollup"))}");
        await stdout.WriteLineAsync($"Changed files   : {item.GetProperty("files").GetArrayLength()}");
        await stdout.WriteLineAsync($"Body excerpt    : {CommandHelpers.Truncate(GetString(item, "body"), 500)}");
        await stdout.WriteLineAsync("✓ PR details loaded");
        return 0;
    }

    private static async Task<int> RunDailySummaryAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var org = CommandHelpers.GetOptionValue(args, "--org") ?? "<GITHUB_ORG>";
        var date = ResolveTargetDate(CommandHelpers.GetOptionValue(args, "--date"));
        var publish = CommandHelpers.HasOption(args, "--publish");
        var report = CommandHelpers.HasOption(args, "--report") || !publish;
        var pageId = CommandHelpers.GetOptionValue(args, "--page-id") ?? Environment.GetEnvironmentVariable("GH_PR_DAILY_PAGE_ID")?.Trim() ?? string.Empty;

        await stdout.WriteLineAsync($"📋 Fetching PRs for {date:yyyy-MM-dd} from {org}...");
        var merged = await FetchPrsAsync(org, date, "merged-at", cancellationToken);
        var opened = await FetchOpenPrsAsync(org, date, cancellationToken);
        await stdout.WriteLineAsync($"  Found {merged.Count} merged, {opened.Count} opened");

        if (publish)
        {
            if (string.IsNullOrWhiteSpace(pageId))
            {
                return Fail("--page-id required or set GH_PR_DAILY_PAGE_ID", stderr);
            }

            return await PublishReportAsync(merged, opened, date, pageId, stdout, stderr, cancellationToken);
        }

        if (report)
        {
            await stdout.WriteAsync(BuildSummary(merged, opened, date));
            await stdout.WriteLineAsync($"✓ {merged.Count + opened.Count} PR(s) summarized for {date:yyyy-MM-dd}");
        }

        return 0;
    }

    private static async Task<int> PublishReportAsync(
        IReadOnlyList<JsonElement> merged,
        IReadOnlyList<JsonElement> opened,
        DateOnly date,
        string pageId,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var summary = BuildSummary(merged, opened, date);
        var email = Environment.GetEnvironmentVariable("CONFLUENCE_EMAIL")?.Trim() ?? string.Empty;
        var token = Environment.GetEnvironmentVariable("WWEEKS_CONFLUENCE_API_TOKEN")?.Trim() ?? string.Empty;
        var baseUrl = (Environment.GetEnvironmentVariable("CONFLUENCE_BASE_URL")?.Trim() ?? "https://<YOUR_ATLASSIAN>.atlassian.net/wiki").TrimEnd('/');

        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(token))
        {
            return Fail("Set CONFLUENCE_EMAIL and WWEEKS_CONFLUENCE_API_TOKEN in .env or environment", stderr);
        }

        var auth = Convert.ToBase64String(Encoding.UTF8.GetBytes($"{email}:{token}"));
        using var client = new HttpClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Basic", auth);
        client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));

        var page = await GetConfluencePageAsync(client, baseUrl, pageId, cancellationToken);
        var updatedBody = MarkdownToParagraphs(summary) + "\n<hr />\n" + page.Body;
        var payload = new
        {
            id = pageId,
            status = "current",
            title = page.Title,
            version = new { number = page.Version + 1 },
            body = new { storage = new { value = updatedBody, representation = "storage" } }
        };

        var response = await client.PutAsync(
            $"{baseUrl}/api/v2/pages/{pageId}",
            new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json"),
            cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            return Fail($"HTTP {(int)response.StatusCode} while publishing PR summary", stderr);
        }

        await stdout.WriteLineAsync($"✓ Published to Confluence page {pageId}");
        await stdout.WriteLineAsync($"  {baseUrl}/spaces/<SPACE>/pages/{pageId}");
        return 0;
    }

    private static async Task<List<JsonElement>> FetchPrsAsync(string org, DateOnly date, string dateField, CancellationToken cancellationToken)
    {
        var command = new[] { "gh", "search", "prs", "--owner", org, $"--{dateField}", date.ToString("yyyy-MM-dd"), "--json", "number,title,author,repository,url,createdAt,closedAt,state", "--limit", "200" };
        var result = await LocalCommandRunner.RunCaptureAsync("gh", command.ToArray(), cancellationToken);
        var output = result.Stdout;
        var json = JsonDocument.Parse(output).RootElement;
        var results = new List<JsonElement>();
        foreach (var item in json.EnumerateArray())
        {
            results.Add(item.Clone());
        }

        return results;
    }

    private static async Task<List<JsonElement>> FetchOpenPrsAsync(string org, DateOnly date, CancellationToken cancellationToken)
    {
        var command = new[] { "gh", "search", "prs", "--owner", org, "--created", date.ToString("yyyy-MM-dd"), "--state", "open", "--json", "number,title,author,repository,url,createdAt,closedAt,state", "--limit", "200" };
        var result = await LocalCommandRunner.RunCaptureAsync("gh", command.ToArray(), cancellationToken);
        var output = result.Stdout;
        var json = JsonDocument.Parse(output).RootElement;
        var results = new List<JsonElement>();
        foreach (var item in json.EnumerateArray())
        {
            results.Add(item.Clone());
        }

        return results;
    }

    private static string BuildSummary(IReadOnlyList<JsonElement> mergedPrs, IReadOnlyList<JsonElement> openedPrs, DateOnly date)
    {
        var lines = new List<string>
        {
            $"## PR Summary — {date:dddd, MMMM d, yyyy}",
            string.Empty
        };

        if (mergedPrs.Count == 0 && openedPrs.Count == 0)
        {
            lines.Add("*No pull requests merged or opened on this date.*");
            return string.Join("\n", lines);
        }

        if (mergedPrs.Count > 0)
        {
            lines.Add($"### ✅ Merged ({mergedPrs.Count})");
            lines.Add(string.Empty);
            lines.Add("| Repo | PR | Author | Title |");
            lines.Add("|------|-----|--------|-------|");
            foreach (var pr in mergedPrs.OrderByDescending(pr => GetString(pr, "closedAt")))
            {
                lines.Add($"| {GetRepoName(pr.GetProperty("repository"))} | [#{GetNumber(pr)}]({GetString(pr, "url")}) | {GetAuthor(pr.GetProperty("author"))} | {GetString(pr, "title")} |");
            }
            lines.Add(string.Empty);
        }

        if (openedPrs.Count > 0)
        {
            lines.Add($"### 🆕 Opened ({openedPrs.Count})");
            lines.Add(string.Empty);
            lines.Add("| Repo | PR | Author | Title |");
            lines.Add("|------|-----|--------|-------|");
            foreach (var pr in openedPrs.OrderByDescending(pr => GetString(pr, "createdAt")))
            {
                lines.Add($"| {GetRepoName(pr.GetProperty("repository"))} | [#{GetNumber(pr)}]({GetString(pr, "url")}) | {GetAuthor(pr.GetProperty("author"))} | {GetString(pr, "title")} |");
            }
            lines.Add(string.Empty);
        }

        lines.Add($"**Total activity:** {mergedPrs.Count} merged, {openedPrs.Count} opened across the org.");
        lines.Add(string.Empty);
        lines.Add("---");
        lines.Add(string.Empty);
        return string.Join("\n", lines);
    }

    private static async Task<(string Title, int Version, string Body)> GetConfluencePageAsync(HttpClient client, string baseUrl, string pageId, CancellationToken cancellationToken)
    {
        var response = await client.GetAsync($"{baseUrl}/api/v2/pages/{pageId}?body-format=storage", cancellationToken);
        var body = await response.Content.ReadAsStringAsync(cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException($"HTTP {(int)response.StatusCode} while fetching Confluence page");
        }

        var json = JsonDocument.Parse(body).RootElement;
        var title = json.GetProperty("title").GetString() ?? string.Empty;
        var version = json.GetProperty("version").GetProperty("number").GetInt32();
        var storage = json.GetProperty("body").GetProperty("storage").GetProperty("value").GetString() ?? string.Empty;
        return (title, version, storage);
    }

    private static DateOnly ResolveTargetDate(string? dateText)
        => DateOnly.TryParse(dateText, out var parsed) ? parsed : DateOnly.FromDateTime(DateTime.Today.AddDays(-1));

    private static string MarkdownToParagraphs(string text)
    {
        var lines = text.Split('\n').Select(line => line.TrimEnd()).Where(line => !string.IsNullOrWhiteSpace(line));
        return string.Join("\n", lines.Select(line => $"<p>{EscapeXml(line)}</p>"));
    }

    private static string EscapeXml(string text)
        => text.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;").Replace("\"", "&quot;").Replace("'", "&#39;");

    private static async Task<int> RunPassthroughAsync(
        IReadOnlyList<string> command,
        string successMessage,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        var exitCode = await LocalCommandRunner.RunAsync(command[0], command.Skip(1).ToArray(), stdout, stderr, cancellationToken);
        if (exitCode != 0)
        {
            return exitCode;
        }

        await stdout.WriteLineAsync($"✓ {successMessage}");
        return 0;
    }

    private static string SummarizeChecks(JsonElement statusChecks)
    {
        if (statusChecks.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
        {
            return "—";
        }

        var passed = 0;
        var failed = 0;
        var pending = 0;
        foreach (var item in statusChecks.EnumerateArray())
        {
            var state = (item.TryGetProperty("conclusion", out var conclusion) && conclusion.ValueKind != JsonValueKind.Null ? conclusion.GetString() : null)
                ?? (item.TryGetProperty("state", out var stateValue) ? stateValue.GetString() : null)
                ?? (item.TryGetProperty("status", out var status) ? status.GetString() : null)
                ?? "PENDING";
            switch (state.ToUpperInvariant())
            {
                case "SUCCESS":
                case "SUCCESSFUL":
                case "NEUTRAL":
                case "SKIPPED":
                    passed++;
                    break;
                case "FAILURE":
                case "FAILED":
                case "ERROR":
                case "TIMED_OUT":
                case "CANCELLED":
                case "ACTION_REQUIRED":
                case "STARTUP_FAILURE":
                    failed++;
                    break;
                default:
                    pending++;
                    break;
            }
        }

        return $"{passed}✓ {failed}✗ {pending}…";
    }

    private static string ReviewSymbol(string? reviewDecision) => reviewDecision?.ToUpperInvariant() switch
    {
        "APPROVED" => "✓",
        "CHANGES_REQUESTED" => "✗",
        "REVIEW_REQUIRED" => "?",
        _ => "—"
    };

    private static string GetRepoName(JsonElement repository)
        => repository.TryGetProperty("name", out var name) ? name.GetString() ?? string.Empty : string.Empty;

    private static string GetAuthor(JsonElement author)
        => author.TryGetProperty("login", out var login) ? login.GetString() ?? "unknown" : "unknown";

    private static int GetNumber(JsonElement pr)
        => pr.TryGetProperty("number", out var number) && number.TryGetInt32(out var value) ? value : 0;

    private static int GetNumber(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var property) && property.TryGetInt32(out var value) ? value : 0;

    private static string GetString(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var property) ? (property.ValueKind == JsonValueKind.Null ? string.Empty : property.GetString() ?? string.Empty) : string.Empty;

    private static int Fail(string message, TextWriter stderr)
    {
        stderr.WriteLine($"❌ {message}");
        return 1;
    }

    private static string FirstNonEmpty(params string[] values)
        => values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value))?.Trim() ?? string.Empty;
}
