"""
Datos de demostración para SecureAuth Store.

Crea el catálogo completo (12 productos con sus imágenes) y
dos usuarios locales de prueba con contraseñas hasheadas
mediante pepper + Argon2id.

Idempotente: puede ejecutarse varias veces sin duplicar datos.

Uso:
    python seed.py
"""

from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import Product, User

app = create_app()


DEMO_USERS = [
    {
        "email": "admin@example.com",
        "name": "Administrador Demo",
        "password": "Admin#Secure2026",
        "role": "Admin",
    },
    {
        "email": "cliente@example.com",
        "name": "Cliente Demo",
        "password": "Cliente#Secure2026",
        "role": "Customer",
    },
]


# Las imágenes viven en app/static/uploads/ y se versionan
# junto al proyecto para que la demo funcione sin Azure.
DEMO_PRODUCTS = [
    {
        "name": 'Audífonos Nova',
        "description": 'Audífonos inalámbricos cómodos, con estuche de carga y sonido equilibrado.',
        "category": 'Audio',
        "price": Decimal('149.9'),
        "stock": 18,
        "image_blob_name": 'e587f77bec124c9bb6d7c6649453d886.webp',
        "image_content_type": 'image/webp',
    },
    {
        "name": 'Teclado Orbit',
        "description": 'Teclado compacto para estudio y trabajo, con teclas silenciosas y conexión USB-C.',
        "category": 'Accesorios',
        "price": Decimal('189.9'),
        "stock": 12,
        "image_blob_name": '4a6de1aa796041a09f7a8aedb29669d1.webp',
        "image_content_type": 'image/webp',
    },
    {
        "name": 'Mochila Urban Shield',
        "description": 'Mochila resistente con compartimento acolchado para laptop y organización interior.',
        "category": 'Estilo',
        "price": Decimal('129.9'),
        "stock": 25,
        "image_blob_name": 'e5e8493cfa3b446bbb93df1c464d6737.webp',
        "image_content_type": 'image/webp',
    },
    {
        "name": 'Cámara Nexxt Home MM107NXT23 2K 5MP',
        "description": 'Cámara de seguridad interior',
        "category": 'Vigilancia',
        "price": Decimal('189.9'),
        "stock": 5,
        "image_blob_name": 'b13d5c0b9ffa4e98b681dc6768394281.webp',
        "image_content_type": 'image/webp',
    },
    {
        "name": 'Control Biometrico Zkteko K50',
        "description": 'Sistemas de Control de Acceso Biométrico',
        "category": 'Seguridad',
        "price": Decimal('228.9'),
        "stock": 15,
        "image_blob_name": '5661f2421b3c49528ae66ef9bff3c389.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Cerradura digital HAvern',
        "description": 'Cerradura digital HAvern Cerraduras Inteligentes para Racks de Servidores',
        "category": 'Seguridad',
        "price": Decimal('609.9'),
        "stock": 4,
        "image_blob_name": 'fef0a0a6d2804fcea95dd15b729641a6.webp',
        "image_content_type": 'image/webp',
    },
    {
        "name": 'Rack estándar de 30U RC1300',
        "description": 'El bastidor del rack consta de tres partes: columnas de aluminio extruido 6063 T5, vigas y conexiones entre vigas y columnas fabricadas en aleación de aluminio (ADC12) con soportes en forma de T.',
        "category": 'Servidor',
        "price": Decimal('1800.9'),
        "stock": 1,
        "image_blob_name": '5dd7ba5e53c340b4ba3a2d775fac27a0.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Dispositivo Flash USB Kingston IronKey Keypad 200',
        "description": 'FIPS 140-3 Nivel 3 validada con encriptado por hardware XTS-AES de 256 bits',
        "category": 'Seguridad',
        "price": Decimal('1389.9'),
        "stock": 7,
        "image_blob_name": '4dfadee2d95b411385d99dbd4da3deaf.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Caja de Disco Duro HDD de 2,5in Pulgadas SATA',
        "description": 'Permite convertir un Disco Duro o de Estado Sólido SATA de 2,5" en un disco duro cifrado con protección por contraseña a través de una pantalla táctil',
        "category": 'Accesorios',
        "price": Decimal('45'),
        "stock": 19,
        "image_blob_name": 'c5f05d9cd0ce4ec1b51227277842d39a.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Clave de seguridad FIDO2 U2F Passkey',
        "description": 'Clave de seguridad: Proteja sus cuentas en línea contra el acceso no autorizado utilizando la autenticación FIDO2 y U2F con T110.',
        "category": 'Seguridad',
        "price": Decimal('88.9'),
        "stock": 11,
        "image_blob_name": 'ae6d6a9cd6f7428cbdad688d556fa703.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Lector de tarjeta inteligente con ISO 7816',
        "description": 'Nuestro lector de tarjetas inteligentes CAC es un dispositivo USB fácil de instalar adecuado para todas las operaciones de tarjetas inteligentes como la banca en línea o las aplicaciones con firma digital',
        "category": 'Seguridad',
        "price": Decimal('100.9'),
        "stock": 4,
        "image_blob_name": 'ae88ee6d4d02473893bc7d41d44b8563.jpg',
        "image_content_type": 'image/jpeg',
    },
    {
        "name": 'Cat 7 Ethernet Cable 3 ft 6 Pack',
        "description": 'Construcción de alta calidad: Equipado con 4 pares trenzados blindados y conectores RJ45 chapados en oro, el cable Cat7 ofrece una protección superior contra la diafonía, las interferencias y la degradación de la señal, garantizando una conexión de red fiable y de alto rendimiento.',
        "category": 'Equipo',
        "price": Decimal('57.6'),
        "stock": 15,
        "image_blob_name": '57f236c1292f497ea097de3c09bbf48f.webp',
        "image_content_type": 'image/webp',
    },
]


with app.app_context():
    # El import va dentro del contexto: hash_password
    # necesita current_app para leer el pepper.
    from app.auth import hash_password, normalize_email

    created_users = 0
    for demo in DEMO_USERS:
        email = normalize_email(demo["email"])
        if db.session.query(User).filter_by(email=email).first() is None:
            db.session.add(
                User(
                    email=email,
                    name=demo["name"],
                    password_hash=hash_password(demo["password"]),
                    role=demo["role"],
                    active=True,
                )
            )
            created_users += 1

    created_products = 0
    for item in DEMO_PRODUCTS:
        exists = (
            db.session.query(Product)
            .filter_by(name=item["name"])
            .first()
        )
        if exists is None:
            db.session.add(Product(**item, active=True))
            created_products += 1

    db.session.commit()

    print(f"Productos creados: {created_products} "
          f"(total en catálogo: {Product.query.count()})")

    if created_users:
        print(f"Usuarios demo creados: {created_users}")
        print("  admin@example.com   / Admin#Secure2026")
        print("  cliente@example.com / Cliente#Secure2026")
    else:
        print("Los usuarios demo ya existían.")
