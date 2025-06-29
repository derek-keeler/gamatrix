@description('The name of the Static Web App')
param name string

@description('The location for the Static Web App')
param location string

@description('Allowed IP addresses/CIDR blocks for access restrictions')
param allowedCidrs array = []

@description('Tags to apply to the Static Web App')
param tags object = {}

resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    allowConfigFileUpdates: true
    stagingEnvironmentPolicy: 'Enabled'
    enterpriseGradeCdnStatus: 'Disabled'
  }
}

// Configure IP restrictions if provided
// Note: IP restrictions are available in Standard tier and above
resource accessRestrictionPolicy 'Microsoft.Web/staticSites/config@2023-01-01' = if (length(allowedCidrs) > 0) {
  name: 'networkAcls'
  parent: staticWebApp
  properties: {
    ipSecurityRestrictions: [for (cidr, index) in allowedCidrs: {
      ipAddress: cidr
      action: 'Allow'
      priority: 100 + index
      name: 'AllowedCIDR_${replace(cidr, '/', '_')}'
      description: 'Allow access from ${cidr}'
    }]
    defaultAction: length(allowedCidrs) > 0 ? 'Deny' : 'Allow'
  }
}

output id string = staticWebApp.id
output name string = staticWebApp.name
output url string = 'https://${staticWebApp.properties.defaultHostname}'
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey