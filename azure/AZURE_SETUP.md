# Configuración de Azure paso a paso

Use nombres únicos y la región `westus3` cuando el servicio la admita.

## 1. Grupo de recursos

```bash
az login
az account set --subscription "TU-SUSCRIPCION"
az group create --name rg-secureauth --location westus3
```

## 2. Storage privado

```bash
az storage account create \
  --name TUCUENTAUNICA \
  --resource-group rg-secureauth \
  --location westus3 \
  --sku Standard_LRS \
  --kind StorageV2 \
  --https-only true \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2
```

Cree el contenedor `product-images` desde Portal o Azure CLI autenticado con Entra.

## 3. Azure SQL

Cree el servidor y la base desde Portal, configure un administrador Microsoft Entra y limite la red. Para el laboratorio puede agregar temporalmente su IP pública; elimínela cuando ya no sea necesaria.

## 4. Key Vault

```bash
az keyvault create \
  --name TU-VAULT-UNICO \
  --resource-group rg-secureauth \
  --location westus3 \
  --enable-rbac-authorization true \
  --enable-purge-protection true
```

Cree secretos:

```bash
az keyvault secret set --vault-name TU-VAULT-UNICO --name flask-secret-key --value "VALOR_ALEATORIO"
az keyvault secret set --vault-name TU-VAULT-UNICO --name audit-hmac-key --value "OTRO_VALOR_ALEATORIO"
az keyvault secret set --vault-name TU-VAULT-UNICO --name entra-client-secret --value "SECRETO_ENTRA"
```

No coloque los valores en scripts versionados.

## 5. App Service

Cree un App Service Linux con Python 3.12 o despliegue el `Dockerfile` como contenedor personalizado. Active identidad administrada:

```bash
az webapp identity assign --resource-group rg-secureauth --name secureauth-store
```

Obtenga el `principalId` devuelto y asigne roles con el menor alcance posible:

- `Key Vault Secrets User` sobre el Vault.
- `Storage Blob Data Contributor` sobre la cuenta o el contenedor.
- En Azure SQL, ejecute `sql_least_privilege.sql`.

## 6. Variables de App Service

Configure al menos:

```text
APP_ENV=production
SCM_DO_BUILD_DURING_DEPLOYMENT=true
ENTRA_TENANT_ID=...
ENTRA_CLIENT_ID=...
ENTRA_CLIENT_SECRET=@Microsoft.KeyVault(VaultName=TU-VAULT-UNICO;SecretName=entra-client-secret)
ENTRA_REDIRECT_URI=https://secureauth-store.azurewebsites.net/auth/callback
ENTRA_POST_LOGOUT_URI=https://secureauth-store.azurewebsites.net/
FLASK_SECRET_KEY=@Microsoft.KeyVault(VaultName=TU-VAULT-UNICO;SecretName=flask-secret-key)
AUDIT_HMAC_KEY=@Microsoft.KeyVault(VaultName=TU-VAULT-UNICO;SecretName=audit-hmac-key)
AZURE_STORAGE_ACCOUNT_URL=https://TUCUENTAUNICA.blob.core.windows.net
AZURE_STORAGE_CONTAINER=product-images
DATABASE_URL=mssql+pyodbc://@SERVIDOR.database.windows.net/secureauth?driver=ODBC+Driver+18+for+SQL+Server&authentication=ActiveDirectoryMsi&Encrypt=yes&TrustServerCertificate=no
```

Active `HTTPS Only`, TLS mínimo 1.2 o superior y establezca `./startup.sh` como comando de inicio si usa despliegue de código.

## 7. ODBC

Compruebe desde SSH/Kudu:

```bash
odbcinst -q -d
```

Debe aparecer `ODBC Driver 18 for SQL Server`. Si no aparece, use el `Dockerfile` incluido, que instala el controlador explícitamente; es la opción más reproducible.

## 8. GitHub Actions con OIDC

Desde Deployment Center puede generar la identidad federada. El workflow requiere estos secretos no sensibles de identificación:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
```

No use publish profile como primera opción. La identidad de CI/CD debe tener `Website Contributor` solo sobre la Web App o el alcance mínimo necesario.
