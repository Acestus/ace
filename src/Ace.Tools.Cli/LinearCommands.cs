using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Ace.Tools.Cli;

internal static class LinearCommands
{
    // Claims are now in ~/.ace/rounds.db via RoundsDb (ACE-22)
    private static readonly Dictionary<string, string> DefaultFlowStates = new(StringComparer.OrdinalIgnoreCase)
    {
        ["queue"] = "Backlog",
        ["active"] = "In Progress",
        ["waiting"] = "In Review",
        ["done"] = "Done",
    };

    private static readonly Dictionary<int, string> PriorityLabels = new()
    {
        [0] = "No Priority",
        [1] = "Urgent",
        [2] = "High",
        [3] = "Medium",
        [4] = "Low",
    };

    public static async Task<int> RunAsync(
        string[] args,
        TextWriter stdout,
        TextWriter stderr,
        CancellationToken cancellationToken)
    {
        if (args.Length == 0)
        {
            return UnknownCommand("linear", stderr);
        }

        return args[0] switch
        {
            "get-issue" => await GetIssueAsync(args[1..], stdout, stderr, cancellationToken),
            "search" => await SearchAsync(args[1..], stdout, stderr, cancellationToken),
            "set-flow" => await SetFlowAsync(args[1..], stdout, stderr, cancellationToken),
            "comment" => await CommentAsync(args[1..], stdout, stderr, cancellationToken),
            "create-issue" => await CreateIssueAsync(args[1..], stdout, stderr, cancellationToken),
            "create-project" => await CreateProjectAsync(args[1..], stdout, stderr, cancellationToken),
            "dispatch-next" => await DispatchNextAsync(args[1..], stdout, stderr, cancellationToken),
            "start-my-day" => await StartMyDayAsync(args[1..], stdout, stderr, cancellationToken),
            _ => UnknownCommand($"linear {args[0]}", stderr)
        };
    }

    private static async Task<int> GetIssueAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var key = CommandHelpers.GetRequiredOptionValue(args, "--key");
        var json = CommandHelpers.HasOption(args, "--json");

        var client = new LinearClient();
        var issue = await client.GetIssueAsync(key, cancellationToken);
        if (issue.ValueKind == JsonValueKind.Undefined || issue.ValueKind == JsonValueKind.Null)
        {
            return Fail($"Issue {key} not found.", stderr);
        }

        if (json)
        {
            await stdout.WriteAsync(issue.GetRawText());
            await stdout.WriteLineAsync();
            return 0;
        }

