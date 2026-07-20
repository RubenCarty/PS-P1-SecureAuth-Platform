# Política y lista de verificación de seguridad

## Nunca hacer

- No concatenar entrada del usuario en SQL, ni siquiera para búsquedas u ordenamiento.
- No usar `Markup`, `|safe` o HTML introducido por usuarios.
- No permitir SVG, HTML, ejecutables o extensiones basadas únicamente en el nombre del archivo.
- No guardar `.env`, secretos, publish profiles, claves de Storage o contraseñas SQL en GitHub.
- No confiar en un rol enviado por el frontend.
- No ejecutar `flask db upgrade` automáticamente al arrancar la aplicación con la identidad de producción.

## Antes de entregar

- Ejecutar `pytest -q`.
- Ejecutar análisis de dependencias y SAST en GitHub.
- Confirmar que App Service tiene `HTTPS Only`, TLS mínimo 1.2 o superior y FTPS deshabilitado si no se usa.
- Confirmar que Blob no permite acceso público y que la identidad tiene solo `Storage Blob Data Contributor` en el contenedor/cuenta necesarios.
- Confirmar que Key Vault usa RBAC, soft delete y purge protection.
- Confirmar que Azure SQL restringe red y la identidad de la app solo pertenece a `db_datareader` y `db_datawriter`.
- Confirmar que únicamente usuarios asignados reciben el rol `Admin`.
- Probar IDOR, CSRF, XSS reflejado/almacenado, SQLi, carga de archivos, rate limiting y autorización horizontal/vertical.
