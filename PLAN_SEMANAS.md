# Plan de trabajo S1–S8

## S1 — Arquitectura segura y entorno

- Crear repositorio, entorno virtual y estructura Flask con patrón application factory.
- Definir límites de confianza y diagrama en `ARCHITECTURE.md`.
- Configurar `.env`, `.gitignore`, cookies seguras y ambientes development/production.
- Crear recursos base en `westus3`: Resource Group, App Service Plan, Web App, Storage, SQL y Key Vault.
- Entregable: aplicación local mostrando el catálogo vacío y pruebas iniciales.

## S2 — OAuth 2.0 con Microsoft Entra ID

- Registrar aplicación Web y redirect URI.
- Implementar Authorization Code Flow con MSAL, PKCE, state y nonce.
- Rotar sesión después del login y almacenar solo claims mínimos.
- Crear roles `Admin` y `Customer`; asignarlos desde Enterprise Applications.
- Entregable: login/logout funcional y rutas protegidas.

## S3 — Backend Flask y modelos seguros

- Crear modelos Product, CartItem, Order, OrderItem y AuditLog.
- Agregar validaciones, restricciones SQL e índices.
- Crear blueprints auth/store/admin y manejadores de errores.
- Entregable: CRUD local, carrito por usuario y auditoría.

## S4 — EP: autenticación funcional y store básico

- Completar catálogo, búsqueda, detalle, carrito y checkout simulado.
- Verificar control horizontal: cada usuario solo accede a su carrito/pedidos.
- Ejecutar demo con Entra y SQLite.
- Entregable: evidencia de login, catálogo, carrito y rol Admin.

## S5 — Azure SQL y anti-SQLi

- Crear Azure SQL Database y administrador Entra.
- Ejecutar migraciones con identidad controlada.
- Dar a la identidad de App Service solo `db_datareader` y `db_datawriter`.
- Validar payloads SQLi y listas permitidas de ordenamiento.
- Entregable: aplicación usando Azure SQL y reporte de pruebas SQLi.

## S6 — Azure Blob Storage

- Crear contenedor privado y asignar `Storage Blob Data Contributor`.
- Validar tamaño, formato real, píxeles y recodificar JPEG/PNG/WEBP.
- Rechazar SVG, extensiones falsas y archivos corruptos.
- Servir imágenes mediante el backend sin exponer el contenedor.
- Entregable: carga segura desde Admin y catálogo con imágenes.

## S7 — Key Vault y hardening

- Guardar secreto Flask, HMAC de auditoría y secreto Entra en Key Vault.
- Usar referencias de Key Vault en App Service.
- Activar HTTPS Only, HSTS, CSP, CSRF, rate limiting y headers.
- Configurar Redis si hay varias instancias.
- Entregable: checklist de hardening y evidencia de secretos fuera del código.

## S8 — EF: despliegue y pentesting

- Configurar GitHub Actions con OIDC y despliegue a App Service.
- Ejecutar pruebas automáticas y manuales: SQLi, XSS, CSRF, IDOR, RBAC, upload y rate limit.
- Revisar logs, request IDs y AuditLog.
- Corregir hallazgos y preparar exposición/demostración.
- Entregable: URL HTTPS, repositorio, informe de pruebas y presentación final.
