using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Ace.Tools.Cli;

internal sealed class LinearClient
{
    private static readonly HttpClient HttpClient = new()
    {
        BaseAddress = new Uri("https://api.linear.app/graphql"),
        Timeout = TimeSpan.FromSeconds(30)
    };

    private const string IssueQuery = """
        query FetchIssue($id: String!) {
          issue(id: $id) {
            id
            identifier
            title
            description
            priority
            state { name type }
            assignee { name email }
            labels { nodes { name } }
            dueDate
            createdAt
            updatedAt
            team {
              id
              name
              key
              states { nodes { id name type } }
              labels { nodes { id name } }
            }
            comments(orderBy: createdAt) {
              nodes {
                createdAt
                user { name }
                body
              }
            }
            parent { identifier title }
            children { nodes { identifier title state { name } } }
          }
        }
        """;

    private const string TeamQuery = """
        query GetTeam($key: String!) {
          teams(filter: { key: { eq: $key } }) {
            nodes {
              id
              key
              name
              states { nodes { id name type } }
              labels { nodes { id name } }
            }
          }
        }
        """;

    private const string ProjectsQuery = """
        query GetProjects($name: String!) {
          projects(filter: { name: { eq: $name } }) {
            nodes {
              id
              name
              url
              description
              teams { nodes { key name } }
            }
          }
        }
        """;

