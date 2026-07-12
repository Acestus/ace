using Azure;
using Azure.Data.Tables;

namespace Ace.Crm.Data;

/// <summary>
/// Azure Table Storage row shapes. Kept separate from the domain models
/// (<see cref="Company"/>, <see cref="Contact"/>, <see cref="Interaction"/>)
/// so the domain layer has no dependency on Azure.Data.Tables types — the
/// repository is the only place that converts between the two.
/// </summary>
public sealed class CompanyEntity : ITableEntity
{
    public string PartitionKey { get; set; } = null!;
    public string RowKey { get; set; } = null!;
    public DateTimeOffset? Timestamp { get; set; }
    public ETag ETag { get; set; }

    public string Name { get; set; } = null!;
    public string? Website { get; set; }
    public string? Industry { get; set; }
    public string? Notes { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }

    public Company ToDomain() => new()
    {
        Id = RowKey,
        Name = Name,
        Website = Website,
        Industry = Industry,
        Notes = Notes,
        CreatedAt = CreatedAt,
        UpdatedAt = UpdatedAt
    };
}

public sealed class ContactEntity : ITableEntity
{
    public string PartitionKey { get; set; } = null!;
    public string RowKey { get; set; } = null!;
    public DateTimeOffset? Timestamp { get; set; }
    public ETag ETag { get; set; }

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

    public Contact ToDomain() => new()
    {
        Id = RowKey,
        FirstName = FirstName,
        LastName = LastName,
        Email = Email,
        Phone = Phone,
        CompanyId = CompanyId,
        Title = Title,
        Notes = Notes,
        LastContactedAt = LastContactedAt,
        CreatedAt = CreatedAt,
        UpdatedAt = UpdatedAt
    };
}

public sealed class InteractionEntity : ITableEntity
{
    public string PartitionKey { get; set; } = null!;
    public string RowKey { get; set; } = null!;
    public DateTimeOffset? Timestamp { get; set; }
    public ETag ETag { get; set; }

    public string ContactId { get; set; } = null!;
    public string InteractionId { get; set; } = null!;
    public string InteractionType { get; set; } = null!;
    public DateTime OccurredAt { get; set; }
    public string? Notes { get; set; }
    public DateTime? FollowUpAt { get; set; }
    public DateTime CreatedAt { get; set; }

    public Interaction ToDomain() => new()
    {
        Id = InteractionId,
        ContactId = ContactId,
        InteractionType = InteractionType,
        OccurredAt = OccurredAt,
        Notes = Notes,
        FollowUpAt = FollowUpAt,
        CreatedAt = CreatedAt
    };
}
