from decimal import Decimal
from io import BytesIO

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import or_, select, update
from sqlalchemy.orm import joinedload

from .audit import audit_event
from .extensions import db, limiter
from .models import CartItem, Order, OrderItem, Product
from .security import current_user, login_required
from .storage import ProductImageStorage

store_bp = Blueprint("store", __name__)


def _clean_search(value: str) -> str:
    return " ".join(value.strip().split())[:80]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@store_bp.get("/")
@store_bp.get("/catalogo")
def catalog():
    query_text = _clean_search(request.args.get("q", ""))
    sort_key = request.args.get("sort", "newest")
    page = request.args.get("page", default=1, type=int) or 1
    page = max(1, min(page, 1000))

    stmt = select(Product).where(Product.active.is_(True))
    if query_text:
        escaped = _escape_like(query_text)
        pattern = f"%{escaped}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                Product.description.ilike(pattern, escape="\\"),
                Product.category.ilike(pattern, escape="\\"),
            )
        )

    sort_map = {
        "newest": Product.created_at.desc(),
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name": Product.name.asc(),
    }
    stmt = stmt.order_by(sort_map.get(sort_key, sort_map["newest"]))
    pagination = db.paginate(stmt, page=page, per_page=12, error_out=False)
    return render_template(
        "catalog.html",
        products=pagination.items,
        pagination=pagination,
        q=query_text,
        sort=sort_key if sort_key in sort_map else "newest",
    )


@store_bp.get("/producto/<int:product_id>")
def product_detail(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    return render_template("product_detail.html", product=product)


@store_bp.get("/media/producto/<int:product_id>")
@limiter.limit("180 per minute")
def product_image(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active or not product.image_blob_name:
        abort(404)
    try:
        data, content_type = ProductImageStorage().download(product.image_blob_name)
    except (FileNotFoundError, RuntimeError):
        abort(404)
    return send_file(
        BytesIO(data),
        mimetype=content_type,
        max_age=300,
        download_name=f"producto-{product.id}",
        as_attachment=False,
    )


@store_bp.get("/carrito")
@login_required
def cart():
    items = db.session.execute(
        select(CartItem)
        .where(CartItem.user_oid == current_user()["oid"])
        .options(joinedload(CartItem.product))
        .order_by(CartItem.created_at.desc())
    ).scalars().all()
    total = sum((item.product.price * item.quantity for item in items), Decimal("0.00"))
    return render_template("cart.html", items=items, total=total)


@store_bp.post("/carrito/agregar/<int:product_id>")
@login_required
@limiter.limit("60 per minute")
def add_to_cart(product_id: int):
    product = db.session.get(Product, product_id)
    if not product or not product.active:
        abort(404)
    quantity = request.form.get("quantity", type=int)
    if quantity is None or quantity < 1 or quantity > 20:
        abort(400)
    if product.stock < quantity:
        flash("No existe stock suficiente.", "error")
        return redirect(url_for("store.product_detail", product_id=product.id))

    item = db.session.execute(
        select(CartItem).where(
            CartItem.user_oid == current_user()["oid"],
            CartItem.product_id == product.id,
        )
    ).scalar_one_or_none()
    if item:
        new_quantity = item.quantity + quantity
        if new_quantity > min(product.stock, 20):
            flash("La cantidad solicitada supera el stock o el límite de 20 unidades.", "error")
            return redirect(url_for("store.product_detail", product_id=product.id))
        item.quantity = new_quantity
    else:
        item = CartItem(
            user_oid=current_user()["oid"], product_id=product.id, quantity=quantity
        )
        db.session.add(item)
    db.session.commit()
    audit_event("CART_ADD", resource_type="product", resource_id=product.id, details={"quantity": quantity})
    flash("Producto agregado al carrito.", "success")
    return redirect(url_for("store.cart"))


@store_bp.post("/carrito/actualizar/<int:item_id>")
@login_required
@limiter.limit("60 per minute")
def update_cart(item_id: int):
    item = db.session.execute(
        select(CartItem)
        .where(CartItem.id == item_id, CartItem.user_oid == current_user()["oid"])
        .options(joinedload(CartItem.product))
    ).scalar_one_or_none()
    if not item:
        abort(404)
    quantity = request.form.get("quantity", type=int)
    if quantity is None or quantity < 0 or quantity > 20:
        abort(400)
    if quantity == 0:
        db.session.delete(item)
    elif quantity > item.product.stock:
        flash("La cantidad supera el stock disponible.", "error")
        return redirect(url_for("store.cart"))
    else:
        item.quantity = quantity
    db.session.commit()
    audit_event("CART_UPDATE", resource_type="cart_item", resource_id=item_id, details={"quantity": quantity})
    flash("Carrito actualizado.", "success")
    return redirect(url_for("store.cart"))


@store_bp.post("/checkout")
@login_required
@limiter.limit("5 per minute")
def checkout():
    user_oid = current_user()["oid"]
    items = db.session.execute(
        select(CartItem)
        .where(CartItem.user_oid == user_oid)
        .options(joinedload(CartItem.product))
    ).scalars().all()
    if not items:
        flash("El carrito está vacío.", "error")
        return redirect(url_for("store.cart"))

    order = Order(user_oid=user_oid, total=Decimal("0.00"), status="CREATED")
    db.session.add(order)
    db.session.flush()
    total = Decimal("0.00")

    try:
        for item in items:
            result = db.session.execute(
                update(Product)
                .where(
                    Product.id == item.product_id,
                    Product.active.is_(True),
                    Product.stock >= item.quantity,
                )
                .values(stock=Product.stock - item.quantity)
            )
            if result.rowcount != 1:
                raise ValueError(f"Stock insuficiente para {item.product.name}")
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item.product.id,
                    product_name=item.product.name,
                    unit_price=item.product.price,
                    quantity=item.quantity,
                )
            )
            total += item.product.price * item.quantity
            db.session.delete(item)
        order.total = total
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        audit_event("CHECKOUT_FAILED", success=False, details={"reason": str(exc)[:200]})
        flash("No se pudo confirmar el pedido porque cambió el stock.", "error")
        return redirect(url_for("store.cart"))

    audit_event("CHECKOUT_SUCCESS", resource_type="order", resource_id=order.id, details={"total": str(total)})
    flash(f"Pedido #{order.id} creado correctamente. El pago es simulado.", "success")
    return redirect(url_for("store.orders"))


@store_bp.get("/pedidos")
@login_required
def orders():
    user_orders = db.session.execute(
        select(Order)
        .where(Order.user_oid == current_user()["oid"])
        .options(joinedload(Order.items))
        .order_by(Order.created_at.desc())
    ).unique().scalars().all()
    return render_template("orders.html", orders=user_orders)
