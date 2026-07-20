import logging
import re
import uuid
from datetime import datetime, timezone

from flask import Flask, g, render_template, request, session
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import (
    csrf,
    db,
    limiter,
    migrate,
    oauth,
    talisman,
)

def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if app.config["ENVIRONMENT"] == "production" and not app.config.get("SECRET_KEY"):
        raise RuntimeError("FLASK_SECRET_KEY es obligatorio en producción")

    if app.config["ENVIRONMENT"] == "production" and not app.config.get("PASSWORD_PEPPER"):
        raise RuntimeError("PASSWORD_PEPPER es obligatorio en producción")

    # El segundo factor viaja por correo: sin SMTP el MFA
    # no puede entregarse y la aplicación quedaría con un
    # solo factor efectivo.
    if app.config["ENVIRONMENT"] == "production" and not all(
        (
            app.config.get("SMTP_HOST"),
            app.config.get("SMTP_USER"),
            app.config.get("SMTP_PASSWORD"),
        )
    ):
        raise RuntimeError(
            "La configuración SMTP es obligatoria en producción: "
            "sin ella no puede entregarse el segundo factor."
        )

    # App Service termina TLS delante de Gunicorn y envía X-Forwarded-*.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    oauth.init_app(app)

    # Google OAuth es opcional: el login local con
    # contraseña + OTP funciona sin credenciales externas.
    # Un placeholder de .env.example no cuenta como
    # configuración real.
    _gid = app.config.get("GOOGLE_CLIENT_ID") or ""
    _gsecret = app.config.get("GOOGLE_CLIENT_SECRET") or ""

    app.config["GOOGLE_OAUTH_ENABLED"] = bool(
        _gid
        and _gsecret
        and not _gid.startswith("000000000000-")
        and _gsecret != "NO_SUBIR_A_GIT"
    )

    if app.config["GOOGLE_OAUTH_ENABLED"]:
        oauth.register(
            name="google",
            client_id=_gid,
            client_secret=_gsecret,
            server_metadata_url=(
                "https://accounts.google.com/"
                ".well-known/openid-configuration"
            ),
            client_kwargs={
                "scope": "openid email profile",
            },
        )
    else:
        app.logger.info(
            "Google OAuth deshabilitado: no hay "
            "credenciales configuradas. El login local "
            "con MFA sigue disponible."
        )

    csp = {
        "default-src": ["'self'"],
        "base-uri": ["'self'"],
        "object-src": ["'none'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "img-src": ["'self'", "data:"],
        "style-src": ["'self'"],
        "script-src": ["'self'"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
    }
    talisman.init_app(
        app,
        content_security_policy=csp,
        force_https=app.config["FORCE_HTTPS"],
        strict_transport_security=app.config["FORCE_HTTPS"],
        strict_transport_security_max_age=31536000,
        strict_transport_security_include_subdomains=True,
        strict_transport_security_preload=True,
        referrer_policy="strict-origin-when-cross-origin",
        frame_options="DENY",
    )

    from .admin import admin_bp
    from .auth import auth_bp
    from .store import store_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(admin_bp)

    @app.before_request
    def create_request_context() -> None:
        supplied = request.headers.get("X-Request-ID", "")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied):
            g.request_id = supplied
        else:
            g.request_id = uuid.uuid4().hex
        g.request_started_at = datetime.now(timezone.utc)

    @app.after_request
    def apply_security_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "unknown")
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.endpoint and request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        response.headers.add("Vary", "Cookie")
        return response

    @app.context_processor
    def inject_session_user():
        user = session.get("user")

        def cart_count() -> int:
            """
            Unidades en el carrito del usuario en sesión.

            Se consulta siempre filtrando por el identificador
            de la sesión, nunca por un valor del cliente.
            """
            if not user:
                return 0

            from sqlalchemy import func, select

            from .extensions import db
            from .models import CartItem

            total = db.session.execute(
                select(
                    func.coalesce(
                        func.sum(CartItem.quantity),
                        0,
                    )
                ).where(
                    CartItem.user_oid == str(user["oid"])
                )
            ).scalar_one()

            return int(total or 0)

        return {
            "current_user": user,
            "cart_count": cart_count,
        }

    @app.errorhandler(CSRFError)
    def handle_csrf(error):
        return render_template(
            "error.html",
            code=400,
            title="Solicitud inválida",
            message="El token CSRF no es válido o expiró. Actualiza la página e inténtalo nuevamente.",
        ), 400

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(429)
    @app.errorhandler(500)
    def handle_http_error(error):
        code = getattr(error, "code", 500)
        titles = {
            400: "Solicitud inválida",
            403: "Acceso denegado",
            404: "Página no encontrada",
            429: "Demasiadas solicitudes",
            500: "Error interno",
        }
        messages = {
            400: "Revisa los datos enviados.",
            403: "No tienes permisos para realizar esta acción.",
            404: "El recurso solicitado no existe.",
            429: "Espera un momento antes de volver a intentarlo.",
            500: "Ocurrió un error inesperado. Usa el identificador de solicitud para soporte.",
        }
        if code == 500:
            db.session.rollback()
            app.logger.exception("Error no controlado request_id=%s", getattr(g, "request_id", "unknown"))
        return render_template(
            "error.html",
            code=code,
            title=titles.get(code, "Error"),
            message=messages.get(code, "No se pudo completar la operación."),
        ), code

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return app
