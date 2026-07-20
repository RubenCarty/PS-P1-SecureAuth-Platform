from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "email",
            name="uq_users_email",
        ),
        UniqueConstraint(
            "google_sub",
            name="uq_users_google_sub",
        ),
        Index(
            "ix_users_email",
            "email",
        ),
        Index(
            "ix_users_google_sub",
            "google_sub",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    google_sub: Mapped[str | None] = mapped_column(
        db.String(255),
        nullable=True,
    )

    email: Mapped[str] = mapped_column(
        db.String(254),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        db.String(120),
        nullable=False,
    )

    password_hash: Mapped[str | None] = mapped_column(
        db.String(500),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        db.String(20),
        nullable=False,
        default="Customer",
    )

    active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    banned_reason: Mapped[str | None] = mapped_column(
        db.String(300),
        nullable=True,
    )

    banned_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class Product(db.Model):
    __tablename__ = "products"

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_products_price_nonnegative",
        ),
        CheckConstraint(
            "stock >= 0",
            name="ck_products_stock_nonnegative",
        ),
        Index(
            "ix_products_active_created",
            "active",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        db.String(120),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        db.String(2000),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        db.String(80),
        nullable=False,
        default="General",
    )

    price: Mapped[Decimal] = mapped_column(
        db.Numeric(10, 2),
        nullable=False,
    )

    stock: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        index=True,
    )

    image_blob_name: Mapped[str | None] = mapped_column(
        db.String(300),
        nullable=True,
    )

    image_content_type: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    cart_items: Mapped[list["CartItem"]] = relationship(
        back_populates="product",
    )


class CartItem(db.Model):
    __tablename__ = "cart_items"

    __table_args__ = (
        UniqueConstraint(
            "user_oid",
            "product_id",
            name="uq_cart_user_product",
        ),
        CheckConstraint(
            "quantity > 0 AND quantity <= 20",
            name="ck_cart_quantity",
        ),
        Index(
            "ix_cart_user",
            "user_oid",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    user_oid: Mapped[str] = mapped_column(
        db.String(64),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        db.ForeignKey("products.id"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    product: Mapped["Product"] = relationship(
        back_populates="cart_items",
    )


class Order(db.Model):
    __tablename__ = "orders"

    __table_args__ = (
        Index(
            "ix_orders_user_created",
            "user_oid",
            "created_at",
        ),
        UniqueConstraint(
            "payment_reference",
            name="uq_orders_payment_reference",
        ),
    )
    

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    user_oid: Mapped[str] = mapped_column(
        db.String(64),
        nullable=False,
    )

    total: Mapped[Decimal] = mapped_column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
    )

    status: Mapped[str] = mapped_column(
        db.String(30),
        nullable=False,
        default="CREATED",
    )
    
    payment_method: Mapped[str | None] = mapped_column(
        db.String(30),
        nullable=True,
    )

    payment_provider: Mapped[str | None] = mapped_column(
        db.String(30),
        nullable=True,
    )

    payment_last4: Mapped[str | None] = mapped_column(
        db.String(4),
        nullable=True,
    )

    payment_reference: Mapped[str | None] = mapped_column(
        db.String(40),
        nullable=True,
    )



    created_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        nullable=False,
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_order_item_quantity",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_order_item_price",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    order_id: Mapped[int] = mapped_column(
        db.ForeignKey("orders.id"),
        nullable=False,
    )

    product_id: Mapped[int] = mapped_column(
        nullable=False,
    )

    product_name: Mapped[str] = mapped_column(
        db.String(120),
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        db.Numeric(10, 2),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        nullable=False,
    )

    order: Mapped["Order"] = relationship(
        back_populates="items",
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index(
            "ix_audit_created",
            "created_at",
        ),
        Index(
            "ix_audit_user",
            "user_oid",
        ),
        Index(
            "ix_audit_action",
            "action",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    request_id: Mapped[str] = mapped_column(
        db.String(64),
        nullable=False,
    )

    user_oid: Mapped[str | None] = mapped_column(
        db.String(64),
        nullable=True,
    )

    username: Mapped[str | None] = mapped_column(
        db.String(254),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        db.String(80),
        nullable=False,
    )

    resource_type: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        db.String(80),
        nullable=True,
    )

    success: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )

    ip_hash: Mapped[str | None] = mapped_column(
        db.String(64),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        db.String(300),
        nullable=True,
    )

    details: Mapped[str | None] = mapped_column(
        db.String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utcnow,
        nullable=False,
    )