param location string
param suffix string
param prefix string

var acsName = 'acs-${prefix}-${suffix}'

resource acs 'Microsoft.Communication/communicationServices@2023-03-31' = {
  name: acsName
  location: 'Global'
  properties: { dataLocation: 'europe' }
}

output id string = acs.id
output name string = acs.name
