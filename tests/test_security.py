from decimal import Decimal
from io import BytesIO

from app.extensions import db
from app.models import CartItem, Product
from app.storage import ImageValidationError, normalize_image
from werkzeug.datastructures import FileStorage


def test_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"].startswith("no-store")


def test_admin_requires_authentication(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_customer_cannot_access_admin(login_customer):
    response = login_customer.get("/admin/")
    assert response.status_code == 403


def test_sql_injection_payload_is_data_not_code(app, client):
    with app.app_context():
        db.session.add(Product(name="Producto visible", description="Descripción válida para la prueba.", category="Test", price=Decimal("10.00"), stock=3))
        db.session.commit()
    response = client.get("/catalogo", query_string={"q": "' OR 1=1--"})
    assert response.status_code == 200
    assert b"Producto visible" not in response.data


def test_svg_is_rejected():
    file = FileStorage(stream=BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'), filename="x.svg", content_type="image/svg+xml")
    try:
        normalize_image(file, 2 * 1024 * 1024)
    except ImageValidationError:
        pass
    else:
        raise AssertionError("SVG debe rechazarse")



def test_csrf_blocks_post_without_token(app, login_customer):
    app.config["WTF_CSRF_ENABLED"] = True
    response = login_customer.post("/checkout")
    assert response.status_code == 400


def test_cart_idor_is_blocked(app, login_customer):
    with app.app_context():
        product = Product(name="Privado", description="Producto usado para validar autorización horizontal.", category="Test", price=Decimal("20.00"), stock=5)
        db.session.add(product)
        db.session.flush()
        other_item = CartItem(user_oid="other-user", product_id=product.id, quantity=1)
        db.session.add(other_item)
        db.session.commit()
        item_id = other_item.id
    response = login_customer.post(f"/carrito/actualizar/{item_id}", data={"quantity": 2})
    assert response.status_code == 404
