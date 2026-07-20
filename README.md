# SecureAuth Store

**Tienda virtual con autenticación Zero-Trust, MFA por correo y defensa en profundidad en 5 niveles**

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![Argon2id](https://img.shields.io/badge/Hash-Argon2id-4B275F)
![MFA](https://img.shields.io/badge/MFA-OTP%20por%20correo-0aa884)
![Tests](https://img.shields.io/badge/tests-32%20passed-2ea44f)

Proyecto final del curso **DD281 Programación Segura** —
Universidad Autónoma del Perú.

Tienda en línea (catálogo, carrito, checkout) construida sobre
un sistema de autenticación endurecido: contraseñas con
**Argon2id + salt + pepper**, **verificación en dos pasos por
correo** y controles de seguridad organizados en cinco niveles,
cada uno respaldado por pruebas automatizadas.

> El checkout es un simulador académico. No procesa dinero real
> ni almacena datos de tarjeta.

---

## Tabla de contenidos

- [Los 5 niveles de seguridad](#los-5-niveles-de-seguridad)
- [Stack](#stack)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Parte 1 — Despliegue local](#parte-1-despliegue-local)
  - [1.1 Requisitos](#11-requisitos)
  - [1.2 Obtener el código](#12-obtener-el-código)
  - [1.3 Entorno virtual](#13-entorno-virtual)
  - [1.4 Dependencias](#14-dependencias)
  - [1.5 Variables de entorno](#15-variables-de-entorno)
  - [1.6 Base de datos y catálogo](#16-base-de-datos-y-catálogo)
  - [1.7 Arrancar la aplicación](#17-arrancar-la-aplicación)
  - [1.8 Probar el flujo completo](#18-probar-el-flujo-completo)
  - [1.9 Pruebas automáticas](#19-pruebas-automáticas)
  - [1.10 Problemas frecuentes](#110-problemas-frecuentes)
- [Parte 2 — Despliegue en línea](#parte-2-despliegue-en-línea)
  - [2.1 Preparar el correo emisor](#21-preparar-el-correo-emisor)
  - [2.2 Verificar que no se suba nada sensible](#22-verificar-que-no-se-suba-nada-sensible)
  - [2.3 Subir a GitHub](#23-subir-a-github)
  - [2.4 Crear el servicio en Render](#24-crear-el-servicio-en-render)
  - [2.5 Completar las variables de correo](#25-completar-las-variables-de-correo)
  - [2.6 Qué hace el despliegue](#26-qué-hace-el-despliegue)
  - [2.7 Asegurar la instancia pública](#27-asegurar-la-instancia-pública)
  - [2.8 Verificar el despliegue](#28-verificar-el-despliegue)
  - [2.9 Limitaciones del plan gratuito](#29-limitaciones-del-plan-gratuito)
  - [2.10 Problemas frecuentes en el despliegue](#210-problemas-frecuentes-en-el-despliegue)
  - [2.11 Actualizar el despliegue](#211-actualizar-el-despliegue)
- [Contribuir](#contribuir)
- [Contexto académico](#contexto-académico)

---

## Los 5 niveles de seguridad

| Nivel | Control | Implementación |
|---|---|---|
| **1. Transporte** | HTTPS forzado, HSTS (1 año, preload), SMTP con STARTTLS | Flask-Talisman, `app/mailer.py` |
| **2. Almacenamiento** | Argon2id + salt único por usuario + **pepper** global fuera de la BD | `app/auth.py`, `PASSWORD_PEPPER` |
| **3. Sesión** | Cookies `HttpOnly` + `Secure` + `SameSite` + prefijo `__Host-`, rotación anti-fijación | `app/config.py` |
| **4. Aplicación** | **MFA por OTP al correo**, registro verificado, política de contraseñas, rate limiting, respuestas anti-enumeración | `app/auth.py`, Flask-Limiter |
| **5. Infraestructura** | CSP, `nosniff`, `X-Frame-Options: DENY`, CSRF, validación estricta de entradas | Flask-Talisman, Flask-WTF |

Además, el **carrito y el pago** aplican el mismo principio de
no confiar en el cliente: el total se recalcula en el servidor,
las cantidades se acotan al stock, el método de pago se valida
contra listas permitidas y de la tarjeta solo persisten los
últimos 4 dígitos.

Detalle completo de cada control, con el archivo y la prueba que
lo respalda, en **[`SECURITY.md`](SECURITY.md)**.

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + Flask 3.1 |
| Hash de contraseñas | Argon2id (`argon2-cffi`) |
| Segundo factor | OTP de 6 dígitos por SMTP |
| Formularios / CSRF | Flask-WTF |
| Rate limiting | Flask-Limiter |
| Cabeceras de seguridad | Flask-Talisman |
| ORM / migraciones | SQLAlchemy 2 + Flask-Migrate |
| Base de datos | SQLite (local) · PostgreSQL (producción) |
| Frontend | Jinja2 + CSS propio, sin frameworks |
| Servidor | Gunicorn |

---

## Estructura del proyecto

```
secureauth-store/
├── run.py                  # Punto de entrada (crea la app)
├── seed.py                 # Catálogo y usuarios de demostración
├── requirements.txt
├── render.yaml             # Blueprint de despliegue en Render
├── Dockerfile
├── .env.example            # Plantilla de variables de entorno
│
├── app/
│   ├── __init__.py         # Factory, Talisman, blueprints
│   ├── auth.py             # Login, pepper, MFA/OTP, registro
│   ├── mailer.py           # Envío SMTP con STARTTLS
│   ├── config.py           # Configuración por entorno
│   ├── models.py           # User, Product, Order, AuditLog
│   ├── store.py            # Catálogo, carrito, checkout
│   ├── admin.py            # Panel de administración (RBAC)
│   ├── audit.py            # Auditoría firmada con HMAC
│   ├── security.py         # Utilidades de seguridad
│   ├── storage.py          # Carga endurecida de imágenes
│   ├── forms.py            # Formularios y validación
│   ├── templates/          # Vistas Jinja2
│   └── static/
│       ├── css/app.css
│       └── uploads/        # 12 imágenes del catálogo
│
├── migrations/             # Esquema versionado
├── tests/                  # 29 pruebas de seguridad
├── azure/                  # Scripts para despliegue en Azure
├── SECURITY.md             # Los 5 niveles en detalle
└── ARCHITECTURE.md
```

---

# Parte 1 — Despliegue local

## 1.1 Requisitos

| Requisito | Comprobar con | Esperado |
|---|---|---|
| Python 3.12 | `py --version` | `3.12.x` |
| Git | `git --version` | cualquiera |

Si tenés 3.11 o 3.13 el proyecto funciona igual, pero el
pipeline de CI usa 3.12 y conviene igualarlo para evitar
diferencias de comportamiento.

## 1.2 Obtener el código

```bash
git clone https://github.com/<usuario>/PS-P1-SecureAuth-Platform.git
cd PS-P1-SecureAuth-Platform
```

> ⚠️ **No clones dentro de OneDrive, Google Drive o Dropbox.**
> La sincronización bloquea archivos de `.git` mientras están
> en uso y produce errores `Permission denied` al hacer push.
> Usá una ruta como `~/Dev/` o `C:\Dev\`.

Verificá que estás en el lugar correcto:

```bash
ls
```

Debe listar `run.py`, `seed.py`, `app/`, `requirements.txt`.

## 1.3 Entorno virtual

El comando de activación **depende de la terminal**:

<details>
<summary><b>Git Bash (MINGW64)</b></summary>

```bash
py -m venv .venv
source .venv/Scripts/activate
```
</details>

<details>
<summary><b>PowerShell</b></summary>

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea el script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```
</details>

<details>
<summary><b>CMD</b></summary>

```cmd
py -m venv .venv
.venv\Scripts\activate.bat
```
</details>

<details>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv .venv
source .venv/bin/activate
```
</details>

El prompt debe empezar con `(.venv)`. Confirmá que apunta a tu
máquina:

```bash
which python      # Git Bash / macOS / Linux
where python      # PowerShell / CMD
```

La ruta debe contener tu carpeta de usuario. Si aparece la de
otra persona, borrá `.venv` y recrealo: **los entornos
virtuales guardan rutas absolutas y no son portables** entre
equipos.

## 1.4 Dependencias

```bash
pip install -r requirements.txt
```

Tarda 1–2 minutos. El aviso final sobre una versión nueva de
pip es informativo, no un error.

## 1.5 Variables de entorno

```bash
cp .env.example .env
```

Generá **tres secretos distintos**:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Ejecutá ese comando tres veces y pegá cada resultado en su
línea del `.env`:

```dotenv
FLASK_SECRET_KEY=<primer valor>
AUDIT_HMAC_KEY=<segundo valor>
PASSWORD_PEPPER=<tercer valor>
```

> 🔑 **No reutilices el mismo valor en los tres.** Cada uno
> protege algo distinto: la firma de sesión, la firma de la
> auditoría y el hash de contraseñas. Si se filtra uno, los
> otros dos siguen cumpliendo su función.

El resto del `.env` puede quedarse como está: en local no hacen
falta Google OAuth, Azure ni SMTP.

## 1.6 Base de datos y catálogo

```bash
flask --app run.py db upgrade
python seed.py
```

`db upgrade` crea el esquema aplicando las migraciones.
`seed.py` carga 12 productos con sus imágenes y dos usuarios de
prueba. Es **idempotente**: podés correrlo varias veces sin
duplicar nada.

Salida esperada:

```
Productos creados: 12 (total en catálogo: 12)
Usuarios demo creados: 2
  admin@example.com   / Admin#Secure2026
  cliente@example.com / Cliente#Secure2026
```

## 1.7 Arrancar la aplicación

```bash
python run.py
```

Abrir <http://localhost:5000>.

> 📋 **Dejá esa terminal abierta.** Como en local no hay SMTP
> configurado, los códigos OTP se imprimen ahí.

### Usuarios de demostración

| Correo | Contraseña | Rol |
|---|---|---|
| `admin@example.com` | `Admin#Secure2026` | Admin |
| `cliente@example.com` | `Cliente#Secure2026` | Customer |

## 1.8 Probar el flujo completo

### Login con verificación en dos pasos

1. Clic en **Iniciar sesión**.
2. Ingresá `admin@example.com` / `Admin#Secure2026`.
3. La app redirige a `/auth/otp`: **la contraseña sola no dio
   acceso**.
4. Conseguí el código de 6 dígitos. Dónde buscarlo depende
   de tu `.env`:

   | Situación | Dónde aparece el código |
   |---|---|
   | Sin SMTP configurado (por defecto) | Consola de `run.py` |
   | SMTP configurado y funcionando | Bandeja de entrada del correo |
   | SMTP configurado pero con error | Consola de `run.py` |

   **Sin SMTP** — en la terminal verás:

   ```
   WARNING in mailer: [SMTP NO CONFIGURADO] Para admin@example.com
   Tu código de verificación es: 194674
   ```

   **Con SMTP fallando** — el error y, debajo, el respaldo:

   ```
   ERROR in mailer: Fallo al enviar correo a un destinatario.
   smtplib.SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted...')
   WARNING in mailer: [SMTP FALLÓ — MODO DESARROLLO] Para admin@example.com
   Tu código de verificación es: 194674
   ```

   > El respaldo en consola **solo existe en desarrollo**. En
   > producción, si el envío falla el acceso queda bloqueado:
   > un código de autenticación nunca debe escribirse en los
   > logs de un servidor. Por eso `check_smtp.py` debe pasar
   > antes de desplegar.

   Si el correo falla, diagnosticá con:

   ```bash
   python check_smtp.py
   ```

   Ver [diagnóstico de correo](#diagnóstico-de-correo).

5. Ingresá esos 6 dígitos → acceso concedido.

### Registro con verificación de correo

1. En el login, **Crear una cuenta**.
2. Probá una contraseña débil (`12345678`): debe rechazarla
   exigiendo mayúscula, número y símbolo.
3. Con una válida (12+ caracteres, cuatro clases de
   caracteres), envía al paso OTP igual que el login.

### Compra completa

1. Con sesión de `cliente@example.com`, abrí el **Catálogo**.
2. Clic en **Agregar al carrito** en cualquier tarjeta. El
   icono 🛒 de la barra superior muestra un contador con las
   unidades acumuladas.
3. Abrí el **carrito** desde ese icono.
4. Cambiá la cantidad y pulsá **Actualizar** — el contador se
   ajusta. Probá también **Eliminar**.
5. **Proceder al pago**.
6. Completá el formulario según el método elegido:

   | Método | Datos de prueba |
   |---|---|
   | Tarjeta | Proveedor `Mastercard`, número `5555444433332226`, titular libre, vencimiento `12/30`, CVV `123` |
   | Tarjeta (Amex) | Proveedor `American Express`, número de 15 dígitos, CVV de 4 |
   | Billetera | Proveedor `Yape` o `Plin`, número de celular de 9 dígitos |

   > Son datos simulados. El sistema valida el formato pero no
   > contacta ninguna pasarela real.

7. Se genera el **voucher** y el pedido queda registrado en
   **Pedidos**. El carrito se vacía y el contador desaparece.

**Qué demostrar aquí:** con DevTools, agregá un campo `total`
al formulario de pago con un valor bajo. El pedido se crea
igualmente con el total correcto, porque el servidor lo
recalcula desde los precios de la base de datos.

### Panel de administración

Con `admin@example.com` entrá a
<http://localhost:5000/admin/>. Con `cliente@example.com` debe
responder **403**.

## 1.9 Pruebas automáticas

```bash
pytest -q     # 32 pruebas
pytest -v     # detalle una por una
```

**Cobertura:**

- **Autenticación** — pepper en los hashes, migración de hashes
  legados, ciclo completo de MFA (contraseña sola no da sesión,
  OTP incorrecto rechazado, bloqueo por intentos agotados,
  expiración del desafío), política de contraseñas y
  anti-enumeración en el registro.
- **Compra** — total recalculado en el servidor, cantidades
  acotadas al stock, método y proveedor validados contra listas
  permitidas, datos de tarjeta no persistidos, voucher ajeno
  inaccesible.
- **Aplicación** — cabeceras de seguridad, RBAC, SQLi tratada
  como dato y no como código, rechazo de SVG, CSRF, IDOR de
  carrito.

### Pruebas manuales sugeridas

| # | Prueba | Resultado esperado |
|---|---|---|
| 1 | Buscar `' OR 1=1--` | No devuelve todo el catálogo |
| 2 | Producto llamado `<script>alert(1)</script>` | Se muestra escapado |
| 3 | POST sin token CSRF | 400 |
| 4 | Customer en `/admin/` | 403 |
| 5 | `item_id` de otro usuario | 404 |
| 6 | Repetir login fallido | 429 |
| 7 | OTP incorrecto 5 veces | Desafío bloqueado |
| 8 | Alterar el total con DevTools | El cobro no cambia |
| 9 | Revisar la BD tras pagar | Solo los últimos 4 dígitos |

## 1.10 Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `bash: .venv/bin/activate: No such file` | Ruta de Linux en Windows | Usar `.venv/Scripts/activate` |
| `ModuleNotFoundError: argon2` | Entorno no activado | Reactivar el `.venv` |
| `Fatal error in launcher` con ruta ajena | `.venv` copiado de otra PC | Borrar `.venv` y recrearlo |
| Catálogo vacío | Falta el seed | `python seed.py` |
| Imágenes en gris | `app/static/uploads/` vacío | Verificar que el clon esté completo |
| `Permission denied` en git | Carpeta dentro de OneDrive | Mover fuera de la carpeta sincronizada |
| No llega el OTP | Sin SMTP, o SMTP con error | Está en la consola de `run.py`; para diagnosticar: `python check_smtp.py` |

---

# Parte 2 — Despliegue en línea

Objetivo: dejar la aplicación accesible por internet con HTTPS
válido, para que pueda probarse con cuentas de correo reales.

**Por qué Render y no Azure:** el proyecto incluye workflows
para Azure App Service, pero requieren suscripción con costo y
credenciales que GitHub no propaga a los forks. Render ofrece
plan gratuito con certificado TLS automático, PostgreSQL
administrada y despliegue desde GitHub. Alternativas
equivalentes: Railway, Fly.io o PythonAnywhere.

## 2.1 Preparar el correo emisor

**Hacer esto primero.** Sin SMTP la aplicación **no arranca**
en producción, por diseño: un MFA que no puede entregar el
código dejaría el sistema con un solo factor efectivo.

1. Entrar a [myaccount.google.com](https://myaccount.google.com) → **Seguridad**.
2. Activar la **verificación en 2 pasos** de esa cuenta
   (requisito de Google para el paso siguiente).
3. Ir a **Contraseñas de aplicaciones**
   ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
4. Crear una nueva, con nombre libre (ej. `SecureAuth Store`).
5. Copiar el valor de **16 caracteres**.

> ⚠️ Guardalo: solo se muestra una vez.

> 🔐 Se usa una contraseña de aplicación y **nunca** la
> contraseña personal, porque es revocable de forma individual
> y no da acceso al resto de la cuenta de Google. Si el
> servidor se compromete, se revoca esa sola credencial.

**Recomendación:** crear una cuenta de Gmail dedicada al
proyecto en vez de usar la personal.

> Gmail limita el envío a ~500 correos diarios, suficiente para
> una demostración académica. Para producción real conviene un
> servicio transaccional (Resend, Brevo, SendGrid) con dominio
> verificado y registros SPF/DKIM.

### Diagnóstico de correo

El proyecto incluye `check_smtp.py`, que prueba las
credenciales **sin pasar por la aplicación**:

```bash
python check_smtp.py                    # solo verifica el login
python check_smtp.py tu-correo@gmail.com  # además envía una prueba
```

Si devuelve `535 BadCredentials`, las causas por frecuencia:

1. **Se pegó la contraseña personal** en vez de una contraseña
   de aplicación.
2. **La verificación en 2 pasos no está activa** en la cuenta
   emisora. Google no permite crear contraseñas de aplicación
   sin ella, y si se desactiva después, las existentes dejan
   de funcionar.
3. **La contraseña tiene 16 caracteres**, no 4 grupos de 4.
   Google la muestra como `abcd efgh ijkl mnop`; el código
   elimina los espacios automáticamente, pero conviene
   verificar que no haya comillas alrededor del valor en el
   `.env`.
4. **`SMTP_USER` no es el correo completo** (falta `@gmail.com`).
5. **Cuenta de Google Workspace** con SMTP bloqueado por el
   administrador del dominio. En ese caso hay que usar una
   cuenta `@gmail.com` personal.

> Mientras el correo no funcione en local, el código OTP se
> escribe igualmente en la consola donde corre `run.py`, para
> que puedas seguir probando el flujo. En producción ese
> respaldo está desactivado a propósito.

## 2.2 Verificar que no se suba nada sensible

```bash
git status --short
git ls-files | grep -E "^\.env$"
```

El segundo comando **no debe devolver nada**. Si devuelve
`.env`:

```bash
git rm --cached .env
git commit -m "chore: excluir .env del control de versiones"
```

Y **rotá cualquier secreto** que hubiera estado dentro: queda
en el historial de git aunque borres el archivo.

Comprobá también que no viajen entornos ni cachés:

```bash
git ls-files | grep -E "\.venv|__pycache__|\.db$"
```

## 2.3 Subir a GitHub

Al ser trabajo grupal, en rama y por Pull Request:

```bash
git checkout -b feat/entrega-final
git add .
git commit -m "feat: entrega final con MFA por correo y despliegue"
git push -u origin feat/entrega-final
```

Luego abrir el PR hacia el repositorio del grupo. Ver
[Contribuir](#contribuir).

## 2.4 Crear el servicio en Render

1. Entrar a [render.com](https://render.com) → **New** → **Blueprint**.
2. Seleccionar el repositorio y la rama.
3. Render lee `render.yaml` y propone crear dos recursos:
   - servicio web `secureauth-store`
   - base de datos PostgreSQL `secureauth-db`
4. **Apply**.

`FLASK_SECRET_KEY`, `AUDIT_HMAC_KEY` y `PASSWORD_PEPPER` se
generan automáticamente (`generateValue: true`) y quedan
almacenados como secretos en la plataforma, nunca en el
repositorio.

`DATABASE_URL` se inyecta desde la base creada. El código
normaliza el esquema `postgres://` que entrega Render al
`postgresql+psycopg://` que espera SQLAlchemy 2.

## 2.5 Completar las variables de correo

> El primer despliegue **va a fallar** hasta que cargues estas
> tres variables. Es el comportamiento esperado.

Panel del servicio → **Environment**:

| Variable | Valor |
|---|---|
| `SMTP_USER` | la cuenta de Gmail emisora completa |
| `SMTP_PASSWORD` | la contraseña de aplicación de 16 caracteres |
| `MAIL_FROM` | `SecureAuth Store <esa-cuenta@gmail.com>` |

**Save Changes** dispara un redespliegue automático.

Si el log muestra:

```
RuntimeError: La configuración SMTP es obligatoria en producción
```

es que falta alguna de las tres.

## 2.6 Qué hace el despliegue

Según `render.yaml`:

| Fase | Comando |
|---|---|
| Build | `pip install -r requirements.txt` |
| Pre-deploy | `flask --app run.py db upgrade && python seed.py` |
| Start | `gunicorn --bind=0.0.0.0:$PORT --workers=2 --threads=4 "run:app"` |
| Health check | `GET /catalogo` |

La URL queda como `https://secureauth-store.onrender.com`
(Render agrega un sufijo si el nombre está tomado).

## 2.7 Asegurar la instancia pública

> 🚨 **Paso obligatorio.** `seed.py` crea `admin@example.com`
> con una contraseña publicada en este README. En una URL
> pública, cualquiera que lea el repositorio entra como
> administrador.

1. Registrate en la app con tu correo real y completá el OTP.
2. Promové esa cuenta a Admin. En Render: panel de la base de
   datos → **Connect** → copiar el comando `psql`:

   ```sql
   UPDATE users SET role = 'Admin'
   WHERE email = 'tu-correo@gmail.com';
   ```

3. Desactivá las cuentas de demostración:

   ```sql
   UPDATE users SET active = false
   WHERE email IN ('admin@example.com', 'cliente@example.com');
   ```

Quedan en la base para preservar la integridad referencial de
la auditoría, pero no pueden iniciar sesión.

## 2.8 Verificar el despliegue

Recorré esta lista y guardá capturas: son la evidencia de los
cinco niveles para la sustentación.

| # | Qué probar | Cómo | Esperado |
|---|---|---|---|
| 1 | HTTPS | abrir la URL | candado en la barra |
| 2 | Redirección | entrar con `http://` | redirige a `https://` |
| 3 | HSTS | DevTools → Network → Headers | `Strict-Transport-Security` |
| 4 | CSP | mismos headers | `Content-Security-Policy` |
| 5 | Cookie | DevTools → Application → Cookies | `__Host-secureauth` con `HttpOnly`, `Secure`, `SameSite=Lax` |
| 6 | Registro real | crear cuenta con tu Gmail | el código llega al buzón |
| 7 | MFA | contraseña correcta | redirige a `/auth/otp`, sin sesión |
| 8 | OTP inválido | código incorrecto | error, sin acceso |
| 9 | Bloqueo | fallar el OTP 5 veces | vuelve al login |
| 10 | Rate limit | 6 logins fallidos seguidos | HTTP 429 |
| 11 | RBAC | cuenta Customer en `/admin/` | 403 |
| 12 | Anti-enumeración | login con correo inexistente | mismo mensaje que con contraseña errada |
| 13 | Total del pedido | alterar el total con DevTools | el cobro no cambia |

### Informes externos

Sobre la URL pública, dos herramientas generan reportes
descargables que documentan los niveles 1 y 5:

- [securityheaders.com](https://securityheaders.com) — cabeceras de seguridad
- [ssllabs.com/ssltest](https://www.ssllabs.com/ssltest/) — configuración TLS

## 2.9 Limitaciones del plan gratuito

**El servicio se duerme.** Tras 15 minutos sin tráfico, la
primera petición tarda ~50 segundos. Abrí la URL varios minutos
antes de la exposición.

**Sistema de archivos efímero.** Las imágenes que subas desde
el panel admin se pierden en cada redespliegue. Las 12 del
catálogo están versionadas en `app/static/uploads/` y
sobreviven sin problema. Para cargas persistentes haría falta
Azure Blob Storage o un disco de pago.

**Vigencia de la base de datos.** Render aplica límites de
tiempo a las bases PostgreSQL gratuitas. Verificá la fecha de
expiración en el panel y anotala: si vence antes de la
sustentación, el sitio queda sin datos. Alternativas: Neon o
Supabase, cambiando solo `DATABASE_URL`.

## 2.10 Problemas frecuentes en el despliegue

| Error en el log | Causa | Solución |
|---|---|---|
| `SMTP es obligatorio en producción` | Faltan variables de correo | Cargar las tres de [2.5](#25-completar-las-variables-de-correo) |
| `PASSWORD_PEPPER es obligatorio` | No se generó el secreto | Revisar `render.yaml` |
| `Can't load plugin: sqlalchemy.dialects:postgres` | Esquema antiguo de URL | Verificar que se desplegó la versión con la normalización en `config.py` |
| `SMTPAuthenticationError (535 BadCredentials)` | Contraseña de aplicación incorrecta | Ver [diagnóstico de correo](#diagnóstico-de-correo) |
| El correo no llega | Filtro de spam | Revisar spam y agregar el emisor a contactos |
| `Application exited early` | Falló el pre-deploy | Revisar el log de esa fase |
| Deploy a Azure falla en un fork | GitHub no propaga secrets a forks | Comportamiento esperado; los checks relevantes son `test` y `security-checks` |

## 2.11 Actualizar el despliegue

Cada push a la rama conectada dispara un redespliegue
automático:

```bash
git add .
git commit -m "fix: descripción del cambio"
git push
```

Las migraciones se aplican solas en el pre-deploy.

> Para agregar productos al catálogo, editá `DEMO_PRODUCTS` en
> `seed.py`. Los que cargues desde el panel admin solo viven en
> la base y no se replican al redesplegar.

---

## Contribuir

El proyecto sigue un flujo de forks encadenados:

```
RubenCarty (profesor)  ←  anaastoac (repo del grupo)  ←  forks individuales
```

Cada integrante trabaja sobre su propio fork del repositorio
del grupo y envía Pull Request hacia él. La consolidación hacia
el repositorio del profesor se realiza desde ahí.

```bash
# configurar el remoto del repo del grupo
git remote add upstream https://github.com/anaastoac/PS-P1-SecureAuth-Platform.git

# sincronizar antes de empezar
git fetch upstream
git merge upstream/main

# trabajar en una rama por funcionalidad
git checkout -b feat/nombre-del-modulo
git add .
git commit -m "feat: descripción del cambio"
git push -u origin feat/nombre-del-modulo
```

Luego abrir el PR desde GitHub hacia
`anaastoac/PS-P1-SecureAuth-Platform:main`.

### Antes de abrir un PR

- [ ] `pytest -q` pasa completo
- [ ] `git ls-files` no incluye `.env`, `.venv` ni `__pycache__`
- [ ] No hay secretos ni credenciales en el código
- [ ] Los cambios de seguridad están documentados en `SECURITY.md`

---

## Contexto académico

Base aplicada del trabajo de investigación:

> **"Zero-Trust Behavioral Authentication: A Machine
> Learning-Enhanced Identity Verification Framework with
> Anomaly Detection for Continuous User Authentication in
> Cloud-Native Web Applications"**

Curso **DD281 Programación Segura** — Universidad Autónoma del
Perú. La tienda virtual es el caso de uso donde se implementa y
demuestra el motor de autenticación descrito en el paper.
