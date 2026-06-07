param location string
param suffix string
param prefix string
param enableFreeTier bool = false

var cosmosName = 'cosmos-${prefix}-${suffix}'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: enableFreeTier
    enableMultipleWriteLocations: false
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: { backupIntervalInMinutes: 240, backupRetentionIntervalInHours: 8 }
    }
  }
}

resource sqlDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: 'order-db'
  properties: { resource: { id: 'order-db' } }
}

resource ordersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: sqlDatabase
  name: 'Orders'
  properties: {
    resource: {
      id: 'Orders'
      partitionKey: { paths: ['/id'], kind: 'Hash' }
      defaultTtl: 2592000
    }
  }
}

resource orderStatusContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: sqlDatabase
  name: 'OrderStatus'
  properties: {
    resource: {
      id: 'OrderStatus'
      partitionKey: { paths: ['/orderId'], kind: 'Hash' }
      defaultTtl: 2592000
    }
  }
}

output id string = cosmosAccount.id
output endpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = sqlDatabase.name
