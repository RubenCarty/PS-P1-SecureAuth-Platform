# TODO - SecureAuth

## Paso 1: Actualizar lógica de carrito
- [x] En `app.py` modificar `/cart/add` para redirigir siempre al catálogo (`url_for('index')`) y mostrar flash de éxito.

## Paso 2: Credenciales específicas
- [x] En `app.py` ajustar `init_db()` para inyectar (cuando la tabla `users` esté vacía):
  - `carlos.mendoza.92@outlook.com`
  - contraseña: `C4rl0s!2026Mx`
  - rol: `admin`

## Paso 3: Productos por categoría (varios)
- [x] En `app.py` ampliar `init_db()` para inyectar varios productos por cada categoría: Electrónica, Ropa, Hogar, Deportes, Libros, Otros.
  - Asegurar que se use la columna `category`.

## Paso 4: Filtrado en catálogo
- [x] En `templates/index.html` reemplazar inferencia por nombre para usar `product['category']`.
  - Usar `data-category` y badge basados en `product.category`.

## Paso 5: Verificación
- [ ] Correr `flask init-db` y validar:
  - Login con las credenciales pedidas.
  - Al agregar al carrito: flash + redirección al catálogo.
  - Filtrado por todas las categorías.


