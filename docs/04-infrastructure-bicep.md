# 04 — Infrastructure (Bicep)

## Resource Group

```
Name: rg-orderprocessing-${suffix}
Location: westeurope (or northeurope)
```

## Complete Resource List

| # | Resource | Bicep Type | SKU | Purpose |
|---|---|---|---|---|
| 1 | Storage Account | `Microsoft.Storage/storageAccounts` | `Standard_LRS` | Blob, Table, Static website |
| 2 | Blob Container `orders-inbox` | `blobServices/containers` | — | Event Grid source |
| 3 | Blob Container `$web` | `blobServices/containers` | — | Static website hosting |
| 4 | Table `ExpiredOrders` | `tableServices/tables` | — | Expired order log |
| 5 | Event Grid System Topic | `Microsoft.EventGrid/systemTopics` | — | BlobCreated routing |
| 6 | Event Grid Subscription | `systemTopics/eventSubscriptions` | — | Function endpoint |
| 7 | Function App | `Microsoft.Web/sites` | `Consumption (Y1)` | Python runtime |
| 8 | App Service Plan | `Microsoft.Web/serverfarms` | `Y1` | Consumption hosting |
| 9 | Application Insights | `Microsoft.Insights/components` | `Basic` | Telemetry |
| 10 | Cosmos DB Account | `Microsoft.DocumentDB/databaseAccounts` | `Free Tier` | Order + Counter + Status |
| 11 | Cosmos DB Database | `sqlDatabases` | — | `OrderProcessing` |
| 12 | Cosmos DB Container `Counter` | `sqlContainers` | 400 RU/s | Counter document |
| 13 | Cosmos DB Container `OrderStatus` | `sqlContainers` | 400 RU/s | Timeline status |
| 14 | Cosmos DB Container `Orders` | `sqlContainers` | 400 RU/s | Final orders |
| 15 | ACS | `Microsoft.Communication/communicationServices` | `Free` | SMS delivery |

## RBAC Role Assignments

| Identity | Scope | Role |
|---|---|---|
| Function App (System MI) | Storage Account | `Storage Blob Data Contributor` |
| Function App (System MI) | Storage Account | `Storage Table Data Contributor` |
| Function App (System MI) | Cosmos DB Account | `Cosmos DB Built-in Data Contributor` |
| Function App (System MI) | ACS | `ACS SMS Sender` |
| Function App (System MI) | App Insights | `Monitoring Metrics Publisher` |

## Bicep File Structure

```
infra/
├── main.bicep              # Top-level: RG + module calls + outputs
├── modules/
│   ├── storage.bicep       # Storage Account + containers + tables + static website
│   ├── eventgrid.bicep     # System Topic + subscription with filters
│   ├── functionapp.bicep   # Function App + App Insights + settings
│   ├── cosmos.bicep        # Cosmos DB Account + database + 3 containers
│   ├── acs.bicep           # Azure Communication Services (optional)
│   └── rbac.bicep          # All role assignments with principal_id
└── parameters.json         # Environment-specific parameters
```

## Main Bicep Template (skeleton)

```bicep
targetScope = 'subscription'

@minLength(3)
@maxLength(8)
param suffix string

param location string = 'westeurope'

var resourceGroupName = 'rg-orderprocessing-${suffix}'
var storageAccountName = 'storder${suffix}'
var functionAppName = 'func-order-${suffix}'
var cosmosAccountName = 'cosmos-order-${suffix}'
var appInsightsName = 'appi-order-${suffix}'
var acsName = 'acs-order-${suffix}'

// Create Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
}

// Deploy modules
module storage './modules/storage.bicep' = {
  name: 'storage-module'
  scope: rg
  params: {
    storageAccountName: storageAccountName
    location: location
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos-module'
  scope: rg
  params: {
    cosmosAccountName: cosmosAccountName
    location: location
  }
}

// ... eventgrid, functionapp, acs, rbac modules

output functionAppName string = functionAppName
output storageAccountName string = storageAccountName
output cosmosEndpoint string = cosmos.outputs.endpoint
```

## Key Bicep Snippets

### Storage Static Website

```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
}

resource staticWebsite 'Microsoft.Storage/storageAccounts/staticWebsite@2023-01-01' = {
  name: 'default'
  parent: storageAccount
  properties: {
    indexDocument: 'index.html'
    errorDocument404Path: 'error.html'
  }
}
```

### Event Grid Subscription (with BlobCreated filter)

```bicep
resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  name: '${systemTopicName}/blob-to-function'
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: functionApp.outputs.id
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      subjectBeginsWith: '/blobServices/default/containers/orders-inbox/'
      includedEventTypes: ['Microsoft.Storage.BlobCreated']
    }
  }
}
```

### Cosmos DB Free Tier + Containers

```bicep
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    enableFreeTier: true
    databaseAccountOfferType: 'Standard'
    locations: [{ locationName: location }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
  }
}

resource sqlDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: 'OrderProcessing'
}

resource counterContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: sqlDb
  name: 'Counter'
  properties: {
    resource: {
      id: 'Counter'
      partitionKey: { paths: ['/partitionKey'], kind: 'Hash' }
    }
    options: { throughput: 400 }
  }
}

resource statusContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: sqlDb
  name: 'OrderStatus'
  properties: {
    resource: {
      id: 'OrderStatus'
      partitionKey: { paths: ['/orderId'], kind: 'Hash' }
    }
    options: { throughput: 400 }
  }
}

resource ordersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: sqlDb
  name: 'Orders'
  properties: {
    resource: {
      id: 'Orders'
      partitionKey: { paths: ['/id'], kind: 'Hash' }
    }
    options: { throughput: 400 }
  }
}
```

## Post-Deployment Steps

```bash
# 1. Seed counter document (or let code auto-seed)
# 2. Set Function App settings
az functionapp config appsettings set \
  --name func-order-$SUFFIX \
  --resource-group rg-orderprocessing-$SUFFIX \
  --settings \
    COSMOS_DB_ENDPOINT="$(az cosmosdb show --name cosmos-order-$SUFFIX --query documentEndpoint -o tsv)" \
    COSMOS_DB_DATABASE="OrderProcessing" \
    COSMOS_DB_CONTAINER="Counter" \
    COSMOS_DB_STATUS_CONTAINER="OrderStatus" \
    COSMOS_DB_ORDERS_CONTAINER="Orders" \
    STORAGE_ACCOUNT_URL="https://storder$SUFFIX.blob.core.windows.net" \
    TABLE_NAME="ExpiredOrders" \
    CONFIRMATION_TIMEOUT_SECONDS="180" \
    SMS_PROVIDER="simulated"

# 3. Upload webapp to $web
az storage blob upload-batch \
  --account-name storder$SUFFIX \
  --auth-mode login \
  --destination '$web' \
  --source webapp/
```

## Verification Commands

```bash
# Test submit
curl -X POST "https://func-order-$SUFFIX.azurewebsites.net/api/submit_order" \
  -H "Content-Type: application/json" \
  -d '{...}'

# Check blob was created
az storage blob list --container-name orders-inbox --account-name storder$SUFFIX --auth-mode login

# Poll status
curl "https://func-order-$SUFFIX.azurewebsites.net/api/status?orderId=ORD-0042-abc123"

# Confirm
curl -X POST "https://func-order-$SUFFIX.azurewebsites.net/api/confirm_handler?instance_id=ORD-0042-abc123"

# Check Cosmos DB
az cosmosdb sql container show ...
```
