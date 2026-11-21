#!/usr/bin/env bash
# One-time initial setup (brief §7), run once by me with my own Azure account:
#   az login && gh auth login
#   AZURE_LOCATION=<one of your allowed regions> PROFESSOR_EMAIL=<email> ./infra/setup.sh
#
# After this, everything is created and updated only by the CD workflow.
# The script is safe to run again: every step checks or overwrites the same thing.
set -euo pipefail

PREFIX=hmoumeni-ieu2024
REPO=hadimoumeni/sdd-flight-school-tracker
RG="rg-$PREFIX"
LOCATION="${AZURE_LOCATION:?set AZURE_LOCATION (list yours with: az account list-locations -o table)}"
SQL_SERVER="$PREFIX-sql"

# 1. Resource group.
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
for SUBJECT in "repo:$REPO:ref:refs/heads/main" \
               "repo:${REPO%%/*}@$OWNER_ID/${REPO##*/}@$REPO_ID:ref:refs/heads/main"; do
  NAME="main-$(echo "$SUBJECT" | shasum | cut -c1-8)"
  az identity federated-credential create --name "$NAME" --identity-name "$PREFIX-github" \
    --resource-group "$RG" --issuer https://token.actions.githubusercontent.com \
    --subject "$SUBJECT" --audiences api://AzureADTokenExchange --output none || true
done

# 3. Passwords: random hex, so they are safe inside a connection-string URL.
#    They go straight into GitHub secrets and are never written to a file.
SQL_ADMIN_PASSWORD="Aa1-$(openssl rand -hex 16)"
MAINTENANCE_DB_PASSWORD="Aa1$(openssl rand -hex 16)"
SCHEDULING_DB_PASSWORD="Aa1$(openssl rand -hex 16)"

# 4. SQL server and the two databases (same settings as infra/main.bicep, which
#    manages them from then on): serverless Gen5 0.5-1 vCore, free offer, LRS backups.
az sql server create --name "$SQL_SERVER" --resource-group "$RG" --location "$LOCATION" \
  --admin-user sqladmin --admin-password "$SQL_ADMIN_PASSWORD" --minimal-tls-version 1.2 --output none
az sql server firewall-rule create --server "$SQL_SERVER" --resource-group "$RG" \
  --name AllowAzureServices --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0 --output none
for SERVICE in maintenance scheduling; do
  az sql db create --server "$SQL_SERVER" --resource-group "$RG" --name "$PREFIX-$SERVICE-db" \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 1 \
    --min-capacity 0.5 --use-free-limit --free-limit-exhaustion-behavior AutoPause \
    --backup-storage-redundancy Local --output none
done

# 5. One login per service, with access to its own database only (db_owner there, so it
#    can run its migrations). My IP is allowed only while this runs, then removed.
MY_IP=$(curl -s https://api.ipify.org)
az sql server firewall-rule create --server "$SQL_SERVER" --resource-group "$RG" \
  --name setup-my-ip --start-ip-address "$MY_IP" --end-ip-address "$MY_IP" --output none
trap 'az sql server firewall-rule delete --server "$SQL_SERVER" --resource-group "$RG" --name setup-my-ip --output none' EXIT

sqlcmd() {  # sqlcmd from the SQL Server image, so nothing extra needs installing
  docker run --rm mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd \
    -S "$SQL_SERVER.database.windows.net" -U sqladmin -P "$SQL_ADMIN_PASSWORD" -b "$@"
}
sqlcmd -d master -Q "
  IF SUSER_ID('maintenance_user') IS NULL CREATE LOGIN maintenance_user WITH PASSWORD = '$MAINTENANCE_DB_PASSWORD'
  ELSE ALTER LOGIN maintenance_user WITH PASSWORD = '$MAINTENANCE_DB_PASSWORD';
  IF SUSER_ID('scheduling_user') IS NULL CREATE LOGIN scheduling_user WITH PASSWORD = '$SCHEDULING_DB_PASSWORD'
  ELSE ALTER LOGIN scheduling_user WITH PASSWORD = '$SCHEDULING_DB_PASSWORD';"
for SERVICE in maintenance scheduling; do
  sqlcmd -d "$PREFIX-$SERVICE-db" -Q "
    IF USER_ID('${SERVICE}_user') IS NULL CREATE USER ${SERVICE}_user FOR LOGIN ${SERVICE}_user;
    ALTER ROLE db_owner ADD MEMBER ${SERVICE}_user;"
done

# 6. GitHub Actions secrets and variables, read only by the CD workflow.
gh secret set AZURE_CLIENT_ID --repo "$REPO" --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID --repo "$REPO" --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$REPO" --body "$(az account show --query id -o tsv)"
gh secret set SQL_ADMIN_PASSWORD --repo "$REPO" --body "$SQL_ADMIN_PASSWORD"
gh secret set MAINTENANCE_DB_PASSWORD --repo "$REPO" --body "$MAINTENANCE_DB_PASSWORD"
gh secret set SCHEDULING_DB_PASSWORD --repo "$REPO" --body "$SCHEDULING_DB_PASSWORD"
gh variable set AZURE_LOCATION --repo "$REPO" --body "$LOCATION"

# 7. Reader on the resource group for the professor, so the deployment can be checked.
if [ -n "${PROFESSOR_EMAIL:-}" ]; then
  az role assignment create --assignee "$PROFESSOR_EMAIL" --role Reader --scope "$RG_ID" --output none
fi

echo "Setup done. Push to main to deploy."
