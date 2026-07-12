using System.Net;
using System.Text.Json;
using Ace.Crm.Data;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace Ace.Crm.Api;

public sealed class CompaniesFunctions
{
    private readonly ICrmRepository _repository;
    private readonly ILogger<CompaniesFunctions> _logger;

    public CompaniesFunctions(ICrmRepository repository, ILogger<CompaniesFunctions> logger)
    {
        _repository = repository;
        _logger = logger;
    }

    [Function("ListCompanies")]
    public async Task<HttpResponseData> ListAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "companies")] HttpRequestData request,
        CancellationToken cancellationToken)
    {
        var companies = await _repository.ListCompaniesAsync(cancellationToken);
        return await JsonResponse.Ok(request, companies);
    }

    [Function("GetCompany")]
    public async Task<HttpResponseData> GetAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "companies/{id}")] HttpRequestData request,
        string id,
        CancellationToken cancellationToken)
    {
        var company = await _repository.GetCompanyAsync(id, cancellationToken);
        return company is null
            ? request.CreateResponse(HttpStatusCode.NotFound)
            : await JsonResponse.Ok(request, company);
    }

    [Function("CreateCompany")]
    public async Task<HttpResponseData> CreateAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", Route = "companies")] HttpRequestData request,
        CancellationToken cancellationToken)
    {
        var body = await JsonSerializer.DeserializeAsync<NewCompanyRequest>(
            request.Body,
            JsonResponse.SerializerOptions,
            cancellationToken);

        if (body is null)
        {
            return await JsonResponse.BadRequest(request, "Request body is required.");
        }

        try
        {
            var company = await _repository.CreateCompanyAsync(body, cancellationToken);
            return await JsonResponse.Created(request, company);
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning("Company creation rejected: {Errors}", string.Join(" ", ex.Errors));
            return await JsonResponse.BadRequest(request, ex.Errors);
        }
    }
}
