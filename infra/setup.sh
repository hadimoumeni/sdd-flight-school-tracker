#!/usr/bin/env bash
# One-time initial setup (brief §7), run once by me with my own Azure account:
#   az login && gh auth login
#   AZURE_LOCATION=<region> [SQL_LOCATION=<region>] ./infra/setup.sh
#
# Use a region from YOUR subscription's "Allowed resource deployment regions" policy:
#   az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters"
# The free SQL offer is not in every region (not in spaincentral); if "az sql db create"
# says "free limit database is not supported", set SQL_LOCATION to another allowed region.
#
# After this, everything is created and updated only by the CD workflow.
# The script is safe to run again: every step checks or overwrites the same thing.
set -euo pipefail

PREFIX=hmoumeni-ieu2024
REPO=hadimoumeni/sdd-flight-school-tracker
RG="rg-$PREFIX"
LOCATION="${AZURE_LOCATION:?set AZURE_LOCATION to one of your allowed regions}"
SQL_LOCATION="${SQL_LOCATION:-$LOCATION}"
SQL_SERVER="$PREFIX-sql"
UI_STORAGE="${PREFIX//-/}ui"

# 1. Resource providers (once per subscription; takes a few minutes), then the resource group.
for NS in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace "$NS" --wait
done
az group create --name "$RG" --location "$LOCATION" --output none

# 2. The pipeline's identity: a user-assigned managed identity, Contributor on this
#    resource group only, trusted through OpenID Connect for runs on main only.
#    No Azure password exists anywhere.
az identity create --name "$PREFIX-github" --resource-group "$RG" --output none
CLIENT_ID=$(az identity show --name "$PREFIX-github" --resource-group "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show --name "$PREFIX-github" --resource-group "$RG" --query principalId -o tsv)
RG_ID=$(az group show --name "$RG" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID" --output none || true

# GitHub may send the subject with names or with numeric ids, so trust both forms.
OWNER_ID=$(gh api "repos/$REPO" --jq .owner.id)
REPO_ID=$(gh api "repos/$REPO" --jq .id)
# (Braces around every variable: in zsh, "$REPO:r..." would be read as a modifier.)
for SUBJECT in "repo:${REPO}:ref:refs/heads/main" \
               "repo:${REPO%%/*}@${OWNER_ID}/${REPO##*/}@${REPO_ID}:ref:refs/heads/main"; do
  NAME="main-$(echo "$SUBJECT" | shasum | cut -c1-8)"
  az identity federated-credential create --name "$NAME" --identity-name "$PREFIX-github" \
    --resource-group "$RG" --issuer https://token.actions.githubusercontent.com \
    --subject "$SUBJECT" --audiences api://AzureADTokenExchange --output none || true
done

# 3. Passwords: random hex, so they are safe inside a connection-string URL.
#    They go straight into GitHub secrets and are never written to a file. The admin
#    password is only needed by the Bicep deployment, which keeps the server's settings.
SQL_ADMIN_PASSWORD="Aa1-$(openssl rand -hex 16)"
MAINTENANCE_DB_PASSWORD="Aa1$(openssl rand -hex 16)"
SCHEDULING_DB_PASSWORD="Aa1$(openssl rand -hex 16)"

# 4. SQL server and the two databases (same settings as infra/main.bicep, which
#    manages them from then on): serverless Gen5 0.5-1 vCore, free offer, LRS backups.
az sql server create --name "$SQL_SERVER" --resource-group "$RG" --location "$SQL_LOCATION" \
  --admin-user sqladmin --admin-password "$SQL_ADMIN_PASSWORD" --minimal-tls-version 1.2 --output none
az sql server firewall-rule create --server "$SQL_SERVER" --resource-group "$RG" \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
for SERVICE in maintenance scheduling; do
  az sql db create --server "$SQL_SERVER" --resource-group "$RG" --name "$PREFIX-$SERVICE-db" \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1 \
    --min-capacity 0.5 --use-free-limit --free-limit-exhaustion-behavior AutoPause \
    --backup-storage-redundancy Local --output none
done

# 5. One contained user per database: it exists only inside its own database, so it
#    cannot reach the other one, and it has only what it needs: create and change tables
#    (migrations), read and write rows. My IP is allowed only while this runs.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create --server "$SQL_SERVER" --resource-group "$RG" \
  --name setup-my-ip --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" --output none
trap 'az sql server firewall-rule delete --server "$SQL_SERVER" --resource-group "$RG" --name setup-my-ip --output none' EXIT

sqlcmd() {  # sqlcmd from the SQL Server image, so nothing extra needs installing
  docker run --rm mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd \
    -S "$SQL_SERVER.database.windows.net" -U sqladmin -P "$SQL_ADMIN_PASSWORD" -b "$@"
}
for SERVICE in maintenance scheduling; do
  if [ "$SERVICE" = maintenance ]; then PASSWORD="$MAINTENANCE_DB_PASSWORD"; else PASSWORD="$SCHEDULING_DB_PASSWORD"; fi
  sqlcmd -d "$PREFIX-$SERVICE-db" -Q "
    IF USER_ID('${SERVICE}_user') IS NULL CREATE USER ${SERVICE}_user WITH PASSWORD = '${PASSWORD}'
    ELSE ALTER USER ${SERVICE}_user WITH PASSWORD = '${PASSWORD}';
    ALTER ROLE db_ddladmin ADD MEMBER ${SERVICE}_user;
    ALTER ROLE db_datareader ADD MEMBER ${SERVICE}_user;
    ALTER ROLE db_datawriter ADD MEMBER ${SERVICE}_user;"
done

# 6. GitHub Actions secrets and variables, read only by the CD workflow.
gh secret set AZURE_CLIENT_ID --repo "$REPO" --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID --repo "$REPO" --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --body "$(az account show --query id -o tsv)"
gh secret set SQL_ADMIN_PASSWORD --repo "$REPO" --body "$SQL_ADMIN_PASSWORD"
gh secret set MAINTENANCE_DB_PASSWORD --repo "$REPO" --body "$MAINTENANCE_DB_PASSWORD"
gh secret set SCHEDULING_DB_PASSWORD --repo "$REPO" --body "$SCHEDULING_DB_PASSWORD"
gh variable set AZURE_LOCATION --repo "$REPO" --body "$LOCATION"
gh variable set SQL_LOCATION --repo "$REPO" --body "$SQL_LOCATION"
gh variable set PREFIX --repo "$REPO" --body "$PREFIX"
gh variable set RESOURCE_GROUP --repo "$REPO" --body "$RG"
gh variable set UI_STORAGE --repo "$REPO" --body "$UI_STORAGE"

# 7. Reader on the resource group for the professors, so the deployment can be checked.
for PROFESSOR in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee "$PROFESSOR" --role Reader --scope "$RG_ID" --output none || true
done

echo "Setup done. Push to main to deploy."
