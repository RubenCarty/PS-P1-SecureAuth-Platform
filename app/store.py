import re
import secrets
from decimal import Decimal
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy import or_, select, update
from sqlalchemy.orm import joinedload

from .audit import audit_event
from .extensions import db, limiter
from .models import (
    CartItem,
    Order,
    OrderItem,
    Product,
)
from .security import current_user, login_required
from .storage import ProductImageStorage


store_bp = Blueprint(
    "store",
    __name__,
)


def _clean_search(value: str) -> str:
    return " ".join(
        value.strip().split()
    )[:80]


def _escape_like(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _only_digits(value: str) -> str:
    return "".join(
        character
        for character in value
        if character.isdigit()
    )


# =========================================================
# CATÁLOGO
# =========================================================

@store_bp.get("/")
@store_bp.get("/catalogo")
def catalog():
    query_text = _clean_search(
        request.args.get("q", "")
    )

    sort_key = request.args.get(
        "sort",
        "newest",
    )

    page = request.args.get(
        "page",
        default=1,
        type=int,
    ) or 1

    page = max(
        1,
        min(page, 1000),
    )

    stmt = select(Product).where(
        Product.active.is_(True)
    )

    if query_text:
        escaped = _escape_like(
            query_text
        )

        pattern = f"%{escaped}%"

        stmt = stmt.where(
            or_(
                Product.name.ilike(
                    pattern,
                    escape="\\",
                ),
                Product.description.ilike(
                    pattern,
                    escape="\\",
                ),
                Product.category.ilike(
                    pattern,
                    escape="\\",
                ),
            )
        )

    sort_map = {
        "newest": Product.created_at.desc(),
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name": Product.name.asc(),
    }

    stmt = stmt.order_by(
        sort_map.get(
            sort_key,
            sort_map["newest"],
        )
    )

    pagination = db.paginate(
        stmt,
        page=page,
        per_page=12,
        error_out=False,
    )

    return render_template(
        "catalog.html",
        products=pagination.items,
        pagination=pagination,
        q=query_text,
        sort=(
            sort_key
            if sort_key in sort_map
            else "newest"
        ),
    )


@store_bp.get(
    "/producto/<int:product_id>"
)
def product_detail(product_id: int):
    product = db.session.get(
        Product,
        product_id,
    )

    if (
        not product
        or not product.active
    ):
        abort(404)

    return render_template(
        "product_detail.html",
        product=product,
    )


@store_bp.get(
    "/media/producto/<int:product_id>"
)
@limiter.limit("180 per minute")
def product_image(product_id: int):
    product = db.session.get(
        Product,
        product_id,
    )

    if (
        not product
        or not product.active
        or not product.image_blob_name
    ):
        abort(404)

    try:
        data, content_type = (
            ProductImageStorage()
            .download(
                product.image_blob_name
            )
        )

    except (
        FileNotFoundError,
        RuntimeError,
    ):
        abort(404)

    return send_file(
        BytesIO(data),
        mimetype=content_type,
        max_age=300,
        download_name=(
            f"producto-{product.id}"
        ),
        as_attachment=False,
    )


# =========================================================
# CARRITO
# =========================================================

@store_bp.get("/carrito")
@login_required
def cart():
    user_oid = str(
        current_user()["oid"]
    )

    items = db.session.execute(
        select(CartItem)
        .where(
            CartItem.user_oid == user_oid
        )
        .options(
            joinedload(
                CartItem.product
            )
        )
        .order_by(
            CartItem.created_at.desc()
        )
    ).scalars().all()

    total = sum(
        (
            item.product.price
            * item.quantity
            for item in items
        ),
        Decimal("0.00"),
    )

    return render_template(
        "cart.html",
        items=items,
        total=total,
    )


@store_bp.post(
    "/carrito/agregar/<int:product_id>"
)
@login_required
@limiter.limit("60 per minute")
def add_to_cart(product_id: int):
    product = db.session.get(
        Product,
        product_id,
    )

    if (
        not product
        or not product.active
    ):
        abort(404)

    quantity = request.form.get(
        "quantity",
        type=int,
    )

    if (
        quantity is None
        or quantity < 1
        or quantity > 20
    ):
        abort(400)

    if product.stock < quantity:
        flash(
            "No existe stock suficiente.",
            "error",
        )

        return redirect(
            url_for(
                "store.product_detail",
                product_id=product.id,
            )
        )

    user_oid = str(
        current_user()["oid"]
    )

    item = db.session.execute(
        select(CartItem).where(
            CartItem.user_oid == user_oid,
            CartItem.product_id == product.id,
        )
    ).scalar_one_or_none()

    if item:
        new_quantity = (
            item.quantity
            + quantity
        )

        if new_quantity > min(
            product.stock,
            20,
        ):
            flash(
                "La cantidad solicitada supera "
                "el stock o el límite de 20 unidades.",
                "error",
            )

            return redirect(
                url_for(
                    "store.product_detail",
                    product_id=product.id,
                )
            )

        item.quantity = new_quantity

    else:
        item = CartItem(
            user_oid=user_oid,
            product_id=product.id,
            quantity=quantity,
        )

        db.session.add(item)

    db.session.commit()

    audit_event(
        "CART_ADD",
        resource_type="product",
        resource_id=product.id,
        details={
            "quantity": quantity,
        },
    )

    flash(
        "Producto agregado al carrito.",
        "success",
    )

    return redirect(
        url_for("store.cart")
    )


@store_bp.post(
    "/carrito/actualizar/<int:item_id>"
)
@login_required
@limiter.limit("60 per minute")
def update_cart(item_id: int):
    user_oid = str(
        current_user()["oid"]
    )

    item = db.session.execute(
        select(CartItem)
        .where(
            CartItem.id == item_id,
            CartItem.user_oid == user_oid,
        )
        .options(
            joinedload(
                CartItem.product
            )
        )
    ).scalar_one_or_none()

    if not item:
        abort(404)

    quantity = request.form.get(
        "quantity",
        type=int,
    )

    if (
        quantity is None
        or quantity < 0
        or quantity > 20
    ):
        abort(400)

    if quantity == 0:
        db.session.delete(item)

    elif quantity > item.product.stock:
        flash(
            "La cantidad supera el stock disponible.",
            "error",
        )

        return redirect(
            url_for("store.cart")
        )

    else:
        item.quantity = quantity

    db.session.commit()

    audit_event(
        "CART_UPDATE",
        resource_type="cart_item",
        resource_id=item_id,
        details={
            "quantity": quantity,
        },
    )

    flash(
        "Carrito actualizado.",
        "success",
    )

    return redirect(
        url_for("store.cart")
    )


# =========================================================
# CHECKOUT Y PAGO SIMULADO
# =========================================================

@store_bp.route(
    "/checkout",
    methods=["GET", "POST"],
)
@login_required
@limiter.limit("10 per minute")
def checkout():
    user_oid = str(
        current_user()["oid"]
    )

    items = db.session.execute(
        select(CartItem)
        .where(
            CartItem.user_oid == user_oid
        )
        .options(
            joinedload(
                CartItem.product
            )
        )
        .order_by(
            CartItem.created_at.asc()
        )
    ).scalars().all()

    if not items:
        flash(
            "El carrito está vacío.",
            "error",
        )

        return redirect(
            url_for("store.cart")
        )

    # El total se calcula en el servidor.
    # Nunca se confía en un total enviado
    # desde el navegador.
    total = sum(
        (
            item.product.price
            * item.quantity
            for item in items
        ),
        Decimal("0.00"),
    )

    if request.method == "GET":
        return render_template(
            "checkout.html",
            cart_items=items,
            total=total,
        )

    payment_method = request.form.get(
        "payment_method",
        "",
    ).strip()

    provider = request.form.get(
        "provider",
        "",
    ).strip()

    card_providers = {
        "BCP",
        "BBVA",
        "Interbank",
        "Mastercard",
        "American Express",
    }

    wallet_providers = {
        "Yape",
        "Plin",
    }

    payment_last4 = None

    # -----------------------------------------------------
    # Tarjeta simulada
    # -----------------------------------------------------
    if payment_method == "card":
        if provider not in card_providers:
            flash(
                "Selecciona un proveedor de tarjeta válido.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        card_number = _only_digits(
            request.form.get(
                "card_number",
                "",
            )
        )

        cardholder = request.form.get(
            "cardholder",
            "",
        ).strip()

        expiry = request.form.get(
            "expiry",
            "",
        ).strip()

        cvv = _only_digits(
            request.form.get(
                "cvv",
                "",
            )
        )

        if not 3 <= len(cardholder) <= 120:
            flash(
                "Ingresa correctamente el nombre del titular.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        if not re.fullmatch(
            r"(0[1-9]|1[0-2])/\d{2}",
            expiry,
        ):
            flash(
                "La fecha debe utilizar el formato MM/AA.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        if provider == "American Express":
            valid_card = (
                len(card_number) == 15
                and len(cvv) == 4
            )
        else:
            valid_card = (
                len(card_number) == 16
                and len(cvv) == 3
            )

        if not valid_card:
            flash(
                "Los datos de la tarjeta simulada "
                "no tienen el formato correcto.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        # No guardamos el número completo,
        # CVV, titular ni vencimiento.
        payment_last4 = (
            card_number[-4:]
        )

    # -----------------------------------------------------
    # Yape o Plin simulado
    # -----------------------------------------------------
    elif payment_method == "wallet":
        if provider not in wallet_providers:
            flash(
                "Selecciona Yape o Plin.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        phone = _only_digits(
            request.form.get(
                "phone",
                "",
            )
        )

        validation_token = _only_digits(
            request.form.get(
                "validation_token",
                "",
            )
        )

        if (
            len(phone) != 9
            or not phone.startswith("9")
        ):
            flash(
                "Ingresa un celular válido "
                "de 9 dígitos.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        # Código fijo únicamente para
        # esta simulación académica.
        if validation_token != "123456":
            flash(
                "Código simulado incorrecto. "
                "Usa 123456.",
                "error",
            )

            return render_template(
                "checkout.html",
                cart_items=items,
                total=total,
            ), 400

        # Solo se conservan los últimos
        # cuatro dígitos del celular.
        payment_last4 = phone[-4:]

    else:
        flash(
            "Selecciona un método de pago.",
            "error",
        )

        return render_template(
            "checkout.html",
            cart_items=items,
            total=total,
        ), 400

    try:
        order = Order(
            user_oid=user_oid,
            total=Decimal("0.00"),
            status="PAID",
            payment_method=payment_method,
            payment_provider=provider,
            payment_last4=payment_last4,
            payment_reference=(
                "SIM-"
                + secrets.token_hex(6).upper()
            ),
        )

        db.session.add(order)
        db.session.flush()

        confirmed_total = Decimal(
            "0.00"
        )

        for item in items:
            # Actualización condicional para evitar
            # stock negativo si dos personas compran
            # al mismo tiempo.
            result = db.session.execute(
                update(Product)
                .where(
                    Product.id
                    == item.product_id,
                    Product.active.is_(True),
                    Product.stock
                    >= item.quantity,
                )
                .values(
                    stock=(
                        Product.stock
                        - item.quantity
                    )
                )
            )

            if result.rowcount != 1:
                raise ValueError(
                    "Stock insuficiente para "
                    f"{item.product.name}."
                )

            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product.id,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
            )

            db.session.add(order_item)

            confirmed_total += (
                item.product.price
                * item.quantity
            )

            db.session.delete(item)

        order.total = confirmed_total

        db.session.commit()

    except ValueError as exc:
        db.session.rollback()

        audit_event(
            "CHECKOUT_FAILED",
            success=False,
            details={
                "reason": str(exc)[:200],
            },
        )

        flash(
            str(exc),
            "error",
        )

        return redirect(
            url_for("store.cart")
        )

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Error procesando el pago simulado"
        )

        audit_event(
            "CHECKOUT_FAILED",
            success=False,
            details={
                "reason": "internal_error",
            },
        )

        flash(
            "No fue posible completar la compra.",
            "error",
        )

        return redirect(
            url_for("store.cart")
        )

    audit_event(
        "CHECKOUT_SUCCESS",
        resource_type="order",
        resource_id=order.id,
        details={
            "total": str(order.total),
            "method": payment_method,
            "provider": provider,
        },
    )

    flash(
        "Compra realizada correctamente. "
        "Se generó tu voucher.",
        "success",
    )

    return redirect(
        url_for(
            "store.receipt",
            order_id=order.id,
        )
    )


# =========================================================
# VOUCHER CON PROTECCIÓN ANTI-IDOR
# =========================================================

@store_bp.get(
    "/pedidos/<int:order_id>/voucher"
)
@login_required
def receipt(order_id: int):
    user_oid = str(
        current_user()["oid"]
    )

    order = db.session.execute(
        select(Order)
        .where(
            Order.id == order_id,
            Order.user_oid == user_oid,
        )
        .options(
            joinedload(
                Order.items
            )
        )
    ).unique().scalar_one_or_none()

    # Evita que un usuario cambie el ID
    # en la URL para ver pedidos ajenos.
    if order is None:
        abort(404)

    return render_template(
        "receipt.html",
        order=order,
    )


# =========================================================
# HISTORIAL DE PEDIDOS
# =========================================================

@store_bp.get("/pedidos")
@login_required
def orders():
    user_oid = str(
        current_user()["oid"]
    )

    user_orders = db.session.execute(
        select(Order)
        .where(
            Order.user_oid == user_oid
        )
        .options(
            joinedload(
                Order.items
            )
        )
        .order_by(
            Order.created_at.desc()
        )
    ).unique().scalars().all()

    return render_template(
        "orders.html",
        orders=user_orders,
    )