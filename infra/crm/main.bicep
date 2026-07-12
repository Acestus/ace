@description('Azure region for the Static Web App')
param location string = 'centralus'

@description('Name of the Static Web App')
param swaName string = 'swa-crm-dev-scus-001'

@description('SKU for the Static Web App')
param sku string = 'Free'

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

@description('Deployment token for the Static Web App')
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey

@description('Default hostname')
output defaultHostname string = staticWebApp.properties.defaultHostname
