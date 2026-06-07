targetScope = 'resourceGroup'

param location string = resourceGroup().location
param suffix string = '001'
param prefix string = 'order'
param enableFreeTier bool = false

var deploymentSuffix = '${suffix}${uniqueString(resourceGroup().id)}'

module storage 'modules/storage.bicep' = {
  name: 'storage-module'
  params: { location: location, suffix: deploymentSuffix, prefix: prefix }
}

module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos-module'
  params: { location: location, suffix: deploymentSuffix, prefix: prefix, enableFreeTier: enableFreeTier }
}

module acs 'modules/acs.bicep' = {
  name: 'acs-module'
  params: { location: location, suffix: deploymentSuffix, prefix: prefix }
}

module functionapp 'modules/functionapp.bicep' = {
  name: 'functionapp-module'
  params: {
    location: location
    suffix: deploymentSuffix
    prefix: prefix
    storageAccountName: storage.outputs.name
    cosmosEndpoint: cosmos.outputs.endpoint
    cosmosDatabaseName: cosmos.outputs.databaseName
  }
}

module eventgrid 'modules/eventgrid.bicep' = {
  name: 'eventgrid-module'
  params: {
    location: location
    suffix: deploymentSuffix
    prefix: prefix
    storageAccountId: storage.outputs.id
    functionAppId: functionapp.outputs.functionAppId
  }
}

module rbac 'modules/rbac.bicep' = {
  name: 'rbac-module'
  params: {
    functionPrincipalId: functionapp.outputs.functionPrincipalId
    prefix: prefix
    suffix: deploymentSuffix
  }
}

output storageAccountName string = storage.outputs.name
output functionAppName string = functionapp.outputs.functionAppName
output functionAppId string = functionapp.outputs.functionAppId
output cosmosEndpoint string = cosmos.outputs.endpoint
output cosmosDatabaseName string = cosmos.outputs.databaseName
output acsName string = acs.outputs.name
output functionPrincipalId string = functionapp.outputs.functionPrincipalId
