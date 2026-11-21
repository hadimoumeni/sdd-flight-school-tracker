// Everything the system runs on, in the resource group rg-<prefix>.
// Deployed by the CD workflow on every push to main; running it again changes
// only what differs (Bicep deployments are incremental), so data is never lost.
//
//   Log Analytics workspace   <prefix>-logs              container logs (pay per GB, 5 GB/month free)
//   Container Apps env        <prefix>-env               Consumption plan only
//   Container Apps            <prefix>-maintenance       0..1 replicas, public HTTPS
//                             <prefix>-scheduling        0..1 replicas, public HTTPS
//   SQL logical server        <prefix>-sql               one server, two databases
//   SQL databases             <prefix>-maintenance-db    serverless, free offer
//                             <prefix>-scheduling-db
//   Storage account           <prefix without hyphens>ui static website for the UI

@description('Username prefix, e.g. hmoumeni-ieu2024')
@minLength(3)
param prefix string

param location string = resourceGroup().location

@description('Image tag to deploy: the commit SHA')
param imageTag string

@description('Registry path, e.g. ghcr.io/hadimoumeni')
param registry string

param sqlAdminLogin string = 'sqladmin'

@secure()
param sqlAdminPassword string

@secure()
@description('Password of the maintenance_user login (created once in the initial setup)')
param maintenanceDbPassword string

@secure()
@description('Password of the scheduling_user login (created once in the initial setup)')
param schedulingDbPassword string

var storageName = '${replace(prefix, '-', '')}ui'
var sqlHost = '${prefix}-sql${environment().suffixes.sqlServerHostname}'

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource sql 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: '${prefix}-sql'
  location: location
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// "Allow Azure services": 0.0.0.0 - 0.0.0.0 is Azure's special rule for that.
resource allowAzure 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sql
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Serverless General Purpose Gen5, 0.5 to 1 vCore, on the free offer (auto-pause after
// 60 minutes, 32 GB, no cost; when the monthly free amount is used up it pauses instead
// of billing), locally redundant backups.
resource databases 'Microsoft.Sql/servers/databases@2023-08-01-preview' = [
  for service in ['maintenance', 'scheduling']: {
    parent: sql
    name: '${prefix}-${service}-db'
    location: location
    sku: {
      name: 'GP_S_Gen5'
      tier: 'GeneralPurpose'
      family: 'Gen5'
      capacity: 1
    }
    properties: {
      minCapacity: json('0.5')
      useFreeLimit: true
      freeLimitExhaustionBehavior: 'AutoPause'
      requestedBackupStorageRedundancy: 'Local'
    }
  }
]

resource ui 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  // The prefix has letters, so the name is always longer than the 3-character minimum.
  #disable-next-line BCP334
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

// The UI's origin, e.g. https://hmoumeniieu2024ui.z6.web.core.windows.net (no trailing slash).
var uiOrigin = 'https://${split(ui.properties.primaryEndpoints.web, '/')[2]}'

module maintenance 'container-app.bicep' = {
  name: 'maintenance-app'
  params: {
    name: '${prefix}-maintenance'
    location: location
    environmentId: env.id
    image: '${registry}/flight-school-maintenance:${imageTag}'
    databaseUrl: 'mssql+pymssql://maintenance_user:${maintenanceDbPassword}@${sqlHost}:1433/${prefix}-maintenance-db'
    env: [
      { name: 'CORS_ORIGIN', value: uiOrigin }
      { name: 'GIT_SHA', value: imageTag }
    ]
  }
}

module scheduling 'container-app.bicep' = {
  name: 'scheduling-app'
  params: {
    name: '${prefix}-scheduling'
    location: location
    environmentId: env.id
    image: '${registry}/flight-school-scheduling:${imageTag}'
    databaseUrl: 'mssql+pymssql://scheduling_user:${schedulingDbPassword}@${sqlHost}:1433/${prefix}-scheduling-db'
    env: [
      { name: 'CORS_ORIGIN', value: uiOrigin }
      { name: 'GIT_SHA', value: imageTag }
      { name: 'MAINTENANCE_URL', value: 'https://${maintenance.outputs.fqdn}' }
      { name: 'MAINTENANCE_TIMEOUT_S', value: '2' }
    ]
  }
}

output maintenanceUrl string = 'https://${maintenance.outputs.fqdn}'
output schedulingUrl string = 'https://${scheduling.outputs.fqdn}'
output uiUrl string = uiOrigin
output storageAccount string = ui.name
