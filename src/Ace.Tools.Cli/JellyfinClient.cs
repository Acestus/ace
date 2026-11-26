using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Ace.Tools.Cli;

public sealed class JellyfinClient
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true
    };

    private readonly HttpClient _http;

    public JellyfinClient(string baseUrl, string? token = null, HttpClient? httpClient = null)
    {
        _http = httpClient ?? new HttpClient();
        _http.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/", UriKind.Absolute);
        _http.Timeout = TimeSpan.FromSeconds(30);

        if (!string.IsNullOrWhiteSpace(token))
        {
            // Jellyfin 12.x accepts API keys through the Authorization header.
            // Keep the token out of URLs and request logs.
            _http.DefaultRequestHeaders.TryAddWithoutValidation(
                "Authorization", $"MediaBrowser Token=\"{token}\"");
        }
    }

    public async Task<JellyfinPublicSystemInfo> GetPublicSystemInfoAsync(CancellationToken cancellationToken)
        => await GetAsync<JellyfinPublicSystemInfo>("System/Info/Public", cancellationToken);

    public async Task<IReadOnlyList<JellyfinVirtualFolder>> GetLibrariesAsync(CancellationToken cancellationToken)
        => await GetAsync<List<JellyfinVirtualFolder>>("Library/VirtualFolders", cancellationToken);

    public async Task RefreshLibraryAsync(CancellationToken cancellationToken)
        => await SendAsync(HttpMethod.Post, "Library/Refresh", null, cancellationToken);

    public async Task UpdateMediaPathAsync(string libraryName, string path, CancellationToken cancellationToken)
    {
        var payload = new
        {
            Name = libraryName,
            PathInfo = new { Path = path }
        };
        await SendAsync(HttpMethod.Post, "Library/VirtualFolders/Paths/Update", JsonContent.Create(payload), cancellationToken);
    }

    public async Task RemoveLibraryAsync(string libraryName, bool refreshLibrary, CancellationToken cancellationToken)
    {
        var path = "Library/VirtualFolders?name=" + Uri.EscapeDataString(libraryName)
            + "&refreshLibrary=" + refreshLibrary.ToString().ToLowerInvariant();
        await SendAsync(HttpMethod.Delete, path, null, cancellationToken);
    }

    public async Task<IReadOnlyList<JellyfinItem>> SearchAsync(
        string searchTerm,
        string? includeItemTypes,
        CancellationToken cancellationToken)
    {
        var query = new List<string>
        {
            $"SearchTerm={Uri.EscapeDataString(searchTerm)}",
            "Recursive=true",
            "IncludeItemTypes=" + Uri.EscapeDataString(includeItemTypes ?? "Movie,Series")
        };
        var response = await GetAsync<JellyfinItemsResponse>("Items?" + string.Join('&', query), cancellationToken);
        return response.Items;
    }

    public async Task UpdateTagsAsync(
        string itemId,
        IReadOnlyCollection<string> tags,
        CancellationToken cancellationToken)
    {
        var response = await GetAsync<JellyfinItemsResponse>(
            "Items?Ids=" + Uri.EscapeDataString(itemId) + "&Fields=Tags",
            cancellationToken);
        var item = response.Items.SingleOrDefault()
            ?? throw new InvalidOperationException($"Jellyfin item not found: {itemId}");
        var mergedTags = (item.Tags ?? [])
            .Concat(tags)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var payload = new
        {
            Id = item.Id,
            Name = item.Name,
            Type = item.Type,
            Tags = mergedTags
        };
        await SendAsync(HttpMethod.Post, "Items/" + Uri.EscapeDataString(itemId), JsonContent.Create(payload, options: JsonOptions), cancellationToken);
    }

    public async Task<JellyfinCollection> CreateCollectionAsync(string name, CancellationToken cancellationToken)
    {
        var response = await SendAsync(HttpMethod.Post,
            "Collections?Name=" + Uri.EscapeDataString(name), null, cancellationToken);
        return await ReadAsync<JellyfinCollection>(response, cancellationToken);
    }

    public async Task AddItemsToCollectionAsync(
        string collectionId,
        IReadOnlyCollection<string> itemIds,
        CancellationToken cancellationToken)
    {
        var query = string.Join('&', itemIds.Select(id => "Ids=" + Uri.EscapeDataString(id)));
        await SendAsync(HttpMethod.Post,
            "Collections/" + Uri.EscapeDataString(collectionId) + "/Items?" + query,
            null,
            cancellationToken);
    }

    private async Task<T> GetAsync<T>(string path, CancellationToken cancellationToken)
    {
        using var response = await _http.GetAsync(path, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return (await response.Content.ReadFromJsonAsync<T>(JsonOptions, cancellationToken))
            ?? throw new InvalidOperationException($"Jellyfin returned an empty response for {path}.");
    }

    private async Task<HttpResponseMessage> SendAsync(
        HttpMethod method,
        string path,
        HttpContent? content,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(method, path) { Content = content };
        var response = await _http.SendAsync(request, cancellationToken);
        await EnsureSuccessAsync(response, cancellationToken);
        return response;
    }

    private static async Task<T> ReadAsync<T>(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        return await JsonSerializer.DeserializeAsync<T>(stream, JsonOptions, cancellationToken)
            ?? throw new InvalidOperationException("Jellyfin returned an empty response.");
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        var detail = await response.Content.ReadAsStringAsync(cancellationToken);
        throw new HttpRequestException($"Jellyfin API returned {(int)response.StatusCode} {response.ReasonPhrase}: {detail}");
    }
}

public sealed record JellyfinPublicSystemInfo(
    string LocalAddress,
    string ServerName,
    string Version,
    string ProductName,
    bool StartupWizardCompleted);

public sealed record JellyfinVirtualFolder(
    string Name,
    string CollectionType,
    IReadOnlyList<string> Locations);

public sealed class JellyfinItemsResponse
{
    public IReadOnlyList<JellyfinItem> Items { get; set; } = [];
}

public sealed class JellyfinItem
{
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string? Type { get; set; }
    public string[] Tags { get; set; } = [];
}

public sealed record JellyfinCollection(
    [property: JsonPropertyName("Id")] string Id,
    [property: JsonPropertyName("Name")] string Name);
