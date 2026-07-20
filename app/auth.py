import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_, select

from .audit import audit_event
from .extensions import db, limiter, oauth
from .forms import LoginForm
from .mailer import send_email
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


# =========================================================
# NIVEL 2 — ALMACENAMIENTO SEGURO
#
# Defensa en profundidad para contraseñas:
#   pepper (secreto global, fuera de la BD)
#     -> HMAC-SHA256(pepper, contraseña)
#       -> Argon2id (salt único por usuario, embebido
#          en el hash resultante)
#
# Si la base de datos se filtra, los hashes no pueden
# atacarse por fuerza bruta sin conocer además el pepper
# del servidor.
# =========================================================

def _pepper_password(password: str) -> str:
    pepper = current_app.config["PASSWORD_PEPPER"]
    return hmac.new(
        pepper.encode("utf-8"),
        password.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_password(password: str) -> str:
    """Hash definitivo: Argon2id sobre la contraseña con pepper."""
    return password_hasher.hash(
        _pepper_password(password)
    )


def _argon2_verify(
    stored_hash: str,
    candidate: str,
) -> bool:
    try:
        return password_hasher.verify(
            stored_hash,
            candidate,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def verify_password(
    stored_hash: str | None,
    password: str,
) -> tuple[bool, bool]:
    """
    Devuelve (es_valida, requiere_rehash).

    Verifica primero con pepper. Si falla, intenta el
    esquema legado sin pepper: si esa verificación pasa,
    la contraseña es correcta pero el hash es antiguo y
    debe regenerarse con pepper (migración transparente).
    """
    if not stored_hash:
        return False, False

    peppered = _pepper_password(password)

    if _argon2_verify(stored_hash, peppered):
        needs = password_hasher.check_needs_rehash(
            stored_hash
        )
        return True, needs

    # Compatibilidad con hashes creados antes del pepper.
    if _argon2_verify(stored_hash, password):
        return True, True

    return False, False


def create_user_session(
    user: User,
    provider: str,
) -> None:
    """
    Elimina la sesión anterior y crea una nueva sesión
    autenticada con la información mínima del usuario.
    """
    session.clear()
    session.permanent = True

    session["user"] = {
        "oid": str(user.id),
        "name": user.name,
        "username": user.email,
        "roles": [user.role],
        "provider": provider,
    }


# =========================================================
# LOGIN LOCAL
# =========================================================

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

        password_is_valid, needs_rehash = verify_password(
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
                    "provider": "local",
                    "reason": "invalid_credentials",
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

        if needs_rehash:
            user.password_hash = hash_password(
                form.password.data
            )
            db.session.commit()

        # -------------------------------------------------
        # NIVEL 4 — MFA: la contraseña por sí sola no
        # concede la sesión. Se inicia el segundo factor.
        # -------------------------------------------------
        audit_event(
            "LOGIN_PASSWORD_OK",
            resource_type="user",
            resource_id=user.id,
            success=True,
            details={
                "provider": "local",
                "mfa": "otp_challenge_started",
            },
        )

        start_otp_challenge(
            user,
            next_url=(
                next_url
                if is_safe_relative_url(next_url)
                else None
            ),
        )

        return redirect(
            url_for("auth.verify_otp")
        )

    return render_template(
        "login.html",
        form=form,
    )


# =========================================================
# REGISTRO DE CUENTA
#
# El alta también pasa por verificación de correo: la
# cuenta no se crea hasta que el usuario demuestra control
# de la dirección introduciendo el código OTP. Esto evita
# registros con correos ajenos o inexistentes.
#
# La respuesta es idéntica exista o no el correo, para no
# permitir enumeración de usuarios registrados.
# =========================================================

@auth_bp.route(
    "/registro",
    methods=["GET", "POST"],
)
@limiter.limit("5 per hour")
def register():
    from .forms import RegisterForm

    if session.get("user"):
        return redirect(url_for("store.catalog"))

    form = RegisterForm()

    if form.validate_on_submit():
        email = normalize_email(form.email.data)

        existing = db.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

        if existing is None:
            user = User(
                email=email,
                name=form.name.data.strip(),
                password_hash=hash_password(
                    form.password.data
                ),
                role="Customer",
                active=True,
            )
            db.session.add(user)
            db.session.commit()

            audit_event(
                "USER_REGISTERED",
                resource_type="user",
                resource_id=user.id,
                success=True,
                details={"provider": "local"},
            )

            start_otp_challenge(user)

            return redirect(
                url_for("auth.verify_otp")
            )

        # El correo ya existe: se avisa por correo al dueño
        # real y se muestra el mismo mensaje genérico.
        audit_event(
            "REGISTER_DUPLICATE_EMAIL",
            success=False,
            details={"provider": "local"},
        )

        send_email(
            email,
            "Intento de registro · SecureAuth Store",
            (
                "Alguien intentó crear una cuenta con este "
                "correo, que ya está registrado.\n\n"
                "Si fuiste tú, inicia sesión normalmente. "
                "Si no reconoces el intento, cambia tu "
                "contraseña.\n\n"
                "SecureAuth Store"
            ),
        )

        flash(
            "Revisa tu correo para continuar con el registro.",
            "success",
        )

        return redirect(url_for("auth.login"))

    return render_template(
        "register.html",
        form=form,
    )


# =========================================================
# NIVEL 4 — MFA POR CÓDIGO OTP
#
# Tras validar la contraseña se genera un código de un
# solo uso. En la sesión solo se guarda su HMAC (nunca el
# código en claro), con expiración corta y límite de
# intentos. En producción el código se enviaría por correo
# o SMS; en desarrollo se registra en la consola del
# servidor para poder demostrar el flujo.
# =========================================================

def _generate_otp_code() -> str:
    length = current_app.config["OTP_LENGTH"]
    return "".join(
        str(secrets.randbelow(10))
        for _ in range(length)
    )


def _otp_digest(code: str) -> str:
    return hmac.new(
        current_app.config["SECRET_KEY"].encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _deliver_otp(user: User, code: str) -> None:
    """
    Entrega el código por correo electrónico.

    Si no hay SMTP configurado (desarrollo), el mailer
    registra el mensaje en el log del servidor para poder
    demostrar el flujo sin credenciales reales.
    """
    minutes = current_app.config["OTP_TTL_SECONDS"] // 60

    send_email(
        user.email,
        "Tu código de verificación · SecureAuth Store",
        (
            f"Hola {user.name}:\n\n"
            f"Tu código de verificación es: {code}\n\n"
            f"Vence en {minutes} minutos y solo puede usarse "
            "una vez.\n\n"
            "Si no intentaste iniciar sesión, cambia tu "
            "contraseña de inmediato.\n\n"
            "SecureAuth Store"
        ),
    )


def _mask_email(address: str) -> str:
    """Oculta el correo en la interfaz: j****z@gmail.com"""
    local, _, domain = address.partition("@")

    if len(local) <= 2:
        hidden = local[0] + "*"
    else:
        hidden = f"{local[0]}{'*' * 4}{local[-1]}"

    return f"{hidden}@{domain}"


def start_otp_challenge(
    user: User,
    next_url: str | None = None,
) -> None:
    code = _generate_otp_code()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            seconds=current_app.config["OTP_TTL_SECONDS"]
        )
    )

    # Se descarta cualquier estado previo de sesión antes
    # de guardar el desafío (anti fijación de sesión).
    session.clear()
    session["pending_mfa"] = {
        "user_id": user.id,
        "otp_digest": _otp_digest(code),
        "expires_at": expires_at.isoformat(),
        "attempts_left": current_app.config[
            "OTP_MAX_ATTEMPTS"
        ],
        "next_url": next_url,
        "masked_email": _mask_email(user.email),
    }

    _deliver_otp(user, code)


def _clear_otp_challenge() -> None:
    session.pop("pending_mfa", None)


@auth_bp.route(
    "/otp",
    methods=["GET", "POST"],
)
@limiter.limit("10 per minute")
def verify_otp():
    from .forms import OtpForm

    pending = session.get("pending_mfa")

    if not pending:
        flash(
            "La verificación expiró. Vuelve a iniciar sesión.",
            "error",
        )
        return redirect(url_for("auth.login"))

    expires_at = datetime.fromisoformat(
        pending["expires_at"]
    )

    if datetime.now(timezone.utc) > expires_at:
        _clear_otp_challenge()

        audit_event(
            "MFA_EXPIRED",
            success=False,
            details={"reason": "otp_expired"},
        )

        flash(
            "El código expiró. Vuelve a iniciar sesión.",
            "error",
        )
        return redirect(url_for("auth.login"))

    form = OtpForm()

    if form.validate_on_submit():
        submitted_digest = _otp_digest(
            form.code.data.strip()
        )

        if hmac.compare_digest(
            submitted_digest,
            pending["otp_digest"],
        ):
            user = db.session.get(
                User,
                pending["user_id"],
            )

            next_url = pending.get("next_url")
            _clear_otp_challenge()

            if user is None or not user.active:
                flash(
                    "No fue posible completar el acceso.",
                    "error",
                )
                return redirect(
                    url_for("auth.login")
                )

            create_user_session(
                user,
                provider="local",
            )

            audit_event(
                "LOGIN_SUCCESS",
                resource_type="user",
                resource_id=user.id,
                success=True,
                details={
                    "provider": "local",
                    "mfa": "otp_verified",
                },
            )

            destination = (
                next_url
                if is_safe_relative_url(next_url)
                else url_for("store.catalog")
            )

            return redirect(destination)

        # Código incorrecto: descontar intento.
        pending["attempts_left"] -= 1

        if pending["attempts_left"] <= 0:
            _clear_otp_challenge()

            audit_event(
                "MFA_LOCKED",
                success=False,
                details={
                    "reason": "otp_attempts_exhausted",
                },
            )

            flash(
                "Demasiados intentos. Vuelve a iniciar sesión.",
                "error",
            )
            return redirect(
                url_for("auth.login")
            )

        session["pending_mfa"] = pending

        audit_event(
            "MFA_FAILED",
            success=False,
            details={"reason": "otp_mismatch"},
        )

        flash(
            "Código incorrecto.",
            "error",
        )

        return render_template(
            "verify_otp.html",
            form=form,
            attempts_left=pending["attempts_left"],
            masked_email=pending.get("masked_email"),
            ttl_minutes=current_app.config["OTP_TTL_SECONDS"] // 60,
        ), 401

    return render_template(
        "verify_otp.html",
        form=form,
        attempts_left=pending["attempts_left"],
        masked_email=pending.get("masked_email"),
        ttl_minutes=current_app.config["OTP_TTL_SECONDS"] // 60,
    )


# =========================================================
# LOGIN CON GOOGLE
# =========================================================

@auth_bp.get("/google")
@limiter.limit("10 per minute")
def google_login():
    if not current_app.config.get("GOOGLE_OAUTH_ENABLED"):
        flash(
            "El acceso con Google no está disponible.",
            "error",
        )
        return redirect(url_for("auth.login"))

    if session.get("user"):
        return redirect(
            url_for("store.catalog")
        )

    redirect_uri = url_for(
    "auth.google_callback",
    _external=True,
)

    current_app.logger.info(
    "Iniciando Google OAuth host=%s redirect_uri=%s",
    request.host,
    redirect_uri,
)

    return oauth.google.authorize_redirect(
    redirect_uri,
    prompt="select_account",
)


@auth_bp.get("/google/callback")
@limiter.limit("20 per minute")
def google_callback():
    if not current_app.config.get("GOOGLE_OAUTH_ENABLED"):
        return redirect(url_for("auth.login"))

    try:
        token = (
            oauth.google
            .authorize_access_token()
        )

        userinfo = token.get(
            "userinfo",
            {},
        )

    except Exception:
        current_app.logger.exception(
            "Error durante el login con Google"
        )

        audit_event(
            "GOOGLE_LOGIN_FAILED",
            success=False,
            details={
                "provider": "google",
            },
        )

        flash(
            "No fue posible validar la cuenta de Google.",
            "error",
        )

        return redirect(
            url_for("auth.login")
        )

    google_sub = str(
        userinfo.get("sub", "")
    ).strip()

    email = normalize_email(
        str(userinfo.get("email", ""))
    )

    name = str(
        userinfo.get("name", email)
    ).strip()[:120]

    email_verified = bool(
        userinfo.get("email_verified")
    )

    if (
        not google_sub
        or not email
        or not email_verified
    ):
        audit_event(
            "GOOGLE_IDENTITY_INVALID",
            success=False,
            details={
                "provider": "google",
            },
        )

        flash(
            "Google no devolvió un correo verificado.",
            "error",
        )

        return redirect(
            url_for("auth.login")
        )

    user = db.session.execute(
        select(User).where(
            or_(
                User.google_sub == google_sub,
                User.email == email,
            )
        )
    ).scalar_one_or_none()

    if user is None:
        bootstrap_admin_email = (
            current_app.config[
                "BOOTSTRAP_ADMIN_EMAIL"
            ]
        )

        initial_role = (
            "Admin"
            if email == bootstrap_admin_email
            else "Customer"
        )

        user = User(
            google_sub=google_sub,
            email=email,
            name=name,
            password_hash=None,
            role=initial_role,
            active=True,
        )

        db.session.add(user)
        db.session.commit()

        audit_event(
            "GOOGLE_USER_REGISTERED",
            resource_type="user",
            resource_id=user.id,
            success=True,
            details={
                "provider": "google",
                "role": user.role,
            },
        )

    else:
        changed = False

        if not user.google_sub:
            user.google_sub = google_sub
            changed = True

        if user.name != name:
            user.name = name
            changed = True

        if changed:
            db.session.commit()

    if not user.active:
        audit_event(
            "BANNED_USER_LOGIN",
            resource_type="user",
            resource_id=user.id,
            success=False,
            details={
                "provider": "google",
            },
        )

        flash(
            "No fue posible iniciar sesión con esta cuenta.",
            "error",
        )

        return redirect(
            url_for("auth.login")
        )

    create_user_session(
        user,
        provider="google",
    )

    audit_event(
        "GOOGLE_LOGIN_SUCCESS",
        resource_type="user",
        resource_id=user.id,
        success=True,
        details={
            "provider": "google",
        },
    )

    return redirect(
        url_for("store.catalog")
    )


# =========================================================
# LOGOUT
# =========================================================

@auth_bp.post("/logout")
@limiter.limit("10 per minute")
def logout():
    user_data = session.get("user")

    if user_data:
        audit_event(
            "LOGOUT",
            resource_type="user",
            resource_id=user_data.get("oid"),
            success=True,
            details={
                "provider": user_data.get(
                    "provider",
                    "unknown",
                ),
            },
        )

    session.clear()

    flash(
        "La sesión se cerró correctamente.",
        "success",
    )

    return redirect(
        url_for("store.catalog")
    )