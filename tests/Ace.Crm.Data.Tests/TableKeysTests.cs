using Ace.Crm.Data;
using Xunit;

namespace Ace.Crm.Data.Tests;

public class TableKeysTests
{
    [Fact]
    public void CompanyPartitionKey_IsAlwaysTheSameConstant()
    {
        Assert.Equal(TableKeys.CompanyPartitionKey(), TableKeys.CompanyPartitionKey());
    }

    [Fact]
    public void Given_CompanyId_When_BuildingContactPartitionKey_Then_UsesCompanyIdAsPartition()
    {
        var partitionKey = TableKeys.ContactPartitionKey("company-123");

        Assert.Equal("company-123", partitionKey);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Given_NoCompanyId_When_BuildingContactPartitionKey_Then_FallsBackToUnassignedPartition(string? companyId)
    {
        var partitionKey = TableKeys.ContactPartitionKey(companyId);

        Assert.Equal(TableKeys.UnassignedContactPartition, partitionKey);
    }

    [Fact]
    public void Given_ContactId_When_BuildingInteractionPartitionKey_Then_UsesContactIdAsPartition()
    {
        var partitionKey = TableKeys.InteractionPartitionKey("contact-abc");

        Assert.Equal("contact-abc", partitionKey);
    }

    [Fact]
    public void Given_LaterOccurredAt_When_BuildingInteractionRowKeys_Then_LaterEventSortsBeforeEarlierEvent()
    {
        var earlier = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var later = new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);

        var earlierRowKey = TableKeys.InteractionRowKey(earlier, "interaction-1");
        var laterRowKey = TableKeys.InteractionRowKey(later, "interaction-2");

        // Table Storage returns rows in RowKey ascending (ordinal) order, so
        // the row key for the more recent interaction must sort first.
        Assert.True(string.CompareOrdinal(laterRowKey, earlierRowKey) < 0);
    }

    [Fact]
    public void Given_SameOccurredAt_When_BuildingInteractionRowKeysForDifferentIds_Then_RowKeysAreUnique()
    {
        var occurredAt = new DateTime(2026, 3, 1, 9, 0, 0, DateTimeKind.Utc);

        var rowKeyOne = TableKeys.InteractionRowKey(occurredAt, "interaction-1");
        var rowKeyTwo = TableKeys.InteractionRowKey(occurredAt, "interaction-2");

        Assert.NotEqual(rowKeyOne, rowKeyTwo);
    }

    [Fact]
    public void Given_ThreeInteractionsAtDifferentTimes_When_SortingByRowKey_Then_OrderIsMostRecentFirst()
    {
        var oldest = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var middle = new DateTime(2026, 3, 1, 0, 0, 0, DateTimeKind.Utc);
        var newest = new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);

        var rowKeys = new[]
        {
            TableKeys.InteractionRowKey(oldest, "a"),
            TableKeys.InteractionRowKey(newest, "b"),
            TableKeys.InteractionRowKey(middle, "c"),
        };

        var sorted = rowKeys.OrderBy(key => key, StringComparer.Ordinal).ToArray();

        Assert.Equal(TableKeys.InteractionRowKey(newest, "b"), sorted[0]);
        Assert.Equal(TableKeys.InteractionRowKey(middle, "c"), sorted[1]);
        Assert.Equal(TableKeys.InteractionRowKey(oldest, "a"), sorted[2]);
    }
}
