from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import Product

app = create_app()

with app.app_context():
    if Product.query.count() == 0:
        db.session.add_all(
            [
                Product(name="Audífonos Nova", description="Audífonos inalámbricos cómodos, con estuche de carga y sonido equilibrado.", category="Audio", price=Decimal("149.90"), stock=18),
                Product(name="Teclado Orbit", description="Teclado compacto para estudio y trabajo, con teclas silenciosas y conexión USB-C.", category="Accesorios", price=Decimal("189.00"), stock=12),
                Product(name="Mochila Urban Shield", description="Mochila resistente con compartimento acolchado para laptop y organización interior.", category="Estilo", price=Decimal("129.90"), stock=25),
            ]
        )
        db.session.commit()
        print("Productos de ejemplo creados.")
    else:
        print("La base ya contiene productos.")
