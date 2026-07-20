# Política y arquitectura de seguridad

SecureAuth Store implementa defensa en profundidad organizada
en **cinco niveles**. Cada control es verificable en el código
y está cubierto por la suite de pruebas (`pytest -q`).

## Nivel 1 — Transporte (cifrado en tránsito)

- HTTPS forzado en producción (`FORCE_HTTPS`, redirección
  automática vía Flask-Talisman).
- HSTS con `max-age` de 1 año, `includeSubDomains` y `preload`
  (`app/__init__.py`).
- TLS 1.3 / mínimo 1.2 se configura en la capa de terminación
  TLS (Azure App Service: *Minimum TLS Version*; en Render el
  certificado y TLS 1.3 son automáticos). Gunicorn corre detrás
  del proxy con `ProxyFix` para respetar `X-Forwarded-Proto`.
- El canal del segundo factor también va cifrado: el envío SMTP
  usa STARTTLS o SMTPS con verificación de certificado
  (`ssl.create_default_context()`), nunca texto plano.

## Nivel 2 — Almacenamiento (base de datos segura)

- Las contraseñas **nunca** se guardan en texto plano.
- Hash adaptativo **Argon2id** (`argon2-cffi`), con **salt único
  por usuario** embebido en cada hash.
- **Pepper** global del servidor (`PASSWORD_PEPPER`): la
  contraseña se procesa con `HMAC-SHA256(pepper, contraseña)`
  antes del hash. El pepper vive fuera de la base de datos
  (variable de entorno / Key Vault), de modo que una filtración
  de la BD no basta para atacar los hashes.
- Migración transparente: hashes creados antes del pepper se
  validan y se regeneran automáticamente en el primer login
  correcto (`app/auth.py: verify_password`).
- Re-hash automático si cambian los parámetros de Argon2
  (`check_needs_rehash`).

## Nivel 3 — Sesión (tokens y cookies)

- Cookie de sesión con `HttpOnly`, `Secure` (producción),
  `SameSite=Lax` y prefijo `__Host-` en producción
  (`app/config.py`).
- Rotación de sesión en cada login (`session.clear()` antes de
  emitir la nueva sesión) — mitiga fijación de sesión.
- Expiración corta configurable (`SESSION_MINUTES`, 30 por
  defecto) con refresco por request.
- No se usan JWT en el navegador; el estado viaja únicamente en
  la cookie firmada de Flask.

## Nivel 4 — Aplicación (lógica del login)

- **MFA por código OTP entregado por correo**: la contraseña
  correcta no concede la sesión; inicia un desafío de 6 dígitos
  con expiración de 5 minutos y máximo 5 intentos. En la sesión
  solo se guarda el HMAC del código, nunca el código en claro, y
  la comparación es de tiempo constante (`hmac.compare_digest`).
  El envío usa SMTP con STARTTLS (`app/mailer.py`); en producción
  la aplicación se niega a arrancar sin SMTP configurado, para
  que el segundo factor no quede inoperante.
- **Registro verificado**: el alta de cuenta también exige el
  código por correo, de modo que nadie puede registrarse con una
  dirección que no controla.
- **Política de contraseñas**: mínimo 12 caracteres con
  minúscula, mayúscula, número y símbolo (`RegisterForm`).
- **Interfaz sin fuga de datos**: en la pantalla de verificación
  el correo se muestra enmascarado (`p****l@gmail.com`).
- **Rate limiting** con Flask-Limiter: 5/min en login, 10/min en
  OTP, límites globales por IP.
- **Respuestas genéricas**: "Correo o contraseña incorrectos"
  sin distinguir el caso, y verificación contra un hash dummy
  cuando el usuario no existe, para igualar el tiempo de
  respuesta y evitar enumeración de usuarios. El registro
  responde igual exista o no la cuenta: si el correo ya está
  tomado, se avisa por correo al titular real en vez de
  revelarlo al visitante.
- Auditoría firmada (HMAC con `AUDIT_HMAC_KEY`) de cada evento:
  `LOGIN_PASSWORD_OK`, `LOGIN_SUCCESS`, `LOGIN_FAILED`,
  `MFA_FAILED`, `MFA_LOCKED`, `MFA_EXPIRED`.

## Nivel 5 — Infraestructura (servidor y cabeceras)

- **CSP** restrictiva, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy`
  vía Flask-Talisman.
- **CSRF** en todos los formularios (Flask-WTF), verificado por
  `test_csrf_blocks_post_without_token`.
- Validación y saneamiento estricto de entradas: WTForms con
  longitudes máximas, rangos numéricos y expresiones regulares;
  consultas 100% parametrizadas con SQLAlchemy (sin
  concatenación de SQL); listas permitidas para ordenamientos.
- Carga de imágenes endurecida: límite de 2 MB, verificación del
  contenido real, rechazo de SVG, recodificación que elimina
  metadatos, nombre final UUID.

## Seguridad del carrito y el pago

El proceso de compra aplica los mismos principios que la
autenticación: **nada de lo que envía el navegador se toma
como verdad**.

- **El total se recalcula en el servidor** a partir de los
  precios vigentes en la base de datos. Un total manipulado en
  el formulario se ignora (`test_total_se_calcula_en_el_servidor`).
- **Cantidades acotadas**: entre 1 y 20, y nunca por encima
  del stock disponible. Valores negativos devuelven 400.
- **Método y proveedor de pago validados contra listas
  permitidas**: `card` o `wallet`, y proveedor dentro del
  conjunto conocido. Texto arbitrario se rechaza.
- **No se almacenan datos sensibles de tarjeta.** Del pago solo
  persisten el método, el proveedor y los **últimos 4 dígitos**.
  El PAN completo, el CVV y la fecha de vencimiento nunca
  llegan a la base de datos
  (`test_no_se_almacenan_datos_sensibles_de_tarjeta`).
- **Sin autocompletado** en los campos de tarjeta
  (`autocomplete="off"`), para que el navegador no los conserve.
- **CSRF obligatorio** en agregar, actualizar y pagar.
- **Aislamiento entre usuarios (IDOR)**: cada consulta al
  carrito y a los pedidos filtra por el identificador del
  usuario en sesión. Un voucher ajeno devuelve 404, no 403,
  para no confirmar siquiera que el pedido existe.
- **Rate limiting** en checkout (10/min) y actualización de
  carrito (60/min).
- **Auditoría** de `CART_UPDATE` y de la creación del pedido.
- **Contador del carrito por sesión**: el número que aparece
  en la barra de navegación se calcula filtrando por el
  identificador del usuario en sesión, nunca por un parámetro
  del cliente (`test_contador_del_carrito_es_por_usuario`).
- **La interfaz no ofrece lo que el backend rechazaría**: sin
  sesión el catálogo muestra "Inicia sesión para comprar" en
  vez del botón de compra, y los productos sin stock no
  exponen el formulario. La restricción real sigue estando en
  el servidor: la interfaz solo evita el error innecesario.

> El checkout es un simulador académico: no procesa dinero real
> ni se conecta a una pasarela. Precisamente por eso los datos
> de tarjeta se descartan en vez de guardarse — en un sistema
> real esa información solo puede manejarla un proveedor
> certificado PCI DSS, nunca la aplicación.

## Reporte de vulnerabilidades

Si encuentras una vulnerabilidad, abre un *security advisory*
privado en GitHub o contacta al equipo del curso. No publiques
detalles en issues abiertos.
