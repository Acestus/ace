using Ace.Crm.Data;
using Reqnroll;
using Xunit;

namespace Ace.Crm.Acceptance.Tests.Features;

[Binding]
public sealed class ContactManagementSteps
{
    private readonly InMemoryCrmRepository _repository = new(TimeProvider.System, () => Guid.NewGuid().ToString());
    private readonly Dictionary<string, string> _contactIdsByFullName = new(StringComparer.OrdinalIgnoreCase);

    private Company? _lastCompanyResult;
    private Contact? _lastContactResult;
    private Interaction? _lastInteractionResult;
    private ValidationException? _lastRejection;

    [Given(@"no contacts have been recorded yet")]
    public void GivenNoContactsHaveBeenRecordedYet()
    {
        // InMemoryCrmRepository starts empty; nothing to arrange.
    }

    [Given(@"no companies have been registered yet")]
    public void GivenNoCompaniesHaveBeenRegisteredYet()
    {
        // InMemoryCrmRepository starts empty; nothing to arrange.
    }

    [Given(@"a company named ""(.*)"" is already registered")]
    public async Task GivenACompanyIsAlreadyRegistered(string companyName)
    {
        await _repository.CreateCompanyAsync(new NewCompanyRequest(companyName, null, null, null), CancellationToken.None);
    }

    [Given(@"a contact named ""(.*)"" has been recorded")]
    public async Task GivenAContactHasBeenRecorded(string fullName)
    {
        var (firstName, lastName) = SplitName(fullName);
        var contact = await _repository.CreateContactAsync(
            new NewContactRequest(firstName, lastName, null, null, null, null, null),
            CancellationToken.None);
        _contactIdsByFullName[fullName] = contact.Id;
    }

    [When(@"I record a contact with first name ""(.*)"" and no last name")]
    public async Task WhenIRecordAContactWithFirstNameAndNoLastName(string firstName)
    {
        await TryCreateContact(firstName, lastName: null);
    }

    [When(@"I record a contact with no first name and no last name")]
    public async Task WhenIRecordAContactWithNoFirstNameAndNoLastName()
    {
        await TryCreateContact(firstName: null, lastName: null);
    }

    [When(@"I register a company named ""(.*)""")]
    public async Task WhenIRegisterACompanyNamed(string companyName)
    {
        _lastRejection = null;
        _lastCompanyResult = null;
        try
        {
            _lastCompanyResult = await _repository.CreateCompanyAsync(
                new NewCompanyRequest(companyName, null, null, null),
                CancellationToken.None);
        }
        catch (ValidationException ex)
        {
            _lastRejection = ex;
        }
    }

    [When(@"I log a ""(.*)"" interaction against ""(.*)"" today")]
    public async Task WhenILogAnInteractionAgainstToday(string interactionType, string fullName)
    {
        await TryCreateInteraction(interactionType, fullName, followUpOffsetDays: null);
    }

    [When(@"I log a ""(.*)"" interaction against ""(.*)"" today with a follow-up (\d+) days later")]
    public async Task WhenILogAnInteractionWithFollowUpLater(string interactionType, string fullName, int days)
    {
        await TryCreateInteraction(interactionType, fullName, followUpOffsetDays: days);
    }

    [When(@"I log a ""(.*)"" interaction against ""(.*)"" today with a follow-up (\d+) days earlier")]
    public async Task WhenILogAnInteractionWithFollowUpEarlier(string interactionType, string fullName, int days)
    {
        await TryCreateInteraction(interactionType, fullName, followUpOffsetDays: -days);
    }

    [Then(@"the contact is accepted")]
    public void ThenTheContactIsAccepted()
    {
        Assert.Null(_lastRejection);
        Assert.NotNull(_lastContactResult);
    }

    [Then(@"the contact is rejected with a reason mentioning ""(.*)""")]
    public void ThenTheContactIsRejectedWithAReasonMentioning(string expectedFragment)
    {
        AssertRejectedWithReason(expectedFragment);
    }

    [Then(@"the company is accepted")]
    public void ThenTheCompanyIsAccepted()
    {
        Assert.Null(_lastRejection);
        Assert.NotNull(_lastCompanyResult);
    }

    [Then(@"the company is rejected with a reason mentioning ""(.*)""")]
    public void ThenTheCompanyIsRejectedWithAReasonMentioning(string expectedFragment)
    {
        AssertRejectedWithReason(expectedFragment);
    }

    [Then(@"the interaction is accepted")]
    public void ThenTheInteractionIsAccepted()
    {
        Assert.Null(_lastRejection);
        Assert.NotNull(_lastInteractionResult);
    }

    [Then(@"the interaction is rejected with a reason mentioning ""(.*)""")]
    public void ThenTheInteractionIsRejectedWithAReasonMentioning(string expectedFragment)
    {
        AssertRejectedWithReason(expectedFragment);
    }

    [Then(@"""(.*)"" has (\d+) recorded interaction(?:s)?")]
    public async Task ThenHasRecordedInteractions(string fullName, int expectedCount)
    {
        var contactId = _contactIdsByFullName[fullName];
        var interactions = await _repository.ListInteractionsForContactAsync(contactId, CancellationToken.None);
        Assert.Equal(expectedCount, interactions.Count);
    }

    private async Task TryCreateContact(string? firstName, string? lastName)
    {
        _lastRejection = null;
        _lastContactResult = null;
        try
        {
            _lastContactResult = await _repository.CreateContactAsync(
                new NewContactRequest(firstName, lastName, null, null, null, null, null),
                CancellationToken.None);
        }
        catch (ValidationException ex)
        {
            _lastRejection = ex;
        }
    }

    private async Task TryCreateInteraction(string interactionType, string fullName, int? followUpOffsetDays)
    {
        _lastRejection = null;
        _lastInteractionResult = null;

        var occurredAt = DateTime.UtcNow.Date;
        var followUpAt = followUpOffsetDays.HasValue ? occurredAt.AddDays(followUpOffsetDays.Value) : (DateTime?)null;
        var contactId = _contactIdsByFullName.GetValueOrDefault(fullName, "unknown-contact-id");

        try
        {
            _lastInteractionResult = await _repository.CreateInteractionAsync(
                new NewInteractionRequest(contactId, interactionType, occurredAt, null, followUpAt),
                CancellationToken.None);
        }
        catch (ValidationException ex)
        {
            _lastRejection = ex;
        }
    }

    private void AssertRejectedWithReason(string expectedFragment)
    {
        Assert.NotNull(_lastRejection);
        Assert.Contains(_lastRejection!.Errors, error => error.Contains(expectedFragment, StringComparison.OrdinalIgnoreCase));
    }

    private static (string? FirstName, string? LastName) SplitName(string fullName)
    {
        var parts = fullName.Split(' ', 2, StringSplitOptions.RemoveEmptyEntries);
        return parts.Length switch
        {
            0 => (null, null),
            1 => (parts[0], null),
            _ => (parts[0], parts[1])
        };
    }
}
