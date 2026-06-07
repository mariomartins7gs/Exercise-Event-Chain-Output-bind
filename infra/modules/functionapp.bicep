param location string
param suffix string
param prefix string
param storageAccountName string
param cosmosEndpoint string
param cosmosDatabaseName string
param acsPhoneNumber string = ''

var functionName = 'func-${prefix}-${suffix}'

resource hostingPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'asp-${prefix}-${suffix}'
  location: location
  kind: 'linux'
  sku: { name: 'Y1', tier: 'Dynamic' }
  properties: { reserved: true }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}-${suffix}'
  location: location
  kind: 'web'
  properties: { Application_Type: 'web' }
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionName
  location: location
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: hostingPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      alwaysOn: false
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'COSMOS_DB_ACCOUNT_ENDPOINT', value: cosmosEndpoint }
        { name: 'COSMOS_DB_DATABASE_NAME', value: cosmosDatabaseName }
        { name: 'COSMOS_DB_CONTAINER_ORDERS', value: 'Orders' }
        { name: 'COSMOS_DB_CONTAINER_STATUS', value: 'OrderStatus' }
        { name: 'SMS_PROVIDER', value: 'azure' }
        { name: 'ACS_PHONE_NUMBER', value: acsPhoneNumber }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'ENABLE_ORYX_BUILD', value: 'true' }
      ]
    }
  }
}

output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionPrincipalId string = functionApp.identity.principalId
output appInsightsId string = appInsights.id
