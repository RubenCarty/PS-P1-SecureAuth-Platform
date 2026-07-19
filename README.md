# SecureAuth Platform — Tienda Online Segura

Proyecto académico listo para Visual Studio Code con Flask, Microsoft Entra ID, Azure SQL, Blob Storage privado, Key Vault, RBAC, CSRF, rate limiting, auditoría y CI/CD.

> El checkout crea un pedido simulado. No procesa tarjetas ni dinero real.

## 1. Abrir y ejecutar localmente

```powershell
cd secureauth-store
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

En macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Genera dos secretos locales y colócalos en `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 2. Registrar la aplicación en Microsoft Entra ID

1. Entra admin center → **App registrations** → **New registration**.
2. Tipo recomendado para el trabajo: cuentas de este directorio organizacional.
3. En **Authentication → Web**, agrega `http://localhost:5000/auth/callback`.
4. En **Certificates & secrets**, crea un secreto solo para desarrollo. Guarda el valor en `ENTRA_CLIENT_SECRET`.
5. Copia Tenant ID y Client ID a `.env`.
6. En **App roles**, crea `Admin` y `Customer` usando `azure/app_roles.json` como guía.
7. En **Enterprise applications → Users and groups**, asigna cada usuario al rol correspondiente.

Ejecuta:

```bash
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
python seed.py
flask --app run.py run --debug
```

Abre `http://localhost:5000`.

## 3. Protección contra SQL Injection

El proyecto no construye consultas SQL mediante concatenación. Ejemplos seguros:

```python
select(CartItem).where(
    CartItem.user_oid == current_user()["oid"],
    CartItem.product_id == product.id,
)
```

```python
sort_map = {
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
}
stmt = stmt.order_by(sort_map.get(sort_key, Product.created_at.desc()))
```

Los valores del usuario quedan enlazados como parámetros. Para elementos que no pueden parametrizarse, como una columna de ordenamiento, se usa una lista permitida. El test `test_sql_injection_payload_is_data_not_code` verifica un payload clásico.

## 4. Configurar Azure Blob Storage

1. Crea una Storage Account en `westus3` y un contenedor privado `product-images`.
2. Activa la identidad administrada de App Service.
3. Asigna a esa identidad `Storage Blob Data Contributor` con el alcance mínimo posible.
4. Configura `AZURE_STORAGE_ACCOUNT_URL=https://TUCUENTA.blob.core.windows.net`.
5. Mantén deshabilitado el acceso público del contenedor.

El backend lee como máximo 2 MB, verifica el contenido real, rechaza SVG, limita píxeles, corrige orientación, redimensiona y vuelve a codificar la imagen para eliminar metadatos y contenido no esperado. El nombre final es un UUID.

## 5. Configurar Azure SQL con identidad administrada

1. Crea Azure SQL Database y configura un administrador de Microsoft Entra.
2. Habilita la identidad administrada de App Service.
3. Ejecuta `azure/sql_least_privilege.sql` como administrador.
4. Configura App Service:

```text
DATABASE_URL=mssql+pyodbc://@SERVIDOR.database.windows.net/secureauth?driver=ODBC+Driver+18+for+SQL+Server&authentication=ActiveDirectoryMsi&Encrypt=yes&TrustServerCertificate=no
```

5. Restringe la red mediante firewall específico, integración de VNet y Private Endpoint cuando el presupuesto lo permita.
6. Ejecuta migraciones con una identidad separada; la identidad de ejecución no debe tener `db_owner`.

## 6. Configurar Key Vault

Crea estos secretos:

- `flask-secret-key`
- `audit-hmac-key`
- `entra-client-secret`

En App Service, habilita identidad administrada, asígnale `Key Vault Secrets User` y usa referencias como valores de configuración:

```text
FLASK_SECRET_KEY=@Microsoft.KeyVault(VaultName=MI-VAULT;SecretName=flask-secret-key)
AUDIT_HMAC_KEY=@Microsoft.KeyVault(VaultName=MI-VAULT;SecretName=audit-hmac-key)
ENTRA_CLIENT_SECRET=@Microsoft.KeyVault(VaultName=MI-VAULT;SecretName=entra-client-secret)
```

El código los lee como variables de entorno; no conoce la dirección del Vault ni contiene secretos.

## 7. App Service en westus3

- Runtime: Python 3.12 sobre Linux.
- Startup command: `./startup.sh`.
- HTTPS Only: activado.
- Minimum TLS Version: 1.2 o superior.
- Always On: activado si el plan lo permite.
- Health check: `/catalogo`.
- Variables: `APP_ENV=production`, URLs de Entra, SQL, Blob y referencias de Key Vault.
- Redirect URI de Entra: `https://TU-APP.azurewebsites.net/auth/callback`.
- Post logout URI: `https://TU-APP.azurewebsites.net/`.

## 8. GitHub Actions sin publish profile

El workflow `.github/workflows/deploy.yml` usa OIDC. Configura una identidad federada y agrega al repositorio únicamente:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`

La identidad del workflow debe tener `Website Contributor` solamente sobre la Web App o el grupo de recursos requerido.

## 9. Pruebas

```bash
pytest -q
```

Pruebas manuales mínimas:

1. SQLi: buscar `' OR 1=1--`; no debe devolver todos los productos ni producir error SQL.
2. XSS: crear un nombre `<script>alert(1)</script>`; debe mostrarse como texto escapado.
3. CSRF: eliminar el token de un POST; debe responder 400.
4. RBAC: usuario Customer en `/admin/`; debe responder 403.
5. IDOR: cambiar un `item_id` del carrito por el de otro usuario; debe responder 404.
6. Archivo: intentar SVG, archivo renombrado, imagen >2 MB o con dimensiones extremas; debe rechazarse.
7. Rate limit: repetir login/checkout hasta obtener 429.
8. Cabeceras: comprobar CSP, HSTS, `X-Frame-Options`, `nosniff` y `Permissions-Policy`.

Consulta también `ARCHITECTURE.md` y `SECURITY.md`.
