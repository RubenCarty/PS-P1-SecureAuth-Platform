"""
Pruebas de seguridad del carrito y el proceso de pago.

Demuestran que la lógica de compra no confía en el cliente:
el total se recalcula en el servidor, los datos sensibles de
tarjeta no se persisten, y un usuario no puede tocar el
carrito ni los pedidos de otro.
"""

import pytest
from decimal import Decimal

from app.extensions import db
from app.models import CartItem, Order, Product


VALID_CARD = {
    "payment_method": "card",
    "provider": "Mastercard",
    "card_number": "5555444433332226",
    "cardholder": "USUARIO PRUEBA",
    "expiry": "12/30",
    "cvv": "123",
}


@pytest.fixture()
def product(app):
    item = Product(
        name="Llave de seguridad de prueba",
        description="Producto usado por las pruebas de checkout.",
        category="Seguridad",
        price=Decimal("100.00"),
        stock=10,
        active=True,
    )
    db.session.add(item)
    db.session.commit()
    return item


@pytest.fixture()
def cart_with_item(login_customer, product):
    login_customer.post(
        f"/carrito/agregar/{product.id}",
        data={"quantity": 2},
    )
    return login_customer


# ---------------------------------------------------------
# El servidor no confía en el navegador
# ---------------------------------------------------------

def test_total_se_calcula_en_el_servidor(
    cart_with_item, product, app
):
    """Enviar un total manipulado no cambia el cobro."""
    cart_with_item.post(
        "/checkout",
        data={**VALID_CARD, "total": "1.00"},
    )

    order = db.session.query(Order).first()
    assert order is not None
    # 2 unidades x 100.00, no el 1.00 enviado por el cliente.
    assert Decimal(str(order.total)) == Decimal("200.00")


def test_cantidad_no_puede_superar_el_stock(
    login_customer, product
):
    response = login_customer.post(
        f"/carrito/agregar/{product.id}",
        data={"quantity": 999},
    )

    assert response.status_code in (302, 400)

    total_en_carrito = sum(
        i.quantity
        for i in db.session.query(CartItem).all()
    )
    assert total_en_carrito <= product.stock


def test_cantidad_negativa_es_rechazada(
    cart_with_item
):
    item = db.session.query(CartItem).first()

    response = cart_with_item.post(
        f"/carrito/actualizar/{item.id}",
        data={"quantity": -5},
    )

    assert response.status_code == 400


# ---------------------------------------------------------
# Datos de pago
# ---------------------------------------------------------

def test_no_se_almacenan_datos_sensibles_de_tarjeta(
    cart_with_item
):
    """Del pago solo deben quedar los últimos 4 dígitos:
    nunca el PAN completo, el CVV ni el titular."""
    cart_with_item.post("/checkout", data=VALID_CARD)

    order = db.session.query(Order).first()
    assert order is not None

    guardado = " ".join(
        str(v) for v in order.__dict__.values()
    )

    assert VALID_CARD["card_number"] not in guardado
    assert VALID_CARD["cvv"] not in guardado
    assert order.payment_last4 == "2226"


def test_tarjeta_invalida_es_rechazada(cart_with_item):
    """Un número que no pasa la validación no genera pedido."""
    cart_with_item.post(
        "/checkout",
        data={**VALID_CARD, "card_number": "1234"},
    )

    assert db.session.query(Order).count() == 0


def test_metodo_de_pago_desconocido_es_rechazado(
    cart_with_item
):
    cart_with_item.post(
        "/checkout",
        data={**VALID_CARD, "payment_method": "bitcoin"},
    )

    assert db.session.query(Order).count() == 0


def test_proveedor_fuera_de_la_lista_permitida(
    cart_with_item
):
    """El proveedor se valida contra una lista permitida,
    no se acepta texto arbitrario del formulario."""
    cart_with_item.post(
        "/checkout",
        data={**VALID_CARD, "provider": "BancoFalso"},
    )

    assert db.session.query(Order).count() == 0


# ---------------------------------------------------------
# Control de acceso
# ---------------------------------------------------------

def test_checkout_requiere_sesion(client, product):
    response = client.post("/checkout", data=VALID_CARD)

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_carrito_vacio_no_genera_pedido(login_customer):
    response = login_customer.post(
        "/checkout",
        data=VALID_CARD,
    )

    assert response.status_code == 302
    assert db.session.query(Order).count() == 0


def test_voucher_ajeno_no_es_accesible(
    cart_with_item, client
):
    """Un pedido solo lo ve su dueño (protección IDOR)."""
    cart_with_item.post("/checkout", data=VALID_CARD)
    order = db.session.query(Order).first()

    # Otra sesión, otro usuario.
    with client.session_transaction() as sess:
        sess["user"] = {
            "oid": "otro-usuario",
            "name": "Intruso",
            "username": "intruso@example.com",
            "roles": ["Customer"],
        }

    response = client.get(f"/pedidos/{order.id}/voucher")
    assert response.status_code == 404


# ---------------------------------------------------------
# Agregar al carrito desde el catálogo
# ---------------------------------------------------------

def test_agregar_al_carrito_requiere_sesion(client, product):
    """Sin sesión, el catálogo no expone el formulario de
    compra y la ruta redirige al login."""
    listado = client.get("/catalogo")
    assert b"Inicia sesi" in listado.data
    assert b"Agregar al carrito" not in listado.data

    response = client.post(
        f"/carrito/agregar/{product.id}",
        data={"quantity": 1},
    )
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_contador_del_carrito_es_por_usuario(
    cart_with_item, client, product
):
    """El contador de la barra refleja solo el carrito de
    quien tiene la sesión, nunca el de otro usuario."""
    propio = cart_with_item.get("/catalogo").data.decode()
    assert 'class="cart-badge">2<' in propio

    with client.session_transaction() as sess:
        sess["user"] = {
            "oid": "otro-usuario",
            "name": "Otro",
            "username": "otro@example.com",
            "roles": ["Customer"],
        }

    ajeno = client.get("/catalogo").data.decode()
    assert "cart-badge" not in ajeno


def test_producto_sin_stock_no_ofrece_compra(
    login_customer, product
):
    product.stock = 0
    db.session.commit()

    listado = login_customer.get("/catalogo").data.decode()
    assert "Sin stock" in listado
