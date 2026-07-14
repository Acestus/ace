@description('Azure region for the Static Web App')
param location string = 'centralus'

@description('Azure region for the Function App / storage (must match existing resources)')
param funcLocation string = 'southcentralus'

@description('Name of the Static Web App')
param swaName string = 'swa-crm-dev-scus-001'

@description('SKU for the Static Web App')
param sku string = 'Free'

@description('Name of the Function App hosting the CRM API')
param functionAppName string = 'func-crm-dev-scus-001'

@description('Name of the storage account backing the Function App runtime')
param funcStorageAccountName string = 'stcrmdevfuncscus001'

@description('Name of the storage account backing CRM table data')
param dataStorageAccountName string = 'stcrmdevscus001'

@description('Resource group containing the pre-existing user-assigned managed identity')
param uamiResourceGroup string = 'rg-crm-dev-id'

@description('Name of the pre-existing user-assigned managed identity')
param uamiName string = 'uami-crm-dev-scus-001'

resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: swaName
  location: location
  sku: {
    name: sku
    tier: sku
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
    }
  }
  tags: {
    ManagedBy: 'https://github.com/Acestus/ace'
    CreatedBy: 'acestus'
  }
}

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: uamiName
  scope: resourceGroup(uamiResourceGroup)
}

resource funcStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: funcStorageAccountName
}

resource dataStorageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: dataStorageAccountName
}

// Managed identity is granted "Storage Table Data Contributor" on dataStorageAccount out-of-band (see infra/README or
// pim-runbook); referenced here only to make the dependency explicit for future automation.
var dataStorageAccountId = dataStorageAccount.id
var swaHostname = staticWebApp.properties.defaultHostname

resource functionPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: 'AceCrmFlexConsumptionPlan'
  location: funcLocation
  kind: 'functionapp,linux'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: funcLocation
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned, UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    serverFarmId: functionPlan.id
    reserved: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${funcStorageAccount.properties.primaryEndpoints.blob}function-deployments'
          authentication: 'StorageAccountConnectionString'
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 10
        instanceMemoryMB: 2048
      }
    }
    siteConfig: {
      linuxFxVersion: 'DOTNET-ISOLATED|8.0'
      cors: {
        allowedOrigins: [
          'https://${swaHostname}'
        ]
      }
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'dotnet-isolated'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${funcStorageAccountName};EndpointSuffix=core.windows.net;AccountKey=${funcStorageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${funcStorageAccountName};EndpointSuffix=core.windows.net;AccountKey=${funcStorageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'AceCrmTableStorageAccountName'
          value: dataStorageAccountName
        }
        {
          name: 'AceCrmTableStorageClientId'
          value: uami.properties.clientId
        }
      ]
    }
  }
}

@description('Deployment token for the Static Web App')
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey

@description('Default hostname')
output defaultHostname string = staticWebApp.properties.defaultHostname

@description('Function App default hostname')
output functionAppHostname string = functionApp.properties.defaultHostName

@description('Data storage account resource id (dependency marker)')
output dataStorageAccountId string = dataStorageAccountId
