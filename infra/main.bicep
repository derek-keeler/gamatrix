targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name to prefix all resources')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Allowed IP addresses/CIDR blocks for Static Web App access restrictions')
param allowedCidrs array = [
  '127.0.0.1/32'
  '192.168.0.0/24'
]

// Main resource group
resource rg 'Microsoft.Resources/resourceGroups@2022-09-01' = {
  name: 'rg-${environmentName}'
  location: location
}

module staticWebApp 'core/security/staticwebapp.bicep' = {
  name: 'staticwebapp'
  scope: rg
  params: {
    name: 'swa-${environmentName}-gamatrix'
    location: location
    allowedCidrs: allowedCidrs
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output STATIC_WEB_APP_NAME string = staticWebApp.outputs.name
output STATIC_WEB_APP_URL string = staticWebApp.outputs.url
output STATIC_WEB_APP_DEPLOYMENT_TOKEN string = staticWebApp.outputs.deploymentToken