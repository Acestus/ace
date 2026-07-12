namespace Ace.Crm.Data;

/// <summary>
/// Partition/row key derivation for Azure Table Storage, kept as pure functions
/// (no I/O, no Azure SDK types) so key strategy can be unit tested directly and
/// reasoned about independently of the actual table client calls.
///
/// Design goals per entity:
///   Companies:    single logical set, looked up and listed as a whole at this
///                 scale (&lt;= a few hundred companies for a 1-12 person shop).
///                 PartitionKey is a constant so "list all companies" is one
///                 partition scan instead of N cross-partition scans.
///   Contacts:     the dominant query is "contacts for a company", so
///                 PartitionKey = CompanyId groups exactly that. Contacts with
///                 no company use a fixed "unassigned" partition. "List all
///                 contacts" (used by the CRM home page) is a full-table scan
///                 at this scale — acceptable given the entity counts involved.
///   Interactions: the dominant query is "interactions for a contact, most
///                 recent first". PartitionKey = ContactId groups exactly
///                 that; RowKey encodes a reverse-chronological sort key so
///                 the natural Table Storage row order is already
///                 most-recent-first without a client-side sort.
/// </summary>
public static class TableKeys
{
    public const string CompanyPartition = "company";
    public const string UnassignedContactPartition = "unassigned";

    public static string CompanyPartitionKey() => CompanyPartition;

    public static string ContactPartitionKey(string? companyId) =>
        string.IsNullOrWhiteSpace(companyId) ? UnassignedContactPartition : companyId;

    public static string InteractionPartitionKey(string contactId) => contactId;

    /// <summary>
    /// Row key that sorts most-recent-first within a partition. Table Storage
    /// orders rows by RowKey ascending (ordinal string comparison), so we
    /// encode occurredAt as an inverted, fixed-width timestamp
    /// (DateTime.MaxValue.Ticks - occurredAt.Ticks) followed by the entity id
    /// to keep row keys unique even for same-instant interactions.
    /// </summary>
    public static string InteractionRowKey(DateTime occurredAtUtc, string interactionId)
    {
        var invertedTicks = DateTime.MaxValue.Ticks - occurredAtUtc.Ticks;
        return $"{invertedTicks:D19}_{interactionId}";
    }
}
