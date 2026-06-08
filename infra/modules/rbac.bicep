param functionPrincipalId string
param prefix string
param suffix string

var storageName = 'st${prefix}${suffix}'
var cosmosName = 'cosmos-${prefix}-${suffix}'
var acsName = 'acs-${prefix}-${suffix}'
var appInsightsName = 'appi-${prefix}-${suffix}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageName
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosName
}

resource acs 'Microsoft.Communication/communicationServices@2023-03-31' existing = {
  name: acsName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageName, functionPrincipalId, 'blobContributor')
  scope: storageAccount
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalType: 'ServicePrincipal'
  }
}

resource storageTableRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageName, functionPrincipalId, 'tableContributor')
  scope: storageAccount
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
    principalType: 'ServicePrincipal'
  }
}

resource storageQueueRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageName, functionPrincipalId, 'queueContributor')
  scope: storageAccount
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalType: 'ServicePrincipal'
  }
}

resource cosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmosAccount
  name: guid(cosmosName, functionPrincipalId, 'cosmosContributor')
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosAccount.id
  }
}

resource acsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acsName, functionPrincipalId, 'acsContributor')
  scope: acs
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
    principalType: 'ServicePrincipal'
  }
}

resource appInsightsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsightsName, functionPrincipalId, 'monitoringPublisher')
  scope: appInsights
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
    principalType: 'ServicePrincipal'
  }
}
