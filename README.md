<<<<<<< HEAD
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
=======
# PS-P1 — UQ·SecureID | Zero-Trust Authentication Platform
### DD281 Programación Segura · Universidad Autónoma del Perú · 2026-1 · UQ AI SOLUTION COMPANY SAC

[![Grupo](https://img.shields.io/badge/Grupo-G1-blue?style=for-the-badge)]()
[![Stack](https://img.shields.io/badge/Stack-Python%20%7C%20Flask%20%7C%20Azure-orange?style=for-the-badge)]()
[![Journal](https://img.shields.io/badge/Target-Computers_%26_Security_Q1-red?style=for-the-badge)]()
[![Demo](https://img.shields.io/badge/Demo-secureid.uqaisolutions.com.pe-green?style=for-the-badge)]()

---

## 🏆 Los 5 Títulos Scopus Q1 del Curso DD281-2026-1

> Todos los grupos del curso publican su investigación en journals Scopus Q1 al término del ciclo.
> El docente es coautor y guía el proceso de publicación.

| Grupo | Proyecto | Título Scopus Q1 Optimizado | Journal Target | Q |
|:---:|---|---|---|:---:|
| **G1** | UQ·SecureID | **"Zero-Trust Behavioral Authentication: A Machine Learning-Enhanced Identity Verification Framework with Anomaly Detection for Continuous User Authentication in Cloud-Native Web Applications"** | Computers & Security — Elsevier | **Q1** |
| G2 | UQ·FinSecure | "SecureFinAPI: A Hybrid Machine Learning and Rule-Based Fraud Detection System for RESTful Banking APIs Compliant with OWASP API Security Top 10" | J. Information Security & Applications — Elsevier | Q1 |
| G3 | UQ·HealthShield | "PrivacyShield: An End-to-End Encrypted Electronic Health Record System with Attribute-Based Access Control for HIPAA and Ley N°29733 Compliance" | J. Biomedical Informatics — Elsevier | Q1 |
| G4 | UQ·CivicVote | "CryptoVote: A Blockchain-Enhanced Electronic Voting Protocol with Zero-Knowledge Proof Verification for Tamper-Resistant and Privacy-Preserving Democratic Processes" | Future Generation Computer Systems — Elsevier | Q1 |
| G5 | UQ·AuditAI | "AutoPenTest-AI: An Artificial Intelligence-Driven Automated Web Penetration Testing Framework with Natural Language Vulnerability Reporting Based on OWASP Top 10" | IEEE Access — IEEE | Q1 |

---

## 📄 Tu Proyecto: G1 — UQ·SecureID

### Título Scopus Q1 Optimizado

> **"Zero-Trust Behavioral Authentication: A Machine Learning-Enhanced Identity Verification Framework with Anomaly Detection for Continuous User Authentication in Cloud-Native Web Applications"**
>
> 🎯 **Journal:** Computers & Security — Elsevier — **Q1** — Impact Factor: 5.1
> 🔗 **Verificar cuartil:** https://www.scimagojr.com/journalsearch.php?q=Computers+%26+Security

---

### ❗ Problema que Resuelve

El **80% de las brechas de seguridad** en aplicaciones web se originan en credenciales comprometidas (Verizon DBIR 2024). Los sistemas de autenticación tradicionales basados únicamente en contraseñas fallan porque:

1. **No detectan sesiones robadas**: si el atacante tiene el token, el sistema lo acepta como legítimo.
2. **No adaptan el nivel de verificación**: tratan igual a un login desde Lima a las 9am y uno desde Rusia a las 3am.
3. **No implementan Zero-Trust**: asumen que "dentro de la red = confiable".

**UQ·SecureID** resuelve esto con:
- Autenticación OAuth 2.0 via Microsoft Entra ID (sin contraseñas almacenadas en el servidor)
- Análisis de comportamiento en cada request con Isolation Forest + LOF
- Scoring de riesgo continuo que bloquea sesiones anómalas en tiempo real
- Principio Zero-Trust: "never trust, always verify"

---

### 🎯 Objetivo del Proyecto

**Objetivo General:**
Desarrollar e implementar una plataforma de autenticación Zero-Trust con detección de anomalías basada en Machine Learning, integrada con Microsoft Entra ID, que garantice acceso seguro a la tienda virtual de UQ AI SOLUTION COMPANY SAC y sirva como capa de autenticación para los proyectos G2–G5.

**Objetivos Específicos:**
1. Implementar el flujo OAuth 2.0 Authorization Code con protección anti-CSRF
2. Diseñar un modelo de detección de anomalías de login con Isolation Forest + LOF (≥85% F1-Score)
3. Construir el módulo de tienda virtual con prevención de IDOR, SQL Injection y price tampering
4. Configurar el pipeline CI/CD con análisis de seguridad automatizado (Bandit, detect-secrets)
5. Desplegar en Azure App Services bajo el dominio `secureid.uqaisolutions.com.pe`

---

## 📅 Plan de Desarrollo por Semanas (8 Semanas)

### Visión general

```
S1 → Diseño + Setup
S2 → OAuth 2.0 base
S3 → Tienda virtual segura
S4 ★ EP: Exposición 60%
S5 → Anomaly Detection ML
S6 → CI/CD + Azure Deploy
S7 → Integración G2-G5 + PenTest
S8 ★ EF: Presentación Final 100%
```

---

### SEMANA 1 — Setup, Arquitectura y Diseño de Seguridad

**Objetivo:** Tener el entorno listo y el diseño documentado antes de escribir código.

**Tareas del equipo:**
- [ ] Hacer fork del repositorio: `https://github.com/RubenCarty/PS-P1-SecureAuth-Platform`
- [ ] Cada integrante clona su fork y configura `upstream`
- [ ] Configurar entorno virtual Python 3.11 + instalar `requirements.txt`
- [ ] Crear el archivo `.env` a partir de `.env.example`
- [ ] Diagramar la arquitectura del sistema (draw.io o Mermaid)
- [ ] Realizar análisis de amenazas STRIDE para la plataforma de autenticación
- [ ] Documentar en `docs/semana-01/arquitectura.md` y `docs/semana-01/stride_analysis.md`

**Branch a crear:**
```bash
git checkout -b feature/S1-ApellidoNombre-setup-arquitectura
```

**PR hacia:** `main` del repo del docente
**Checklist PR S1:** arquitectura documentada + STRIDE completo + entorno corriendo localmente

---

### SEMANA 2 — Implementación OAuth 2.0 + Microsoft Entra ID

**Objetivo:** Login funcional con Microsoft sin almacenar contraseñas.

**Tareas del equipo:**
- [ ] Registrar la aplicación en Microsoft Entra ID (Azure Portal)
- [ ] Implementar `app/auth/oauth.py`: `get_authorization_url()`, `exchange_code_for_token()`
- [ ] Implementar verificación del parámetro `state` (anti-CSRF)
- [ ] Implementar `app/auth/routes.py`: `/login`, `/callback`, `/logout`, `/profile`
- [ ] Crear modelo `User` con `microsoft_oid` (sin campo password)
- [ ] Aplicar rate limiting a `/login` (máx 20/minuto)
- [ ] Template `login.html` con botón Microsoft y explicación de seguridad

**Branch a crear:**
```bash
git checkout -b feature/S2-ApellidoNombre-oauth-microsoft
```

**Tests mínimos:** verificación de state, usuario creado en BD, sesión iniciada

---

### SEMANA 3 — Tienda Virtual Segura (Prevención OWASP A01, A03, A04)

**Objetivo:** Módulo de tienda sin SQL Injection, IDOR ni price tampering.

**Tareas del equipo:**
- [ ] Implementar modelos `Product`, `CartItem`, `Order` con SQLAlchemy
- [ ] Ruta `add_to_cart()`: precio **siempre desde la BD**, nunca del formulario
- [ ] Ruta `remove_from_cart()`: filtrar por `user_id=current_user.id` (prevención IDOR)
- [ ] Búsqueda de productos con `ilike` via ORM (prevención SQL Injection)
- [ ] Upload de imágenes con validación 4 capas: extensión + MIME + python-magic + PIL
- [ ] Cabeceras de seguridad HTTP en todas las respuestas (CSP, X-Frame-Options, HSTS)
- [ ] Schema SQL en `database/schema.sql`

**Branch a crear:**
```bash
git checkout -b feature/S3-ApellidoNombre-tienda-segura
```

**Tests mínimos:** intento de price tampering rechazado, IDOR bloqueado, búsqueda con caracteres SQL

---

### SEMANA 4 ★ — EP: EVALUACIÓN PARCIAL (60% del proyecto)

**Objetivo:** Demo funcional con OAuth + tienda + seguridad básica implementada.

**Entregables OBLIGATORIOS:**
1. **Pull Request** en GitHub con todos los avances S1–S4 integrados en `main`
2. **Demo en vivo** (15 minutos por grupo):
   - Login con Microsoft (OAuth 2.0 completo)
   - Navegación en tienda virtual
   - Intentar SQL Injection en búsqueda (debe fallar)
   - Intentar price tampering (debe usar precio de BD)
   - Mostrar cabeceras de seguridad con DevTools
3. **Tests corriendo** en GitHub Actions (badge verde)

**Branch a crear:**
```bash
git checkout -b release/EP-S4-NombreGrupo
```

**Rúbrica EP (100 puntos):**
| Criterio | Puntos |
|---|:---:|
| OAuth 2.0 funcional con Entra ID | 30 |
| Tienda virtual con prevención de ataques | 20 |
| Cabeceras HTTP de seguridad correctas | 20 |
| Tests automatizados (cobertura ≥ 60%) | 15 |
| Documentación y diagrama de arquitectura | 15 |

---

### SEMANA 5 — Anomaly Detection con Machine Learning

**Objetivo:** Detectar logins sospechosos automáticamente con ML.

**Tareas del equipo:**
- [ ] Implementar `app/ml/anomaly_detector.py` con Isolation Forest + LOF
- [ ] Extraer 6 features por login: hora, día de semana, país, horas desde último login, intentos fallidos, user-agent hash
- [ ] Función `score_login()` → retorna score 0-1 + risk_level (low/medium/high) + recomendación
- [ ] Integrar scoring en `app/auth/routes.py` callback: log de riesgo en tabla `audit_logs`
- [ ] Endpoint `/admin/anomalies` con dashboard de logins de riesgo alto
- [ ] Tests: score bajo para login normal, score alto para login anómalo simulado

**Branch a crear:**
```bash
git checkout -b feature/S5-ApellidoNombre-ml-anomaly-detection
```

---

### SEMANA 6 — Azure Deploy + CI/CD Pipeline

**Objetivo:** App corriendo en `secureid.uqaisolutions.com.pe` con pipeline automatizado.

**Tareas del equipo:**
- [ ] Crear Azure App Service en Azure for Students (westus3)
- [ ] Configurar Azure Key Vault para secrets (no `.env` en producción)
- [ ] Configurar Azure SQL Database (migrar de SQLite)
- [ ] Configurar Azure Blob Storage para imágenes de productos
- [ ] Completar `.github/workflows/azure-deploy.yml`: tests → Bandit → Safety → deploy
- [ ] Configurar custom domain en Azure: `secureid.uqaisolutions.com.pe`
- [ ] Verificar SSL/HTTPS activo

**Branch a crear:**
```bash
git checkout -b feature/S6-ApellidoNombre-azure-deploy
```

---

### SEMANA 7 — Integración con G2–G5 + Pruebas de Penetración

**Objetivo:** SecureID autenticando a los otros grupos + audit de seguridad externo.

**Tareas del equipo:**
- [ ] Exponer endpoint `/api/auth/verify-token` para que G2, G3, G4 puedan validar tokens
- [ ] Solicitar al G5 (AuditAI) que escanee `secureid.uqaisolutions.com.pe`
- [ ] Revisar reporte de G5 y corregir los hallazgos encontrados
- [ ] Completar `docs/security_audit_s7.md` con evidencias de mitigación
- [ ] Prueba manual con OWASP ZAP o Burp Suite Community (instrucciones en docs/)

**Branch a crear:**
```bash
git checkout -b feature/S7-ApellidoNombre-integracion-pentest
```

---

### SEMANA 8 ★ — EF: EVALUACIÓN FINAL (Proyecto 100%)

**Objetivo:** Presentación y defensa del proyecto completo desplegado.

**Entregables OBLIGATORIOS:**
1. **Pull Request final** fusionado en `main` (todos los cambios integrados)
2. **Demo completa** (20 minutos):
   - Arquitectura explicada con diagrama
   - Demo live en `secureid.uqaisolutions.com.pe`
   - Flujo de anomaly detection con caso de login sospechoso
   - Pipeline CI/CD corriendo en tiempo real
   - Reporte de auditoría de G5 con mitigaciones aplicadas
3. **Paper draft** (borrador de artículo Scopus Q1, 4 páginas mínimo)

**Rúbrica EF (100 puntos):**
| Criterio | Puntos |
|---|:---:|
| Sistema completo desplegado en Azure | 25 |
| ML Anomaly Detection funcional con métricas | 20 |
| Integración OAuth 2.0 + Zero-Trust | 20 |
| CI/CD pipeline y DevSecOps | 15 |
| Borrador paper Scopus Q1 | 10 |
| Presentación y defensa técnica | 10 |

---

## 🔧 Flujo de Trabajo GitHub (Obligatorio)

### 1. Fork del repositorio
```
GitHub → https://github.com/RubenCarty/PS-P1-SecureAuth-Platform → Fork
```

### 2. Configurar tu fork localmente
```bash
git clone https://github.com/TU-USUARIO/PS-P1-SecureAuth-Platform.git
cd PS-P1-SecureAuth-Platform
git remote add upstream https://github.com/RubenCarty/PS-P1-SecureAuth-Platform.git
git fetch upstream
```

### 3. Sincronizar con el repo del docente antes de cada semana
```bash
git checkout main
git pull upstream main
git push origin main
```

### 4. Crear branch para tu trabajo semanal
```bash
# Formato OBLIGATORIO: feature/S{semana}-ApellidoNombre-descripcion
git checkout -b feature/S2-QuispeRuben-oauth-microsoft
```

### 5. Commit + Push + Pull Request
```bash
git add app/auth/oauth.py app/auth/routes.py
git commit -m "feat(S2): implement OAuth 2.0 callback with CSRF state verification"
git push origin feature/S2-QuispeRuben-oauth-microsoft
# → GitHub: "Compare & pull request" → base: RubenCarty/main
```

### 6. El docente revisa y aprueba/solicita cambios
- PRs se revisan los **viernes**
- El docente usa `gh pr review` con comentarios específicos
- Sin PR aprobado = entrega no registrada

---

## 📚 Repositorios de Referencia (Proyectos Similares)

Usa estos repos para guiarte en implementación. Lee el código, no lo copies.

### Autenticación y OAuth 2.0
| Repositorio | Qué aprender |
|---|---|
| [microsoft/ms-identity-python-webapp](https://github.com/Azure-Samples/ms-identity-python-webapp) | Integración oficial MSAL + Flask con Azure Entra ID |
| [Azure-Samples/ms-identity-python-flask-tutorial](https://github.com/Azure-Samples/ms-identity-python-flask-tutorial) | Tutorial paso a paso OAuth 2.0 con Flask |
| [pallets/flask](https://github.com/pallets/flask) | Framework base — leer blueprints y application factory |
| [maxcountryman/flask-login](https://github.com/maxcountryman/flask-login) | Gestión de sesiones seguras en Flask |

### Zero-Trust y Seguridad
| Repositorio | Qué aprender |
|---|---|
| [OWASP/CheatSheetSeries](https://github.com/OWASP/CheatSheetSeries) | Cheat sheets de autenticación, sesiones, CSRF |
| [PyCQA/bandit](https://github.com/PyCQA/bandit) | Análisis estático de seguridad Python |
| [jtesta/ssh-audit](https://github.com/jtesta/ssh-audit) | Modelo de arquitectura de scanner de seguridad |

### Machine Learning para Seguridad
| Repositorio | Qué aprender |
|---|---|
| [scikit-learn/scikit-learn](https://github.com/scikit-learn/scikit-learn) | IsolationForest y LocalOutlierFactor API |
| [elastic/detection-rules](https://github.com/elastic/detection-rules) | Reglas de detección de anomalías de seguridad |

### Azure + Flask Completo
| Repositorio | Qué aprender |
|---|---|
| [Azure-Samples/flask-postgresql-app](https://github.com/Azure-Samples/flask-postgresql-app) | Flask + PostgreSQL en Azure App Service |
| [Azure/azure-sdk-for-python](https://github.com/Azure/azure-sdk-for-python) | SDK oficial Azure: Key Vault, Blob, SQL |

---

## 🏗️ Estructura Completa del Proyecto

```
PS-P1-SecureAuth-Platform/
│
├── 📄 README.md                         ← Este archivo
├── 📄 CONTRIBUTING.md                   ← Leer ANTES de contribuir
├── 📄 requirements.txt                  ← Dependencias Python
├── 📄 .env.example                      ← Variables de entorno (sin secrets)
├── 📄 app.py                            ← Entry point (Gunicorn/Azure)
│
├── 📁 .github/
│   ├── PULL_REQUEST_TEMPLATE.md         ← Template obligatorio para PRs
│   └── workflows/
│       ├── ci.yml                       ← Tests + Security scan en cada PR
│       └── azure-deploy.yml             ← Deploy automático a Azure (S6+)
│
├── 📁 app/
│   ├── __init__.py                      ← Application factory create_app()
│   ├── extensions.py                    ← db, login_manager, csrf, limiter
│   │
│   ├── 📁 auth/
│   │   ├── oauth.py                     ← MSAL + state anti-CSRF
│   │   └── routes.py                    ← /login /callback /logout /profile
│   │
│   ├── 📁 models/
│   │   ├── user.py                      ← User(UserMixin) sin campo password
│   │   └── product.py                   ← Product, CartItem, Order
│   │
│   ├── 📁 store/
│   │   └── routes.py                    ← Tienda con prevención IDOR + SQLi
│   │
│   ├── 📁 admin/
│   │   └── routes.py                    ← Panel admin (solo rol admin)
│   │
│   ├── 📁 ml/
│   │   └── anomaly_detector.py          ← IsolationForest + LOF (S5)
│   │
│   └── 📁 utils/
│       ├── security.py                  ← Validación inputs, sanitización XSS
│       ├── storage.py                   ← Azure Blob Storage upload/delete
│       └── decorators.py                ← @admin_required, @active_user_required
│
├── 📁 templates/
│   ├── base.html                        ← Layout con cabeceras seguras
│   ├── auth/login.html
│   ├── store/index.html
│   └── admin/
│
├── 📁 database/
│   └── schema.sql                       ← Azure SQL (T-SQL) schema
│
├── 📁 docs/
│   ├── semana-01/arquitectura.md
│   ├── semana-01/stride_analysis.md
│   ├── semana-04/EP_evidencias/
│   ├── semana-08/EF_paper_draft.md
│   └── security_audit_s7.md
│
└── 📁 tests/
    ├── test_security.py                 ← Tests de seguridad (headers, validación)
    ├── test_auth.py                     ← Tests OAuth flow
    └── test_store.py                    ← Tests prevención ataques
```

---

## ⚡ Inicio Rápido (Local)

```bash
# 1. Fork + Clone
git clone https://github.com/TU-USUARIO/PS-P1-SecureAuth-Platform.git
cd PS-P1-SecureAuth-Platform

# 2. Entorno virtual
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales de Entra ID

# 5. Correr
flask run --port 8001
# → http://localhost:8001

# 6. Tests
pytest tests/ -v

# 7. Security scan
bandit -r app/ -ll
```

---

## 👥 Integrantes del Grupo G1

| # | Nombre | GitHub | Rol Técnico |
|:---:|---|---|---|
| 1 | [Completar] | [@usuario](https://github.com/usuario) | Líder / OAuth 2.0 + Auth |
| 2 | [Completar] | [@usuario](https://github.com/usuario) | Tienda Virtual + Modelos BD |
| 3 | [Completar] | [@usuario](https://github.com/usuario) | ML Anomaly Detection |
| 4 | [Completar] | [@usuario](https://github.com/usuario) | CI/CD + Azure Deploy |
| 5 | [Completar] | [@usuario](https://github.com/usuario) | Testing + Documentación |

---

## 👨‍🏫 Contacto Docente

- **Docente:** Mg. Ruben Quispe Llacctarimay
- **GitHub:** [@RubenCarty](https://github.com/RubenCarty)
- **Repo del curso:** [DD281-Programacion-Segura-2026-1](https://github.com/RubenCarty/DD281-Programacion-Segura-2026-1)
- **Demo G1:** [secureid.uqaisolutions.com.pe](https://secureid.uqaisolutions.com.pe)

---

*Universidad Autónoma del Perú — DD281 Programación Segura — 2026-1*
*UQ AI SOLUTION COMPANY SAC — Ciclo VIII — Ingeniería de Sistemas*
>>>>>>> b3f86e816f087e978efef383d2a3b29bf96cf4b3
