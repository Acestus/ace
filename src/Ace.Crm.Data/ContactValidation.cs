using System.Text.RegularExpressions;

namespace Ace.Crm.Data;

/// <summary>
/// Pure validation rules for contact/company/interaction input, kept free of any
/// I/O so they can be unit tested deterministically without a database.
/// </summary>
public static class ContactValidation
{
    private static readonly Regex SimpleEmailPattern = new(
        @"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant);

    public static ValidationResult ValidateNewContact(NewContactRequest request)
    {
        var errors = new List<string>();

        if (string.IsNullOrWhiteSpace(request.FirstName) && string.IsNullOrWhiteSpace(request.LastName))
        {
            errors.Add("Contact requires at least a first or last name.");
        }

        if (!string.IsNullOrWhiteSpace(request.Email) && !SimpleEmailPattern.IsMatch(request.Email))
        {
            errors.Add($"Email '{request.Email}' is not a valid email address.");
        }

        return errors.Count == 0 ? ValidationResult.Success() : ValidationResult.Failure(errors);
    }

    public static ValidationResult ValidateNewCompany(NewCompanyRequest request)
    {
        var errors = new List<string>();

        if (string.IsNullOrWhiteSpace(request.Name))
        {
            errors.Add("Company name is required.");
        }

        if (!string.IsNullOrWhiteSpace(request.Website) &&
            !Uri.TryCreate(request.Website, UriKind.Absolute, out _))
        {
            errors.Add($"Website '{request.Website}' is not a valid absolute URL.");
        }

        return errors.Count == 0 ? ValidationResult.Success() : ValidationResult.Failure(errors);
    }

    public static ValidationResult ValidateNewInteraction(NewInteractionRequest request)
    {
        var errors = new List<string>();

        if (string.IsNullOrWhiteSpace(request.ContactId))
        {
            errors.Add("Interaction requires a contact id.");
        }

        if (!InteractionTypes.IsValid(request.InteractionType))
        {
            errors.Add($"Interaction type '{request.InteractionType}' is not one of: {string.Join(", ", InteractionTypes.Allowed)}.");
        }

        if (request.FollowUpAt is { } followUp && followUp <= request.OccurredAt)
        {
            errors.Add("Follow-up date must be after the interaction date.");
        }

        return errors.Count == 0 ? ValidationResult.Success() : ValidationResult.Failure(errors);
    }
}

public sealed record NewContactRequest(string? FirstName, string? LastName, string? Email, string? Phone, string? CompanyId, string? Title, string? Notes);

public sealed record NewCompanyRequest(string Name, string? Website, string? Industry, string? Notes);

public sealed record NewInteractionRequest(string ContactId, string InteractionType, DateTime OccurredAt, string? Notes, DateTime? FollowUpAt);

public sealed record ValidationResult(bool IsValid, IReadOnlyList<string> Errors)
{
    public static ValidationResult Success() => new(true, Array.Empty<string>());
    public static ValidationResult Failure(IReadOnlyList<string> errors) => new(false, errors);
}
