param location string
param suffix string
param prefix string
param storageAccountId string

resource systemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: 'evgt-${prefix}-${suffix}'
  location: location
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

output systemTopicName string = systemTopic.name
output systemTopicId string = systemTopic.id
