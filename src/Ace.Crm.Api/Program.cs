using Ace.Crm.Data;
using Azure.Data.Tables;
using Microsoft.Azure.Functions.Worker.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = FunctionsApplication.CreateBuilder(args);

builder.ConfigureFunctionsWebApplication();

var connectionString = Environment.GetEnvironmentVariable("AceCrmTableStorageConnectionString")
    ?? throw new InvalidOperationException("AceCrmTableStorageConnectionString is not configured.");

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton(_ => new TableServiceClient(connectionString));
builder.Services.AddSingleton<ICrmRepository>(sp =>
    new TableStorageCrmRepository(sp.GetRequiredService<TableServiceClient>()));

builder.Build().Run();