        PrintIssue(stdout, issue);
        return 0;
    }

    private static async Task<int> SearchAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var filter = BuildSearchFilter(args);
        if (filter.Count == 0)
        {
            return Fail("Provide at least one filter (--state, --team, --priority, --label)", stderr);
        }

        var max = int.TryParse(CommandHelpers.GetOptionValue(args, "--max"), out var value) ? value : 25;
        var json = CommandHelpers.HasOption(args, "--json");

        var client = new LinearClient();
        var issues = await client.SearchIssuesAsync(filter, max, cancellationToken);
        if (json)
        {
            await stdout.WriteAsync("[" + string.Join(",", issues.Select(issue => issue.GetRawText())) + "]");
            await stdout.WriteLineAsync();
            return 0;
        }

        if (issues.Count == 0)
        {
            await stdout.WriteLineAsync("No issues found.");
            return 0;
        }

        var rows = new List<IReadOnlyList<string>>();
        foreach (var issue in issues)
        {
            rows.Add(
                [
                    GetString(issue, "identifier"),
                    GetString(issue.GetProperty("state"), "name"),
                    GetPriorityLabel(GetInt(issue, "priority")),
                    BuildLabels(issue),
                    CommandHelpers.Truncate(GetString(issue, "title"), 48)
                ]);
        }

        CommandHelpers.PrintTable(stdout, ["ID", "STATE", "PRI", "LABELS", "TITLE"], rows);
        await stdout.WriteLineAsync();
        await stdout.WriteLineAsync($"{issues.Count} result(s)");
        return 0;
    }

    private static async Task<int> SetFlowAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var key = CommandHelpers.GetRequiredOptionValue(args, "--key");
        var flow = CommandHelpers.GetOptionValue(args, "--flow");
        var state = CommandHelpers.GetOptionValue(args, "--state");
        var targetStateName = !string.IsNullOrWhiteSpace(state)
            ? state
            : !string.IsNullOrWhiteSpace(flow)
                ? ResolveFlowState(flow)
                : string.Empty;

        if (string.IsNullOrWhiteSpace(targetStateName))
        {
            return Fail("Provide either --flow or --state", stderr);
        }

        var client = new LinearClient();
        var issue = await client.GetIssueAsync(key, cancellationToken);
        if (issue.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            return Fail($"Issue {key} not found.", stderr);
        }

        var states = issue.GetProperty("team").GetProperty("states").GetProperty("nodes");
        var targetState = FindState(states, targetStateName);
        if (targetState.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            var available = states.EnumerateArray().Select(node => GetString(node, "name"));
            return Fail($"State '{targetStateName}' not found in team.\nAvailable: {string.Join(", ", available)}", stderr);
        }

        var update = await client.UpdateIssueStateAsync(GetString(issue, "id"), GetString(targetState, "id"), cancellationToken);
        if (update.GetProperty("success").GetBoolean())
        {
            var newState = update.GetProperty("issue").GetProperty("state").GetProperty("name").GetString() ?? "?";
            await stdout.WriteLineAsync($"✓ {key.ToUpperInvariant()} → {newState}");
            return 0;
        }

        return Fail($"Failed to update {key}", stderr);
    }

    private static async Task<int> CommentAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var key = CommandHelpers.GetRequiredOptionValue(args, "--key");
        var body = CommandHelpers.GetOptionValue(args, "--body");
        var file = CommandHelpers.GetOptionValue(args, "--file");
        if (string.IsNullOrWhiteSpace(body) && string.IsNullOrWhiteSpace(file))
        {
            return Fail("Provide either --body or --file", stderr);
        }

        if (!string.IsNullOrWhiteSpace(file))
        {
            body = await File.ReadAllTextAsync(file, cancellationToken);
        }

        var client = new LinearClient();
        var issue = await client.GetIssueAsync(key, cancellationToken);
        if (issue.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            return Fail($"Issue {key} not found.", stderr);
        }

        var result = await client.AddCommentAsync(GetString(issue, "id"), body ?? string.Empty, cancellationToken);
        if (result.GetProperty("success").GetBoolean())
        {
            await stdout.WriteLineAsync($"✓ Comment added to {key.ToUpperInvariant()}");
            return 0;
        }

        return Fail($"Failed to add comment to {key}", stderr);
    }

    private static async Task<int> CreateIssueAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var teamKey = CommandHelpers.GetRequiredOptionValue(args, "--team");
        var title = CommandHelpers.GetRequiredOptionValue(args, "--title");
        var description = CommandHelpers.GetOptionValue(args, "--description") ?? string.Empty;
        var stateName = CommandHelpers.GetOptionValue(args, "--state") ?? "Backlog";
        var json = CommandHelpers.HasOption(args, "--json");
        var priority = int.TryParse(CommandHelpers.GetOptionValue(args, "--priority"), out var parsedPriority) ? parsedPriority : 0;
        var labelNames = CommandHelpers.GetRepeatableOptionValues(args, "--label");
        var projectId = CommandHelpers.GetOptionValue(args, "--project-id") ?? string.Empty;
        var projectName = CommandHelpers.GetOptionValue(args, "--project") ?? string.Empty;

        var client = new LinearClient();
        var team = await client.QueryTeamAsync(teamKey, cancellationToken);
        var stateId = FindStateByName(team.GetProperty("states").GetProperty("nodes"), stateName);
        if (stateId.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            var available = team.GetProperty("states").GetProperty("nodes").EnumerateArray().Select(node => GetString(node, "name"));
            return Fail($"State '{stateName}' not found. Available: {string.Join(", ", available)}", stderr);
        }

        var labelIds = ResolveIssueLabelIds(team.GetProperty("labels").GetProperty("nodes"), labelNames, out var missingLabels);
        if (missingLabels.Count > 0)
        {
            await stdout.WriteLineAsync($"⚠ Labels not found in team (will be skipped): {string.Join(", ", missingLabels)}");
            await stdout.WriteLineAsync($"  Available labels: {string.Join(", ", team.GetProperty("labels").GetProperty("nodes").EnumerateArray().Select(node => GetString(node, "name")))}");
        }

        var input = new Dictionary<string, object?>
        {
            ["teamId"] = GetString(team, "id"),
            ["title"] = title,
            ["priority"] = priority,
            ["stateId"] = GetString(stateId, "id")
        };

        if (!string.IsNullOrWhiteSpace(description))
        {
            input["description"] = description;
        }

        if (!string.IsNullOrWhiteSpace(projectId))
        {
            input["projectId"] = projectId;
        }
        else if (!string.IsNullOrWhiteSpace(projectName))
        {
            var projects = await client.QueryProjectsAsync(projectName, cancellationToken);
            var matching = projects.FirstOrDefault(project =>
                project.GetProperty("teams").GetProperty("nodes").EnumerateArray().Any(teamNode =>
                    string.Equals(GetString(teamNode, "key"), teamKey, StringComparison.OrdinalIgnoreCase)));
            if (matching.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
            {
                return Fail($"Project '{projectName}' not found for team '{teamKey}'.", stderr);
            }

            input["projectId"] = GetString(matching, "id");
        }

        if (labelIds.Count > 0)
        {
            input["labelIds"] = labelIds;
        }

        var created = await client.CreateIssueAsync(input, cancellationToken);
        if (json)
        {
            await stdout.WriteAsync(created.GetRawText());
            await stdout.WriteLineAsync();
            return 0;
        }

        if (created.GetProperty("success").GetBoolean())
        {
            var issue = created.GetProperty("issue");
            await stdout.WriteLineAsync($"✓ Created {GetString(issue, "identifier")} — {GetString(issue, "title")}");
            await stdout.WriteLineAsync($"  URL: {GetString(issue, "url")}");
            await stdout.WriteLineAsync($"  State: {GetString(issue.GetProperty("state"), "name")}");
            return 0;
        }

        return Fail("Failed to create issue.", stderr);
    }

    private static async Task<int> CreateProjectAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var teamKey = CommandHelpers.GetRequiredOptionValue(args, "--team");
        var name = CommandHelpers.GetRequiredOptionValue(args, "--name");
        var description = CommandHelpers.GetOptionValue(args, "--description") ?? string.Empty;
        var icon = CommandHelpers.GetOptionValue(args, "--icon") ?? string.Empty;
        var color = CommandHelpers.GetOptionValue(args, "--color") ?? string.Empty;
        var json = CommandHelpers.HasOption(args, "--json");

        var client = new LinearClient();
        var team = await client.QueryTeamAsync(teamKey, cancellationToken);
        var projects = await client.QueryProjectsAsync(name, cancellationToken);
        var existing = projects.FirstOrDefault(project =>
            project.GetProperty("teams").GetProperty("nodes").EnumerateArray().Any(teamNode =>
                string.Equals(GetString(teamNode, "key"), GetString(team, "key"), StringComparison.OrdinalIgnoreCase)));

        if (existing.ValueKind is not JsonValueKind.Undefined and not JsonValueKind.Null)
        {
            if (json)
            {
                var payload = new { created = false, project = existing.Clone() };
                await stdout.WriteAsync(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
                await stdout.WriteLineAsync();
                return 0;
            }

            await stdout.WriteLineAsync($"✓ Project exists: {GetString(existing, "name")}");
            await stdout.WriteLineAsync($"  URL: {GetString(existing, "url")}");
            return 0;
        }

        var input = new Dictionary<string, object?>
        {
            ["teamIds"] = new[] { GetString(team, "id") },
            ["name"] = name
        };

        if (!string.IsNullOrWhiteSpace(description))
        {
            input["description"] = description;
        }

        if (!string.IsNullOrWhiteSpace(icon))
        {
            input["icon"] = icon;
        }

        if (!string.IsNullOrWhiteSpace(color))
        {
            input["color"] = color;
        }

        var created = await client.CreateProjectAsync(input, cancellationToken);
        if (!created.GetProperty("success").GetBoolean())
        {
            return Fail("Failed to create project.", stderr);
        }

        var project = created.GetProperty("project");
        if (json)
        {
            var payload = new { created = true, project = project.Clone() };
            await stdout.WriteAsync(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
            await stdout.WriteLineAsync();
            return 0;
        }

        await stdout.WriteLineAsync($"✓ Created project: {GetString(project, "name")}");
        await stdout.WriteLineAsync($"  URL: {GetString(project, "url")}");
        return 0;
    }

    private static async Task<int> DispatchNextAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        var activate = CommandHelpers.HasOption(args, "--activate");
        var json = CommandHelpers.HasOption(args, "--json");
        var claimed = LoadClaimedKeys();
        var client = new LinearClient();

        var activeIssues = await client.SearchIssuesAsync(BuildSearchFilter(state: ResolveFlowState("active")), 100, cancellationToken);
        var chosen = activeIssues
            .Where(issue => !claimed.Contains(GetString(issue, "identifier").ToUpperInvariant()))
            .OrderBy(IssueRank)
            .FirstOrDefault();

        var source = "active";
        if (chosen.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            var queued = await client.SearchIssuesAsync(
                BuildSearchFilter(state: ResolveFlowState("queue"), label: "flow:queue"),
                100,
                cancellationToken);
            chosen = queued
                .Where(issue => !claimed.Contains(GetString(issue, "identifier").ToUpperInvariant()))
                .OrderBy(IssueRank)
                .FirstOrDefault();
            source = "queue";
        }

        if (chosen.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            if (json)
            {
                await stdout.WriteAsync("""{"found":false}""");
                await stdout.WriteLineAsync();
                return 0;
            }

            await stdout.WriteLineAsync("No unclaimed Linear tickets found.");
            return 0;
        }

        var payload = new Dictionary<string, object?>
        {
            ["found"] = true,
            ["source"] = source,
            ["key"] = GetString(chosen, "identifier"),
            ["title"] = GetString(chosen, "title"),
            ["priority"] = GetInt(chosen, "priority"),
            ["priority_label"] = GetPriorityLabel(GetInt(chosen, "priority")),
            ["state"] = GetString(chosen.GetProperty("state"), "name"),
            ["team"] = GetString(chosen.GetProperty("team"), "key"),
            ["activated"] = false
        };

        if (activate)
        {
            var chosenKey = payload["key"]?.ToString() ?? string.Empty;
            await SetFlowAsync(new[] { "--key", chosenKey, "--flow", "active" }, TextWriter.Null, stderr, cancellationToken);
            await CreateStubAsync(chosenKey, cancellationToken);
            // Claim the key in SQLite (lane 0 = unassigned / auto-dispatch)
            await RoundsDb.AppendWorklogAsync(null, chosenKey, "dispatch", $"source:{source}", cancellationToken);
            payload["activated"] = true;
        }

        if (json)
        {
            await stdout.WriteAsync(JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
            await stdout.WriteLineAsync();
            return 0;
        }

        await stdout.WriteLineAsync($"✓ Next Linear ticket: {payload["key"]} — {payload["title"]}");
        await stdout.WriteLineAsync($"  Source: {source} | Priority: {payload["priority_label"]} | State: {payload["state"]}");
        if (activate)
        {
            await stdout.WriteLineAsync("  Activated and stubbed.");
        }

        return 0;
    }

    private static async Task<int> StartMyDayAsync(string[] args, TextWriter stdout, TextWriter stderr, CancellationToken cancellationToken)
    {
        if (args.Length > 0 && CommandHelpers.HasOption(args, "--help", "-h"))
        {
            await stdout.WriteLineAsync("linear start-my-day");
            await stdout.WriteLineAsync();
            await stdout.WriteLineAsync("Usage:");
            await stdout.WriteLineAsync("  linear start-my-day");
            return 0;
        }

        var repoRoot = RepoPaths.FindRepoRoot();
        var plannerDir = Path.Combine(repoRoot, "planner");
        Directory.CreateDirectory(plannerDir);

        var today = DateOnly.FromDateTime(DateTime.Now);
        var notePath = Path.Combine(plannerDir, $"{today:MM-dd}.org");
        if (File.Exists(notePath) && !string.IsNullOrWhiteSpace(await File.ReadAllTextAsync(notePath, cancellationToken)))
        {
            await stdout.WriteLineAsync($"✓ Daily note already exists: {Path.GetRelativePath(repoRoot, notePath)}");
            return 0;
        }

        var client = new LinearClient();
        var issues = await client.QueryViewerAssignedIssuesAsync(cancellationToken);
        var activeState = ResolveFlowState("active");
        var activeIssues = issues
            .Where(issue => string.Equals(GetString(issue.GetProperty("state"), "name"), activeState, StringComparison.OrdinalIgnoreCase))
            .OrderBy(IssueRank)
            .ToList();

        var boardedIssues = activeIssues
            .Take(5)
            .Select(issue => new DailyTicket(
                GetString(issue, "identifier"),
                GetString(issue, "title"),
                GetInt(issue, "priority"),
                GetString(issue.GetProperty("team"), "key"),
                GetString(issue.GetProperty("team"), "name"),
                FindIssueFilePath(repoRoot, GetString(issue, "identifier")),
                string.Empty))
            .Select(ticket => ticket with { NextStep = ReadNextStep(ticket.IssueFilePath) })
            .ToList();

        var note = BuildDailyNote(today, boardedIssues, await GetAuthorAsync(cancellationToken));
        await File.WriteAllTextAsync(notePath, note, cancellationToken);

        await stdout.WriteLineAsync($"✓ Daily note created: {Path.GetRelativePath(repoRoot, notePath)}");
        await stdout.WriteLineAsync($"✓ Loaded {boardedIssues.Count} active ticket(s)");
        if (activeIssues.Count > boardedIssues.Count)
        {
            await stdout.WriteLineAsync($"⚠ {activeIssues.Count - boardedIssues.Count} additional active ticket(s) omitted from the 5-lane board.");
        }

        if (boardedIssues.Count < 3)
        {
            await stdout.WriteLineAsync("⚠ Fewer than 3 active tickets loaded. Consider dispatching the next queue item.");
        }

        foreach (var (ticket, index) in boardedIssues.Select((ticket, index) => (ticket, index)))
        {
            await stdout.WriteLineAsync($"  Lane {index + 1}: {ticket.Identifier} — {ticket.Title}");
            await stdout.WriteLineAsync($"    NEXT: {ticket.NextStep}");
        }

        await stdout.WriteLineAsync($"  Board: {Path.GetRelativePath(repoRoot, notePath)}");
        return 0;
    }

    private static async Task CreateStubAsync(string key, CancellationToken cancellationToken)
    {
        var client = new LinearClient();
        var issue = await client.GetIssueAsync(key, cancellationToken);
        if (issue.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
        {
            throw new InvalidOperationException($"Issue {key} not found.");
        }

        var title = GetString(issue, "title");
        var identifier = GetString(issue, "identifier");
        var labels = issue.GetProperty("labels").GetProperty("nodes").EnumerateArray().Select(node => GetString(node, "name")).ToArray();
        var state = GetString(issue.GetProperty("state"), "name");
        var priority = GetInt(issue, "priority");
        var urgency = PriorityToUrgency(priority);
        var team = GetString(issue.GetProperty("team"), "name");
        var due = GetString(issue, "dueDate");
        var folderName = $"{identifier} - {Slugify(title)}";
        var repoRoot = RepoPaths.FindRepoRoot();
        var folder = Path.Combine(repoRoot, "issues", folderName);
        if (Directory.Exists(folder))
        {
            return;
        }

        Directory.CreateDirectory(folder);
        var flow = labels.FirstOrDefault(label => label.StartsWith("flow:", StringComparison.OrdinalIgnoreCase))?.Split(':', 2)[1] ?? "queue";
        var today = DateTime.UtcNow.Date.ToString("yyyy-MM-dd");
        var content = $"""
---
LINEAR: {identifier}
title: {title}
team: {team}
state: {state}
flow: {flow}
urgency: {urgency}
due: {due}
created: {today}
---

## Description

{(string.IsNullOrWhiteSpace(GetString(issue, "description")) ? "*(no description)*" : GetString(issue, "description"))}

## Actions

### {today}

WORKLOG: Stub created from Linear {identifier}

## Follow-up

Status: {state}
TODO:
- [ ] Review and scope work
""";

        await File.WriteAllTextAsync(Path.Combine(folder, $"{folderName}.md"), content, cancellationToken);
    }

    private static IReadOnlyDictionary<string, object?> BuildSearchFilter(string? state = null, string? label = null, string? team = null, int? priority = null)
    {
        var filter = new Dictionary<string, object?>();
        if (!string.IsNullOrWhiteSpace(state))
        {
            filter["state"] = new { name = new { eq = state } };
        }

        if (!string.IsNullOrWhiteSpace(team))
        {
            filter["team"] = new { key = new { eq = team.ToUpperInvariant() } };
        }

        if (priority.HasValue)
        {
            filter["priority"] = new { eq = priority.Value };
        }

        if (!string.IsNullOrWhiteSpace(label))
        {
            filter["labels"] = new { name = new { eq = label } };
        }

        return filter;
    }

    private static IReadOnlyDictionary<string, object?> BuildSearchFilter(string[] args)
    {
        var state = CommandHelpers.GetOptionValue(args, "--state");
        var team = CommandHelpers.GetOptionValue(args, "--team");
        var label = CommandHelpers.GetOptionValue(args, "--label");
        int? priority = int.TryParse(CommandHelpers.GetOptionValue(args, "--priority"), out var parsed) ? parsed : null;
        return BuildSearchFilter(state, label, team, priority);
    }

    private static string BuildDailyNote(DateOnly date, IReadOnlyList<DailyTicket> tickets, string author)
    {
        var builder = new System.Text.StringBuilder();
        builder.AppendLine($"#+TITLE: Daily Note — {date:yyyy-MM-dd} ({date.ToDateTime(TimeOnly.MinValue).ToString("ddd", CultureInfo.InvariantCulture)})");
        builder.AppendLine($"#+DATE: <{date:yyyy-MM-dd} {date.ToDateTime(TimeOnly.MinValue).ToString("ddd", CultureInfo.InvariantCulture)}>");
        builder.AppendLine($"#+AUTHOR: {author}");
        builder.AppendLine();
        builder.AppendLine("* Time Log");
        builder.AppendLine("| Ticket | Start | Stop | Duration | Notes |");
        builder.AppendLine("|--------|-------|------|----------|-------|");
        builder.AppendLine("|        |       |      |          |       |");
        builder.AppendLine();
        builder.AppendLine($"* Kanban Board — WIP: {tickets.Count}/{GetBoardCapacity(tickets.Count)}");
        builder.AppendLine("# Dispatcher can update this section. Status board, not a calendar.");

        for (var lane = 1; lane <= 5; lane++)
        {
            builder.AppendLine();
            builder.AppendLine(lane switch
            {
                1 => "** Lane 1 (Urgent)",
                2 => "** Lane 2 (Manual)",
                3 => "** Lane 3 (Background)",
                4 => "** Lane 4",
                5 => "** Lane 5",
                _ => "** Lane"
            });

            if (lane <= tickets.Count)
            {
                var ticket = tickets[lane - 1];
                builder.AppendLine($"*** TODO {ticket.Identifier} — {ticket.Title}");
                builder.AppendLine($"    :NEXT: {ticket.NextStep}");
            }
            else
            {
                builder.AppendLine("*** (empty)");
            }
        }

        builder.AppendLine();
        builder.AppendLine("* Standup");
        builder.AppendLine("** Yesterday");
        builder.AppendLine("   - (start of day)");
        builder.AppendLine("** Today");
        if (tickets.Count == 0)
        {
            builder.AppendLine("   - [ ] Pull the next ticket from queue");
        }
        else
        {
            foreach (var ticket in tickets)
            {
                builder.AppendLine($"   - [ ] {ticket.Identifier} — {ticket.NextStep}");
            }
        }
        builder.AppendLine("** Blockers");
        builder.AppendLine("   - None");
        builder.AppendLine();
        builder.AppendLine("* Notes");
        builder.AppendLine();
        return builder.ToString();
    }

    private static int GetBoardCapacity(int activeCount) => activeCount <= 3 ? 3 : 5;

    private static string? FindIssueFilePath(string repoRoot, string key)
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

    private static string ReadNextStep(string? issueFilePath)
    {
        if (string.IsNullOrWhiteSpace(issueFilePath) || !File.Exists(issueFilePath))
        {
            return "No next step defined";
        }

        var started = false;
        var followUpLevel = 0;
        foreach (var line in File.ReadLines(issueFilePath))
        {
            if (!started)
            {
                var heading = Regex.Match(line, @"^\s*(?<prefix>#{1,6}|\*{1,6})\s+Follow-up\b", RegexOptions.IgnoreCase);
                if (heading.Success)
                {
                    followUpLevel = heading.Groups["prefix"].Value.Length;
                    started = true;
                }

                continue;
            }

            var nextHeading = Regex.Match(line, @"^\s*(?<prefix>#{1,6}|\*{1,6})\s+\S+");
            if (nextHeading.Success && nextHeading.Groups["prefix"].Value.Length <= followUpLevel)
            {
                break;
            }

            var match = Regex.Match(line, @"^\s*-\s+\[ \]\s+(?<step>.+)$");
            if (match.Success)
            {
                return match.Groups["step"].Value.Trim();
            }
        }

        return "No next step defined";
    }

    private static async Task<string> GetAuthorAsync(CancellationToken cancellationToken)
    {
        var result = await LocalCommandRunner.RunCaptureAsync("git", ["config", "user.name"], cancellationToken);
        var author = result.ExitCode == 0 ? result.Stdout.Trim() : string.Empty;
        return string.IsNullOrWhiteSpace(author) ? "acestus" : author;
    }

    private static IReadOnlyList<string> ResolveIssueLabelIds(JsonElement teamLabels, IReadOnlyList<string> labelNames, out List<string> missingLabels)
    {
        var labelMap = teamLabels.EnumerateArray().ToDictionary(node => GetString(node, "name"), node => GetString(node, "id"), StringComparer.OrdinalIgnoreCase);
        var result = new List<string>();
        missingLabels = new List<string>();
        foreach (var name in labelNames)
        {
            if (labelMap.TryGetValue(name, out var labelId))
            {
                result.Add(labelId);
            }
            else
            {
                missingLabels.Add(name);
            }
        }

        return result;
    }

    private static JsonElement FindState(JsonElement states, string targetStateName)
    {
        foreach (var state in states.EnumerateArray())
        {
            if (string.Equals(GetString(state, "name"), targetStateName, StringComparison.OrdinalIgnoreCase))
            {
                return state;
            }
        }

        return default;
    }

    private static JsonElement FindStateByName(JsonElement states, string stateName) => FindState(states, stateName);

    private static string ResolveFlowState(string flow)
    {
        var envKey = $"LINEAR_STATE_{flow.ToUpperInvariant()}";
        var envValue = Environment.GetEnvironmentVariable(envKey)?.Trim();
        if (!string.IsNullOrWhiteSpace(envValue))
        {
            return envValue;
        }

        return DefaultFlowStates.TryGetValue(flow, out var fallback) ? fallback : "Backlog";
    }

    private static int PriorityToUrgency(int priority) => priority switch
    {
        1 => 1,
        2 => 2,
        3 => 3,
        4 => 4,
        _ => 5
    };

    private static (int Priority, int Number) IssueRank(JsonElement issue)
    {
        var identifier = GetString(issue, "identifier");
        var suffix = identifier.Split('-', 2).LastOrDefault() ?? string.Empty;
        var number = int.TryParse(suffix, out var parsed) ? parsed : int.MaxValue;
        return (GetInt(issue, "priority"), number);
    }

    private static string Slugify(string text)
    {
        var safe = new string(text.Where(ch => char.IsLetterOrDigit(ch) || char.IsWhiteSpace(ch) || ch == '-').ToArray());
        return Regex.Replace(safe, @"\s+", " ").Trim();
    }

    private static string BuildLabels(JsonElement issue)
    {
        var labels = issue.GetProperty("labels").GetProperty("nodes").EnumerateArray().Select(node => GetString(node, "name")).ToArray();
        return labels.Length == 0 ? "None" : string.Join(", ", labels);
    }

    private static void PrintIssue(TextWriter stdout, JsonElement issue)
    {
        var labels = issue.GetProperty("labels").GetProperty("nodes").EnumerateArray().Select(node => GetString(node, "name")).ToArray();
        var comments = issue.GetProperty("comments").GetProperty("nodes").EnumerateArray().ToArray();
        var children = issue.GetProperty("children").GetProperty("nodes").EnumerateArray().ToArray();
        var team = issue.GetProperty("team");
        var assignee = issue.TryGetProperty("assignee", out var assigneeNode) ? assigneeNode : default;
        var parent = issue.TryGetProperty("parent", out var parentNode) ? parentNode : default;

        stdout.WriteLine();
        stdout.WriteLine(new string('=', 60));
        stdout.WriteLine($"  {GetString(issue, "identifier")} — {GetString(issue, "title")}");
        stdout.WriteLine(new string('=', 60));
        stdout.WriteLine($"  Team:      {GetString(team, "name")} ({GetString(team, "key")})");
        stdout.WriteLine($"  State:     {GetString(issue.GetProperty("state"), "name")}");
        stdout.WriteLine($"  Priority:  {GetPriorityLabel(GetInt(issue, "priority"))}");
        stdout.WriteLine($"  Assignee:  {GetString(assignee, "name")}");
        stdout.WriteLine($"  Due:       {GetString(issue, "dueDate")}");
        stdout.WriteLine($"  Labels:    {(labels.Length == 0 ? "None" : string.Join(", ", labels))}");
        if (parent.ValueKind is not JsonValueKind.Undefined and not JsonValueKind.Null)
        {
            stdout.WriteLine($"  Parent:    {GetString(parent, "identifier")} — {GetString(parent, "title")}");
        }
        stdout.WriteLine();

        var description = GetString(issue, "description").Trim();
        if (!string.IsNullOrWhiteSpace(description))
        {
            stdout.WriteLine("--- Description ---");
            stdout.WriteLine(description);
            stdout.WriteLine();
        }

        if (children.Length > 0)
        {
            stdout.WriteLine("--- Sub-issues ---");
            foreach (var child in children)
            {
                stdout.WriteLine($"  {GetString(child, "identifier")} [{GetString(child.GetProperty("state"), "name")}] — {GetString(child, "title")}");
            }
            stdout.WriteLine();
        }

        if (comments.Length > 0)
        {
            stdout.WriteLine($"--- Comments ({comments.Length}) ---");
            foreach (var comment in comments)
            {
                var who = GetString(comment.GetProperty("user"), "name");
                var when = GetString(comment, "createdAt");
                stdout.WriteLine();
                stdout.WriteLine($"  [{when[..Math.Min(10, when.Length)]}] {who}");
                stdout.WriteLine("  " + GetString(comment, "body").Replace("\n", "\n  "));
            }

            stdout.WriteLine();
        }
    }

    private static string GetPriorityLabel(int priority) => PriorityLabels.TryGetValue(priority, out var label) ? label : "Unknown";

    private static string GetString(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var property) ? (property.GetString() ?? string.Empty) : string.Empty;

    private static int GetInt(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var property) && property.TryGetInt32(out var value) ? value : 0;

    private static List<string> LoadClaimedKeys()
        => RoundsDb.GetClaimedKeysAsync(CancellationToken.None).GetAwaiter().GetResult();

    private static int UnknownCommand(string command, TextWriter stderr)
    {
        stderr.WriteLine($"❌ Unknown command: {command}");
        return 2;
    }

    private static int Fail(string message, TextWriter stderr)
    {
        stderr.WriteLine($"❌ {message}");
        return 1;
    }

    private sealed record DailyTicket(
        string Identifier,
        string Title,
        int Priority,
        string TeamKey,
        string TeamName,
        string? IssueFilePath,
        string NextStep);
}
