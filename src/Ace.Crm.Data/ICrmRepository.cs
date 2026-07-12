namespace Ace.Crm.Data;

/// <summary>
/// Repository contract for CRM persistence. Kept as an interface so the API layer
/// and unit tests can depend on an abstraction instead of a concrete SQL client.
/// </summary>
public interface ICrmRepository
{
    Task<Company> CreateCompanyAsync(NewCompanyRequest request, CancellationToken cancellationToken);

    Task<Company?> GetCompanyAsync(string id, CancellationToken cancellationToken);

    Task<IReadOnlyList<Company>> ListCompaniesAsync(CancellationToken cancellationToken);

    Task<Contact> CreateContactAsync(NewContactRequest request, CancellationToken cancellationToken);

    Task<Contact?> GetContactAsync(string id, CancellationToken cancellationToken);

    Task<IReadOnlyList<Contact>> ListContactsAsync(string? companyId, CancellationToken cancellationToken);

    Task<Interaction> CreateInteractionAsync(NewInteractionRequest request, CancellationToken cancellationToken);

    Task<IReadOnlyList<Interaction>> ListInteractionsForContactAsync(string contactId, CancellationToken cancellationToken);
}
