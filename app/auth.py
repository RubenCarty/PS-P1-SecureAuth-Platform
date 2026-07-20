from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import select

from .audit import audit_event
from .extensions import db, limiter
from .forms import LoginForm
from .models import User
from .security import is_safe_relative_url


auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
)

password_hasher = PasswordHasher()

DUMMY_PASSWORD_HASH = password_hasher.hash(
    "Dummy-password-not-used-123!"
)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def verify_password(
    stored_hash: str,
    password: str,
) -> bool:
    try:
        return password_hasher.verify(
            stored_hash,
            password,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


@auth_bp.route(
    "/login",
    methods=["GET", "POST"],
)
@limiter.limit("5 per minute")
def login():
    if session.get("user"):
        return redirect(
            url_for("store.catalog")
        )

    form = LoginForm()
    next_url = request.args.get("next")

    if form.validate_on_submit():
        email = normalize_email(
            form.email.data
        )

        user = db.session.execute(
            select(User).where(
                User.email == email
            )
        ).scalar_one_or_none()

        hash_to_check = (
            user.password_hash
            if user is not None
            else DUMMY_PASSWORD_HASH
        )

        password_is_valid = verify_password(
            hash_to_check,
            form.password.data,
        )

        if (
            user is None
            or not user.active
            or not password_is_valid
        ):
            audit_event(
                "LOGIN_FAILED",
                success=False,
                details={
                    "reason": "invalid_credentials"
                },
            )

            flash(
                "Correo o contraseña incorrectos.",
                "error",
            )

            return render_template(
                "login.html",
                form=form,
            ), 401

        if password_hasher.check_needs_rehash(
            user.password_hash
        ):
            user.password_hash = (
                password_hasher.hash(
                    form.password.data
                )
            )
            db.session.commit()

        session.clear()
        session.permanent = True

        session["user"] = {
            "oid": str(user.id),
            "name": user.name,
            "username": user.email,
            "roles": [user.role],
        }

        audit_event(
            "LOGIN_SUCCESS",
            success=True,
        )

        destination = (
            next_url
            if is_safe_relative_url(next_url)
            else url_for("store.catalog")
        )

        return redirect(destination)

    return render_template(
        "login.html",
        form=form,
    )


@auth_bp.post("/logout")
@limiter.limit("10 per minute")
def logout():
    if session.get("user"):
        audit_event(
            "LOGOUT",
            success=True,
        )

    session.clear()

    flash(
        "La sesión se cerró correctamente.",
        "success",
    )

    return redirect(
        url_for("store.catalog")
    )