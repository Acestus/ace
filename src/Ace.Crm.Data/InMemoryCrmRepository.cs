using System.Collections.Concurrent;

namespace Ace.Crm.Data;

/// <summary>
/// In-memory implementation of <see cref="ICrmRepository"/> for local development
/// and fast, deterministic acceptance/unit testing without a live database.
/// </summary>
public sealed class InMemoryCrmRepository : ICrmRepository
{
    private readonly ConcurrentDictionary<string, Company> _companies = new();
    private readonly ConcurrentDictionary<string, Contact> _contacts = new();
    private readonly ConcurrentDictionary<string, List<Interaction>> _interactionsByContact = new();
    private readonly TimeProvider _timeProvider;
    private readonly Func<string> _idFactory;

    public InMemoryCrmRepository(TimeProvider? timeProvider = null, Func<string>? idFactory = null)
    {
        _timeProvider = timeProvider ?? TimeProvider.System;
        _idFactory = idFactory ?? (() => Guid.NewGuid().ToString());
    }

    public Task<Company> CreateCompanyAsync(NewCompanyRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewCompany(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        if (_companies.Values.Any(c => string.Equals(c.Name, request.Name, StringComparison.OrdinalIgnoreCase)))
        {
            throw new ValidationException(new[] { $"Company '{request.Name}' already exists." });
        }

        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var company = new Company
        {
            Id = _idFactory(),
            Name = request.Name,
            Website = request.Website,
            Industry = request.Industry,
            Notes = request.Notes,
            CreatedAt = now,
            UpdatedAt = now
        };
        _companies[company.Id] = company;
        return Task.FromResult(company);
    }

    public Task<Company?> GetCompanyAsync(string id, CancellationToken cancellationToken) =>
        Task.FromResult(_companies.GetValueOrDefault(id));

    public Task<IReadOnlyList<Company>> ListCompaniesAsync(CancellationToken cancellationToken) =>
        Task.FromResult<IReadOnlyList<Company>>(_companies.Values.OrderBy(c => c.Name, StringComparer.OrdinalIgnoreCase).ToList());

    public Task<Contact> CreateContactAsync(NewContactRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewContact(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var contact = new Contact
        {
            Id = _idFactory(),
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
        _contacts[contact.Id] = contact;
        return Task.FromResult(contact);
    }

    public Task<Contact?> GetContactAsync(string id, CancellationToken cancellationToken) =>
        Task.FromResult(_contacts.GetValueOrDefault(id));

    public Task<IReadOnlyList<Contact>> ListContactsAsync(string? companyId, CancellationToken cancellationToken)
    {
        IEnumerable<Contact> query = _contacts.Values;
        if (companyId is not null)
        {
            query = query.Where(c => c.CompanyId == companyId);
        }

        return Task.FromResult<IReadOnlyList<Contact>>(
            query.OrderBy(c => c.LastName, StringComparer.OrdinalIgnoreCase).ToList());
    }

    public Task<Interaction> CreateInteractionAsync(NewInteractionRequest request, CancellationToken cancellationToken)
    {
        var validation = ContactValidation.ValidateNewInteraction(request);
        if (!validation.IsValid)
        {
            throw new ValidationException(validation.Errors);
        }

        if (!_contacts.ContainsKey(request.ContactId))
        {
            throw new ValidationException(new[] { $"Contact '{request.ContactId}' does not exist." });
        }

        var now = _timeProvider.GetUtcNow().UtcDateTime;
        var interaction = new Interaction
        {
            Id = _idFactory(),
            ContactId = request.ContactId,
            InteractionType = request.InteractionType,
            OccurredAt = request.OccurredAt,
            Notes = request.Notes,
            FollowUpAt = request.FollowUpAt,
            CreatedAt = now
        };

        var list = _interactionsByContact.GetOrAdd(request.ContactId, _ => new List<Interaction>());
        lock (list)
        {
            list.Add(interaction);
        }

        return Task.FromResult(interaction);
    }

    public Task<IReadOnlyList<Interaction>> ListInteractionsForContactAsync(string contactId, CancellationToken cancellationToken)
    {
        if (!_interactionsByContact.TryGetValue(contactId, out var list))
        {
            return Task.FromResult<IReadOnlyList<Interaction>>(Array.Empty<Interaction>());
        }

        lock (list)
        {
            return Task.FromResult<IReadOnlyList<Interaction>>(list.OrderByDescending(i => i.OccurredAt).ToList());
        }
    }
}
