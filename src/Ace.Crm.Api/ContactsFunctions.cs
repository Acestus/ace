using System.Net;
using System.Text.Json;
using Ace.Crm.Data;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace Ace.Crm.Api;

public sealed class ContactsFunctions
{
    private readonly ICrmRepository _repository;
    private readonly ILogger<ContactsFunctions> _logger;

    public ContactsFunctions(ICrmRepository repository, ILogger<ContactsFunctions> logger)
    {
        _repository = repository;
        _logger = logger;
    }

    [Function("ListContacts")]
    public async Task<HttpResponseData> ListAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "contacts")] HttpRequestData request,
        CancellationToken cancellationToken)
    {
        var companyId = QueryHelpers.GetValue(request, "companyId");
        var contacts = await _repository.ListContactsAsync(companyId, cancellationToken);
        return await JsonResponse.Ok(request, contacts);
    }

    [Function("GetContact")]
    public async Task<HttpResponseData> GetAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "contacts/{id}")] HttpRequestData request,
        string id,
        CancellationToken cancellationToken)
    {
        var contact = await _repository.GetContactAsync(id, cancellationToken);
        return contact is null
            ? request.CreateResponse(HttpStatusCode.NotFound)
            : await JsonResponse.Ok(request, contact);
    }

    [Function("CreateContact")]
    public async Task<HttpResponseData> CreateAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", Route = "contacts")] HttpRequestData request,
        CancellationToken cancellationToken)
    {
        var body = await JsonSerializer.DeserializeAsync<NewContactRequest>(
            request.Body,
            JsonResponse.SerializerOptions,
            cancellationToken);

        if (body is null)
        {
            return await JsonResponse.BadRequest(request, "Request body is required.");
        }

        try
        {
            var contact = await _repository.CreateContactAsync(body, cancellationToken);
            return await JsonResponse.Created(request, contact);
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning("Contact creation rejected: {Errors}", string.Join(" ", ex.Errors));
            return await JsonResponse.BadRequest(request, ex.Errors);
        }
    }

    [Function("CreateInteraction")]
    public async Task<HttpResponseData> CreateInteractionAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", Route = "contacts/{contactId}/interactions")] HttpRequestData request,
        string contactId,
        CancellationToken cancellationToken)
    {
        var body = await JsonSerializer.DeserializeAsync<InteractionBody>(
            request.Body,
            JsonResponse.SerializerOptions,
            cancellationToken);

        if (body is null)
        {
            return await JsonResponse.BadRequest(request, "Request body is required.");
        }

        var newInteraction = new NewInteractionRequest(contactId, body.InteractionType, body.OccurredAt, body.Notes, body.FollowUpAt);

        try
        {
            var interaction = await _repository.CreateInteractionAsync(newInteraction, cancellationToken);
            return await JsonResponse.Created(request, interaction);
        }
        catch (ValidationException ex)
        {
            _logger.LogWarning("Interaction creation rejected: {Errors}", string.Join(" ", ex.Errors));
            return await JsonResponse.BadRequest(request, ex.Errors);
        }
    }

    [Function("ListInteractions")]
    public async Task<HttpResponseData> ListInteractionsAsync(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", Route = "contacts/{contactId}/interactions")] HttpRequestData request,
        string contactId,
        CancellationToken cancellationToken)
    {
        var interactions = await _repository.ListInteractionsForContactAsync(contactId, cancellationToken);
        return await JsonResponse.Ok(request, interactions);
    }

    public sealed record InteractionBody(string InteractionType, DateTime OccurredAt, string? Notes, DateTime? FollowUpAt);
}
