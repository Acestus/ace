using Ace.Crm.Data;
using Xunit;

namespace Ace.Crm.Data.Tests;

public class ContactValidationTests
{
    [Fact]
    public void Given_FirstNameOnly_When_ValidatingNewContact_Then_IsAccepted()
    {
        var request = new NewContactRequest("Ada", null, null, null, null, null, null);

        var result = ContactValidation.ValidateNewContact(request);

        Assert.True(result.IsValid);
    }

    [Fact]
    public void Given_NoNameAtAll_When_ValidatingNewContact_Then_IsRejected()
    {
        var request = new NewContactRequest(null, null, "ada@example.com", null, null, null, null);

        var result = ContactValidation.ValidateNewContact(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_NoNameAtAll_When_ValidatingNewContact_Then_ReportsMissingNameReason()
    {
        var request = new NewContactRequest(null, null, "ada@example.com", null, null, null, null);

        var result = ContactValidation.ValidateNewContact(request);

        Assert.Contains(result.Errors, error => error.Contains("first or last name", StringComparison.OrdinalIgnoreCase));
    }

    [Theory]
    [InlineData("not-an-email")]
    [InlineData("missing-at-sign.com")]
    [InlineData("two@@signs.com")]
    public void Given_MalformedEmail_When_ValidatingNewContact_Then_IsRejected(string malformedEmail)
    {
        var request = new NewContactRequest("Ada", "Lovelace", malformedEmail, null, null, null, null);

        var result = ContactValidation.ValidateNewContact(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_WellFormedEmail_When_ValidatingNewContact_Then_IsAccepted()
    {
        var request = new NewContactRequest("Ada", "Lovelace", "ada@example.com", null, null, null, null);

        var result = ContactValidation.ValidateNewContact(request);

        Assert.True(result.IsValid);
    }

    [Fact]
    public void Given_BlankName_When_ValidatingNewCompany_Then_IsRejected()
    {
        var request = new NewCompanyRequest(string.Empty, null, null, null);

        var result = ContactValidation.ValidateNewCompany(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_RelativeWebsiteUrl_When_ValidatingNewCompany_Then_IsRejected()
    {
        var request = new NewCompanyRequest("Acestus", "not-a-url", null, null);

        var result = ContactValidation.ValidateNewCompany(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_AbsoluteWebsiteUrl_When_ValidatingNewCompany_Then_IsAccepted()
    {
        var request = new NewCompanyRequest("Acestus", "https://acestus.example", null, null);

        var result = ContactValidation.ValidateNewCompany(request);

        Assert.True(result.IsValid);
    }

    [Fact]
    public void Given_UnknownInteractionType_When_ValidatingNewInteraction_Then_IsRejected()
    {
        var occurredAt = new DateTime(2026, 1, 10, 0, 0, 0, DateTimeKind.Utc);
        var request = new NewInteractionRequest("contact-1", "carrier-pigeon", occurredAt, null, null);

        var result = ContactValidation.ValidateNewInteraction(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_FollowUpBeforeOccurredDate_When_ValidatingNewInteraction_Then_IsRejected()
    {
        var occurredAt = new DateTime(2026, 1, 10, 0, 0, 0, DateTimeKind.Utc);
        var followUpAt = occurredAt.AddDays(-1);
        var request = new NewInteractionRequest("contact-1", "call", occurredAt, null, followUpAt);

        var result = ContactValidation.ValidateNewInteraction(request);

        Assert.False(result.IsValid);
    }

    [Fact]
    public void Given_FollowUpAfterOccurredDate_When_ValidatingNewInteraction_Then_IsAccepted()
    {
        var occurredAt = new DateTime(2026, 1, 10, 0, 0, 0, DateTimeKind.Utc);
        var followUpAt = occurredAt.AddDays(3);
        var request = new NewInteractionRequest("contact-1", "call", occurredAt, null, followUpAt);

        var result = ContactValidation.ValidateNewInteraction(request);

        Assert.True(result.IsValid);
    }
}
