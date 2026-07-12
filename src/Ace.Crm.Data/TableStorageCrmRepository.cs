using Azure;
using Azure.Data.Tables;

namespace Ace.Crm.Data;

/// <summary>
/// Azure Table Storage-backed implementation of <see cref="ICrmRepository"/>.
/// Partition/row key strategy lives in <see cref="TableKeys"/> (pure, unit
/// tested); this class is the thin I/O layer that applies that strategy
/// against the actual table clients.
/// </summary>
public sealed class TableStorageCrmRepository : ICrmRepository
{
    private const string CompaniesTable = "Companies";
    private const string ContactsTable = "Contacts";
    private const string InteractionsTable = "Interactions";

    private readonly TableServiceClient _serviceClient;
    private readonly TimeProvider _timeProvider;
    private readonly Func<string> _idFactory;

    public TableStorageCrmRepository(
        TableServiceClient serviceClient,
        TimeProvider? timeProvider = null,
        Func<string>? idFactory = null)
    {
        _serviceClient = serviceClient;
        _timeProvider = timeProvider ?? TimeProvider.System;
        _idFactory = idFactory ?? (() => Guid.NewGuid().ToString());
    }

    public async Task<Company> CreateCompanyAsync(NewCompanyRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewCompany(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        var table = await GetTableAsync(CompaniesTable, cancellationToken);

        var existing = table.QueryAsync<CompanyEntity>(
            e => e.PartitionKey == TableKeys.CompanyPartitionKey() && e.Name == request.Name,
            cancellationToken: cancellationToken);
        await foreach (var _ in existing)
        {
            throw new ValidationException(new[] { $"Company '{request.Name}' already exists." });
        }

        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var entity = new CompanyEntity
        {
            PartitionKey = TableKeys.CompanyPartitionKey(),
            RowKey = _idFactory(),
            Name = request.Name,
            Website = request.Website,
            Industry = request.Industry,
            Notes = request.Notes,
            CreatedAt = now,
            UpdatedAt = now
        };

        await table.AddEntityAsync(entity, cancellationToken);
        return entity.ToDomain();
    }

    public async Task<Company?> GetCompanyAsync(string id, CancellationToken cancellationToken)
    {
        var table = await GetTableAsync(CompaniesTable, cancellationToken);
        try
        {
            var response = await table.GetEntityAsync<CompanyEntity>(
                TableKeys.CompanyPartitionKey(), id, cancellationToken: cancellationToken);
            return response.Value.ToDomain();
        }
        catch (RequestFailedException ex) when (ex.Status == 404)
        {
            return null;
        }
    }

    public async Task<IReadOnlyList<Company>> ListCompaniesAsync(CancellationToken cancellationToken)
    {
        var table = await GetTableAsync(CompaniesTable, cancellationToken);
        var results = new List<Company>();
        await foreach (var entity in table.QueryAsync<CompanyEntity>(
            e => e.PartitionKey == TableKeys.CompanyPartitionKey(), cancellationToken: cancellationToken))
        {
            results.Add(entity.ToDomain());
        }

        return results.OrderBy(c => c.Name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    public async Task<Contact> CreateContactAsync(NewContactRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewContact(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        var table = await GetTableAsync(ContactsTable, cancellationToken);
        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var entity = new ContactEntity
        {
            PartitionKey = TableKeys.ContactPartitionKey(request.CompanyId),
            RowKey = _idFactory(),
            FirstName = request.FirstName,
            LastName = request.LastName,
            Email = request.Email,
            Phone = request.Phone,
            CompanyId = request.CompanyId,
            Title = request.Title,
            Notes = request.Notes,
            LastContactedAt = null,
            CreatedAt = now,
            UpdatedAt = now
        };

        await table.AddEntityAsync(entity, cancellationToken);
        return entity.ToDomain();
    }

    public async Task<Contact?> GetContactAsync(string id, CancellationToken cancellationToken)
    {
        // Contact partition key depends on CompanyId, which we don't know from
        // the id alone, so lookups by id require a cross-partition scan on
        // RowKey. Acceptable at this scale (a few hundred contacts); revisit
        // with a secondary index table if contact volume grows materially.
        var table = await GetTableAsync(ContactsTable, cancellationToken);
        await foreach (var entity in table.QueryAsync<ContactEntity>(
            e => e.RowKey == id, cancellationToken: cancellationToken))
        {
            return entity.ToDomain();
        }

        return null;
    }

    public async Task<IReadOnlyList<Contact>> ListContactsAsync(string? companyId, CancellationToken cancellationToken)
    {
        var table = await GetTableAsync(ContactsTable, cancellationToken);
        var results = new List<Contact>();

        if (companyId is not null)
        {
            var partitionKey = TableKeys.ContactPartitionKey(companyId);
            await foreach (var entity in table.QueryAsync<ContactEntity>(
                e => e.PartitionKey == partitionKey, cancellationToken: cancellationToken))
            {
                results.Add(entity.ToDomain());
            }
        }
        else
        {
            await foreach (var entity in table.QueryAsync<ContactEntity>(cancellationToken: cancellationToken))
            {
                results.Add(entity.ToDomain());
            }
        }

        return results.OrderBy(c => c.LastName, StringComparer.OrdinalIgnoreCase).ToList();
    }

    public async Task<Interaction> CreateInteractionAsync(NewInteractionRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewInteraction(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        var contact = await GetContactAsync(request.ContactId, cancellationToken);
        if (contact is null)
        {
            throw new ValidationException(new[] { $"Contact '{request.ContactId}' does not exist." });
        }

        var table = await GetTableAsync(InteractionsTable, cancellationToken);
        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var interactionId = _idFactory();
        var entity = new InteractionEntity
        {
            PartitionKey = TableKeys.InteractionPartitionKey(request.ContactId),
            RowKey = TableKeys.InteractionRowKey(request.OccurredAt, interactionId),
            ContactId = request.ContactId,
            InteractionId = interactionId,
            InteractionType = request.InteractionType,
            OccurredAt = request.OccurredAt,
            Notes = request.Notes,
            FollowUpAt = request.FollowUpAt,
            CreatedAt = now
        };

        await table.AddEntityAsync(entity, cancellationToken);
        return entity.ToDomain();
    }

    public async Task<IReadOnlyList<Interaction>> ListInteractionsForContactAsync(string contactId, CancellationToken cancellationToken)
    {
        var table = await GetTableAsync(InteractionsTable, cancellationToken);
        var partitionKey = TableKeys.InteractionPartitionKey(contactId);
        var results = new List<Interaction>();

        // RowKey encodes reverse-chronological order, so partition-scoped
        // results already come back most-recent-first without a client sort.
        await foreach (var entity in table.QueryAsync<InteractionEntity>(
            e => e.PartitionKey == partitionKey, cancellationToken: cancellationToken))
        {
            results.Add(entity.ToDomain());
        }

        return results;
    }

    private async Task<TableClient> GetTableAsync(string tableName, CancellationToken cancellationToken)
    {
        var table = _serviceClient.GetTableClient(tableName);
        await table.CreateIfNotExistsAsync(cancellationToken);
        return table;
    }
}
