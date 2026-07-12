using Ace.Crm.Data;
using Azure.Core;
using Azure.Data.Tables;
using Azure.Identity;
using Microsoft.Azure.Functions.Worker.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = FunctionsApplication.CreateBuilder(args);

builder.ConfigureFunctionsWebApplication();

// Two supported auth modes:
// 1. Managed identity (preferred in Azure): AceCrmTableStorageAccountName [+ AceCrmTableStorageClientId for user-assigned identity]
// 2. Connection string (local dev / fallback): AceCrmTableStorageConnectionString
var accountName = Environment.GetEnvironmentVariable("AceCrmTableStorageAccountName");
var connectionString = Environment.GetEnvironmentVariable("AceCrmTableStorageConnectionString");

builder.Services.AddSingleton(TimeProvider.System);

if (!string.IsNullOrWhiteSpace(accountName))
{
    var clientId = Environment.GetEnvironmentVariable("AceCrmTableStorageClientId");
    TokenCredential credential = string.IsNullOrWhiteSpace(clientId)
        ? new DefaultAzureCredential()
        : new ManagedIdentityCredential(clientId);

    var tableUri = new Uri($"https://{accountName}.table.core.windows.net");
    builder.Services.AddSingleton(_ => new TableServiceClient(tableUri, credential));
}
else if (!string.IsNullOrWhiteSpace(connectionString))
{
    builder.Services.AddSingleton(_ => new TableServiceClient(connectionString));
}
else
{
    throw new InvalidOperationException(
        "Configure either AceCrmTableStorageAccountName (managed identity) or AceCrmTableStorageConnectionString.");
}

builder.Services.AddSingleton<ICrmRepository>(sp =>
    new TableStorageCrmRepository(sp.GetRequiredService<TableServiceClient>()));

builder.Build().Run();
