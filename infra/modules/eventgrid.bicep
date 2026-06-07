param location string
param suffix string
param prefix string
param storageAccountId string
param functionAppId string

resource systemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: 'evgt-${prefix}-${suffix}'
  location: location
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

resource eventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: systemTopic
  name: 'blob-created-sub'
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: functionAppId
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      includedEventTypes: ['Microsoft.Storage.BlobCreated']
      subjectBeginsWith: '/blobServices/default/containers/orders-inbox/'
      advancedFilters: []
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 3
      eventTimeToLiveInMinutes: 5
    }
  }
}
