namespace Ace.Crm.Data;

/// <summary>
/// Server-side (Azure SQL) CRM company record. Mirrors the shape of
/// <c>Ace.Tools.Cli.CrmContact</c>'s companion company data, kept as a mutable
/// class (not a record) to match the model style already established in
/// Ace.Tools.Cli/Models.cs and to bind cleanly with Dapper's default mapper.
/// </summary>
public class Company
{
    public string Id { get; set; } = null!;
    public string Name { get; set; } = null!;
    public string? Website { get; set; }
    public string? Industry { get; set; }
    public string? Notes { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}

/// <summary>
/// Server-side (Azure SQL) CRM contact record — the shared-store counterpart
/// to <c>Ace.Tools.Cli.CrmContact</c> (which is the local SQLite cache).
/// </summary>
public class Contact
{
    public string Id { get; set; } = null!;
    public string? FirstName { get; set; }
    public string? LastName { get; set; }
    public string? Email { get; set; }
    public string? Phone { get; set; }
    public string? CompanyId { get; set; }
    public string? Title { get; set; }
    public string? Notes { get; set; }
    public DateTime? LastContactedAt { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}

/// <summary>
/// A single logged interaction (call, email, meeting, etc.) against a contact.
/// </summary>
public class Interaction
{
    public string Id { get; set; } = null!;
    public string ContactId { get; set; } = null!;
    public string InteractionType { get; set; } = null!;
    public DateTime OccurredAt { get; set; }
    public string? Notes { get; set; }
    public DateTime? FollowUpAt { get; set; }
    public DateTime CreatedAt { get; set; }
}

public static class InteractionTypes
{
    public static readonly IReadOnlySet<string> Allowed =
        new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "email", "call", "meeting", "coffee", "other" };

    public static bool IsValid(string? interactionType) =>
        interactionType is not null && Allowed.Contains(interactionType);
}
