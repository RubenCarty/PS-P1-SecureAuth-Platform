from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from sqlalchemy import select

from .audit import audit_event
from .extensions import db, limiter
from .forms import ProductForm
from .models import AuditLog, Product
from .security import role_required
from .storage import ImageValidationError, ProductImageStorage, normalize_image

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/")
@role_required("Admin")
def dashboard():
    products = db.session.execute(
        select(Product).order_by(Product.created_at.desc())
    ).scalars().all()
    return render_template("admin/dashboard.html", products=products)


@admin_bp.route("/productos/nuevo", methods=["GET", "POST"])
@role_required("Admin")
@limiter.limit("20 per hour")
def product_create():
    form = ProductForm()
    if form.validate_on_submit():
        storage = ProductImageStorage()
        new_blob = None
        content_type = None
        if form.image.data and form.image.data.filename:
            if not storage.configured():
                form.image.errors.append("Azure Blob Storage no está configurado.")
                return render_template("admin/product_form.html", form=form, product=None)
            try:
                image = normalize_image(form.image.data, current_app.config["MAX_IMAGE_BYTES"])
                new_blob = storage.upload(image)
                content_type = image.content_type
            except ImageValidationError as exc:
                form.image.errors.append(str(exc))
                return render_template("admin/product_form.html", form=form, product=None)

        product = Product(
            name=form.name.data.strip(),
            description=form.description.data.strip(),
            category=form.category.data.strip(),
            price=form.price.data,
            stock=form.stock.data,
            active=form.active.data,
            image_blob_name=new_blob,
            image_content_type=content_type,
        )
        try:
            db.session.add(product)
            db.session.commit()
        except Exception:
            db.session.rollback()
            storage.delete(new_blob)
            raise
        audit_event("PRODUCT_CREATE", resource_type="product", resource_id=product.id)
        flash("Producto creado.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/product_form.html", form=form, product=None)


@admin_bp.route("/productos/<int:product_id>/editar", methods=["GET", "POST"])
@role_required("Admin")
@limiter.limit("30 per hour")
def product_edit(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        storage = ProductImageStorage()
        old_blob = product.image_blob_name
        new_blob = None
        new_content_type = None
        if form.image.data and form.image.data.filename:
            if not storage.configured():
                form.image.errors.append("Azure Blob Storage no está configurado.")
                return render_template("admin/product_form.html", form=form, product=product)
            try:
                image = normalize_image(form.image.data, current_app.config["MAX_IMAGE_BYTES"])
                new_blob = storage.upload(image)
                new_content_type = image.content_type
            except ImageValidationError as exc:
                form.image.errors.append(str(exc))
                return render_template("admin/product_form.html", form=form, product=product)

        product.name = form.name.data.strip()
        product.description = form.description.data.strip()
        product.category = form.category.data.strip()
        product.price = form.price.data
        product.stock = form.stock.data
        product.active = form.active.data
        if new_blob:
            product.image_blob_name = new_blob
            product.image_content_type = new_content_type
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            storage.delete(new_blob)
            raise
        if new_blob:
            storage.delete(old_blob)
        audit_event("PRODUCT_UPDATE", resource_type="product", resource_id=product.id)
        flash("Producto actualizado.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/product_form.html", form=form, product=product)


@admin_bp.post("/productos/<int:product_id>/desactivar")
@role_required("Admin")
@limiter.limit("30 per hour")
def product_disable(product_id: int):
    product = db.session.get(Product, product_id)
    if not product:
        abort(404)
    product.active = False
    db.session.commit()
    audit_event("PRODUCT_DISABLE", resource_type="product", resource_id=product.id)
    flash("Producto desactivado.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.get("/auditoria")
@role_required("Admin")
def audit_logs():
    logs = db.session.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    ).scalars().all()
    return render_template("admin/audit.html", logs=logs)
