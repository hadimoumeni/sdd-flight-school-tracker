// One service as a Container App on the Consumption plan: public HTTPS ingress,
// scale to zero, at most one replica, DATABASE_URL passed as a secret.

param name string
param location string
param environmentId string
param image string

@secure()
param databaseUrl string

@description('Plain (non-secret) environment variables')
param env array

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  properties: {
    environmentId: environmentId
    configuration: {
      // Stored as a Container Apps secret and only referenced by name below, so the
      // connection string never appears as a plain environment variable.
      secrets: [
        { name: 'database-url', value: databaseUrl }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'app'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat(env, [
            { name: 'PORT', value: '8000' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
          ])
        }
      ]
      // 0 when idle (no cost); never more than 1, so the migrations that run at
      // startup can never run twice at the same time.
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
