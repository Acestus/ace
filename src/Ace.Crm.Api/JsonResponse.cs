using System.Net;
using System.Text.Json;
using Microsoft.Azure.Functions.Worker.Http;

namespace Ace.Crm.Api;

internal static class JsonResponse
{
    public static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    public static async Task<HttpResponseData> Ok<T>(HttpRequestData request, T body)
    {
        var response = request.CreateResponse(HttpStatusCode.OK);
        await WriteJsonAsync(response, body);
        return response;
    }

    public static async Task<HttpResponseData> Created<T>(HttpRequestData request, T body)
    {
        var response = request.CreateResponse(HttpStatusCode.Created);
        await WriteJsonAsync(response, body);
        return response;
    }

    public static async Task<HttpResponseData> BadRequest(HttpRequestData request, string message) =>
        await BadRequest(request, new[] { message });

    public static async Task<HttpResponseData> BadRequest(HttpRequestData request, IReadOnlyList<string> errors)
    {
        var response = request.CreateResponse(HttpStatusCode.BadRequest);
        await WriteJsonAsync(response, new { errors });
        return response;
    }

    private static async Task WriteJsonAsync<T>(HttpResponseData response, T body)
    {
        response.Headers.Add("Content-Type", "application/json; charset=utf-8");
        var json = JsonSerializer.Serialize(body, SerializerOptions);
        await response.WriteStringAsync(json);
    }
}

internal static class QueryHelpers
{
    public static string? GetValue(HttpRequestData request, string key)
    {
        var queryString = request.Url.Query.TrimStart('?');
        foreach (var pair in queryString.Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var parts = pair.Split('=', 2);
            var name = Uri.UnescapeDataString(parts[0]);
            if (!string.Equals(name, key, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var value = parts.Length > 1 ? Uri.UnescapeDataString(parts[1]) : null;
            return string.IsNullOrWhiteSpace(value) ? null : value;
        }

        return null;
    }
}
