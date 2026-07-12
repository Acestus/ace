using Ace.Crm.Data;
using Xunit;

namespace Ace.Crm.Data.Tests;

public class InMemoryCrmRepositoryTests
{
    private static readonly DateTimeOffset FixedNow = new(2026, 3, 1, 9, 0, 0, TimeSpan.Zero);

    private static InMemoryCrmRepository CreateRepository(string fixedId = "fixed-id-1") =>
        new(new FixedTimeProvider(FixedNow), () => fixedId);

    [Fact]
    public async Task Given_ValidRequest_When_CreatingCompany_Then_AssignsGeneratedId()
    {
        var repository = CreateRepository("company-1");
        var request = new NewCompanyRequest("Acestus", "https://acestus.example", "Infrastructure", null);

        var company = await repository.CreateCompanyAsync(request, CancellationToken.None);

        Assert.Equal("company-1", company.Id);
    }

    [Fact]
    public async Task Given_ValidRequest_When_CreatingCompany_Then_StampsCreatedAtFromTimeProvider()
    {
        var repository = CreateRepository();
        var request = new NewCompanyRequest("Acestus", null, null, null);

        var company = await repository.CreateCompanyAsync(request, CancellationToken.None);

        Assert.Equal(FixedNow.UtcDateTime, company.CreatedAt);
    }

    [Fact]
    public async Task Given_DuplicateCompanyName_When_CreatingCompany_Then_ThrowsValidationException()
    {
        var repository = CreateRepository();
        await repository.CreateCompanyAsync(new NewCompanyRequest("Acestus", null, null, null), CancellationToken.None);

        var act = () => repository.CreateCompanyAsync(new NewCompanyRequest("acestus", null, null, null), CancellationToken.None);

        await Assert.ThrowsAsync<ValidationException>(act);
    }

    [Fact]
    public async Task Given_InvalidRequest_When_CreatingCompany_Then_NothingIsStored()
    {
        var repository = CreateRepository();
        var invalidRequest = new NewCompanyRequest(string.Empty, null, null, null);

        await Assert.ThrowsAsync<ValidationException>(
            () => repository.CreateCompanyAsync(invalidRequest, CancellationToken.None));

        var companies = await repository.ListCompaniesAsync(CancellationToken.None);
        Assert.Empty(companies);
    }

    [Fact]
    public async Task Given_UnknownId_When_GettingCompany_Then_ReturnsNull()
    {
        var repository = CreateRepository();

        var company = await repository.GetCompanyAsync("does-not-exist", CancellationToken.None);

        Assert.Null(company);
    }

    [Fact]
    public async Task Given_MultipleCompanies_When_ListingCompanies_Then_OrderedByName()
    {
        var repository = new InMemoryCrmRepository(new FixedTimeProvider(FixedNow), SequentialIds());
        await repository.CreateCompanyAsync(new NewCompanyRequest("Zebra Co", null, null, null), CancellationToken.None);
        await repository.CreateCompanyAsync(new NewCompanyRequest("Acme Co", null, null, null), CancellationToken.None);

        var companies = await repository.ListCompaniesAsync(CancellationToken.None);

        Assert.Equal(new[] { "Acme Co", "Zebra Co" }, companies.Select(c => c.Name));
    }

    [Fact]
    public async Task Given_InvalidRequest_When_CreatingContact_Then_ThrowsValidationException()
    {
        var repository = CreateRepository();
        var invalidRequest = new NewContactRequest(null, null, null, null, null, null, null);

        await Assert.ThrowsAsync<ValidationException>(
            () => repository.CreateContactAsync(invalidRequest, CancellationToken.None));
    }

    [Fact]
    public async Task Given_UnknownContact_When_CreatingInteraction_Then_ThrowsValidationException()
    {
        var repository = CreateRepository();
        var request = new NewInteractionRequest("unknown-contact", "call", FixedNow.UtcDateTime, null, null);

        await Assert.ThrowsAsync<ValidationException>(
            () => repository.CreateInteractionAsync(request, CancellationToken.None));
    }

    [Fact]
    public async Task Given_ExistingContact_When_CreatingInteraction_Then_IsRetrievableViaListInteractions()
    {
        var repository = new InMemoryCrmRepository(new FixedTimeProvider(FixedNow), SequentialIds());
        var contact = await repository.CreateContactAsync(
            new NewContactRequest("Ada", "Lovelace", null, null, null, null, null),
            CancellationToken.None);

        await repository.CreateInteractionAsync(
            new NewInteractionRequest(contact.Id, "call", FixedNow.UtcDateTime, "Intro call", null),
            CancellationToken.None);

        var interactions = await repository.ListInteractionsForContactAsync(contact.Id, CancellationToken.None);

        Assert.Single(interactions);
    }

    [Fact]
    public async Task Given_MultipleInteractions_When_ListingInteractionsForContact_Then_OrderedMostRecentFirst()
    {
        var repository = new InMemoryCrmRepository(new FixedTimeProvider(FixedNow), SequentialIds());
        var contact = await repository.CreateContactAsync(
            new NewContactRequest("Ada", "Lovelace", null, null, null, null, null),
            CancellationToken.None);

        var earlier = FixedNow.UtcDateTime.AddDays(-5);
        var later = FixedNow.UtcDateTime;

        await repository.CreateInteractionAsync(
            new NewInteractionRequest(contact.Id, "email", earlier, "First contact", null),
            CancellationToken.None);
        await repository.CreateInteractionAsync(
            new NewInteractionRequest(contact.Id, "call", later, "Follow-up call", null),
            CancellationToken.None);

        var interactions = await repository.ListInteractionsForContactAsync(contact.Id, CancellationToken.None);

        Assert.Equal("call", interactions.First().InteractionType);
    }

    [Fact]
    public async Task Given_ContactWithNoInteractions_When_ListingInteractions_Then_ReturnsEmpty()
    {
        var repository = new InMemoryCrmRepository(new FixedTimeProvider(FixedNow), SequentialIds());
        var contact = await repository.CreateContactAsync(
            new NewContactRequest("Ada", "Lovelace", null, null, null, null, null),
            CancellationToken.None);

        var interactions = await repository.ListInteractionsForContactAsync(contact.Id, CancellationToken.None);

        Assert.Empty(interactions);
    }

    private static Func<string> SequentialIds()
    {
        var counter = 0;
        return () => $"id-{++counter}";
    }

    private sealed class FixedTimeProvider : TimeProvider
    {
        private readonly DateTimeOffset _fixedNow;

        public FixedTimeProvider(DateTimeOffset fixedNow) => _fixedNow = fixedNow;

        public override DateTimeOffset GetUtcNow() => _fixedNow;
    }
}