    private const string CreateIssueMutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue {
              identifier
              title
              url
              state { name }
              priority
            }
          }
        }
        """;

    private const string UpdateIssueStateMutation = """
        mutation UpdateIssueState($id: String!, $stateId: String!) {
          issueUpdate(id: $id, input: { stateId: $stateId }) {
            success
            issue { identifier state { name } }
          }
        }
        """;

    private const string AddCommentMutation = """
        mutation AddComment($issueId: String!, $body: String!) {
          commentCreate(input: { issueId: $issueId, body: $body }) {
            success
            comment { id createdAt }
          }
        }
        """;

    private const string CreateProjectMutation = """
        mutation CreateProject($input: ProjectCreateInput!) {
          projectCreate(input: $input) {
            success
            project {
              id
              name
              url
              description
              teams { nodes { key name } }
            }
          }
        }
        """;

    private readonly string _apiKey;

    public LinearClient()
    {
        DotEnvLoader.LoadIfPresent();
        _apiKey = Environment.GetEnvironmentVariable("LINEAR_API_KEY")?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(_apiKey))
        {
            throw new InvalidOperationException(
                "LINEAR_API_KEY not set. Add it to .env or your environment.");
        }
    }

    public Task<JsonElement> GetIssueAsync(string key, CancellationToken cancellationToken) =>
        QueryIssueAsync(key, cancellationToken);

    public async Task<IReadOnlyList<JsonElement>> SearchIssuesAsync(
        object filter,
        int maxResults,
        CancellationToken cancellationToken)
    {
        var data = await QueryAsync(
            """
            query SearchIssues($filter: IssueFilter!, $first: Int!) {
              issues(filter: $filter, first: $first, orderBy: updatedAt) {
                nodes {
                  identifier
                  title
                  priority
                  state { name }
                  assignee { name }
                  labels { nodes { name } }
                  dueDate
                  updatedAt
                  team { key name }
                }
              }
            }
            """,
            new { filter, first = maxResults },
            cancellationToken);

        return ReadNodes(data, "issues");
    }

    public async Task<JsonElement> QueryTeamAsync(string teamKey, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(TeamQuery, new { key = teamKey.ToUpperInvariant() }, cancellationToken);
        var teams = ReadNodes(data, "teams");
        if (teams.Count == 0)
        {
            throw new InvalidOperationException($"Team '{teamKey}' not found.");
        }

        return teams[0];
    }

    public async Task<IReadOnlyList<JsonElement>> QueryProjectsAsync(string projectName, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(ProjectsQuery, new { name = projectName }, cancellationToken);
        return ReadNodes(data, "projects");
    }

    public async Task<JsonElement> CreateIssueAsync(object input, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(CreateIssueMutation, new { input }, cancellationToken);
        return data.GetProperty("issueCreate").Clone();
    }

    public async Task<JsonElement> CreateProjectAsync(object input, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(CreateProjectMutation, new { input }, cancellationToken);
        return data.GetProperty("projectCreate").Clone();
    }

    public async Task<JsonElement> UpdateIssueStateAsync(string issueId, string stateId, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(UpdateIssueStateMutation, new { id = issueId, stateId }, cancellationToken);
        return data.GetProperty("issueUpdate").Clone();
    }

    public async Task<JsonElement> AddCommentAsync(string issueId, string body, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(AddCommentMutation, new { issueId, body }, cancellationToken);
        return data.GetProperty("commentCreate").Clone();
    }

    public async Task<JsonElement> QueryIssueAsync(string key, CancellationToken cancellationToken)
    {
        var data = await QueryAsync(IssueQuery, new { id = key.ToUpperInvariant() }, cancellationToken);
        return data.GetProperty("issue").Clone();
    }

    public async Task<JsonElement> QueryTeamStatesAsync(string issueKey, CancellationToken cancellationToken)
    {
        var issue = await QueryIssueAsync(issueKey, cancellationToken);
        return issue.GetProperty("team").GetProperty("states").Clone();
    }

    public async Task<JsonElement> QueryIssueTeamAsync(string issueKey, CancellationToken cancellationToken)
    {
        var issue = await QueryIssueAsync(issueKey, cancellationToken);
        return issue.GetProperty("team").Clone();
    }

    private async Task<JsonElement> QueryAsync(
        string query,
        object? variables,
        CancellationToken cancellationToken)
    {
        var request = new JsonObject
        {
            ["query"] = query,
            ["variables"] = JsonSerializer.SerializeToNode(variables ?? new { }) ?? new JsonObject()
        };

        using var message = new HttpRequestMessage(HttpMethod.Post, string.Empty)
        {
            Content = new StringContent(request.ToJsonString(), Encoding.UTF8, "application/json")
        };
        message.Headers.Authorization = new AuthenticationHeaderValue(_apiKey);

        using var response = await HttpClient.SendAsync(message, cancellationToken);
        var responseText = await response.Content.ReadAsStringAsync(cancellationToken);

        using var document = JsonDocument.Parse(responseText);
        if (!response.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(DescribeFailure(response.StatusCode, document));
        }

        if (document.RootElement.TryGetProperty("errors", out var errors))
        {
            throw new InvalidOperationException(DescribeGraphQlErrors(errors));
        }

        if (!document.RootElement.TryGetProperty("data", out var data))
        {
            throw new InvalidOperationException("Linear API response missing data.");
        }

        return data.Clone();
    }

    private static string DescribeFailure(System.Net.HttpStatusCode statusCode, JsonDocument document)
    {
        if (document.RootElement.TryGetProperty("errors", out var errors))
        {
            return $"{(int)statusCode} {statusCode}: {DescribeGraphQlErrors(errors)}";
        }

        return $"{(int)statusCode} {statusCode}: Linear API request failed.";
    }

    private static string DescribeGraphQlErrors(JsonElement errors)
    {
        var messages = new List<string>();
        foreach (var error in errors.EnumerateArray())
        {
            if (error.TryGetProperty("message", out var message))
            {
                messages.Add(message.GetString() ?? "Unknown Linear API error");
            }
        }

        return messages.Count == 0
            ? "Unknown Linear API error"
            : string.Join("; ", messages);
    }

    private static IReadOnlyList<JsonElement> ReadNodes(JsonElement data, string containerName)
    {
        if (!data.TryGetProperty(containerName, out var container))
        {
            return Array.Empty<JsonElement>();
        }

        if (!container.TryGetProperty("nodes", out var nodes))
        {
            return Array.Empty<JsonElement>();
        }

        var results = new List<JsonElement>();
        foreach (var node in nodes.EnumerateArray())
        {
            results.Add(node.Clone());
        }

        return results;
    }
}
