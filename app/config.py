import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # ---------------------------------------------------------
    # Entorno
    # ---------------------------------------------------------
    ENVIRONMENT = os.getenv(
        "APP_ENV",
        "development",
    ).lower()

    DEBUG = (
        ENVIRONMENT == "development"
        and os.getenv("FLASK_DEBUG", "0") == "1"
    )

    # ---------------------------------------------------------
    # Clave secreta de Flask
    # ---------------------------------------------------------
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or (
        "local-development-only-change-me"
        if ENVIRONMENT != "production"
        else None
    )

    # ---------------------------------------------------------
    # Base de datos
    # ---------------------------------------------------------
    _raw_database_url = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'secureauth.db'}",
    )

    # Render y Heroku entregan el esquema antiguo
    # "postgres://", que SQLAlchemy 2 ya no reconoce.
    if _raw_database_url.startswith("postgres://"):
        _raw_database_url = _raw_database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )
    elif _raw_database_url.startswith("postgresql://"):
        _raw_database_url = _raw_database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    SQLALCHEMY_DATABASE_URI = _raw_database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ---------------------------------------------------------
    # Límites de archivos
    # ---------------------------------------------------------
    MAX_CONTENT_LENGTH = int(
        os.getenv(
            "MAX_CONTENT_LENGTH",
            str(3 * 1024 * 1024),
        )
    )

    MAX_IMAGE_BYTES = int(
        os.getenv(
            "MAX_IMAGE_BYTES",
            str(2 * 1024 * 1024),
        )
    )

    # ---------------------------------------------------------
    # Sesión segura
    # ---------------------------------------------------------
    SESSION_MINUTES = int(
        os.getenv("SESSION_MINUTES", "30")
    )

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SECURE = (
        ENVIRONMENT == "production"
    )

    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_NAME = (
        "__Host-secureauth"
        if ENVIRONMENT == "production"
        else "secureauth_session"
    )

    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=SESSION_MINUTES
    )

    SESSION_REFRESH_EACH_REQUEST = True

    # ---------------------------------------------------------
    # Protección CSRF
    # ---------------------------------------------------------
    WTF_CSRF_ENABLED = True

    # Flask-WTF espera segundos.
    WTF_CSRF_TIME_LIMIT = int(
        os.getenv("WTF_CSRF_TIME_LIMIT", "3600")
    )

    WTF_CSRF_SSL_STRICT = (
        ENVIRONMENT == "production"
    )

    # ---------------------------------------------------------
    # HTTPS
    # ---------------------------------------------------------
    FORCE_HTTPS = (
        ENVIRONMENT == "production"
    )

    PREFERRED_URL_SCHEME = (
        "https"
        if FORCE_HTTPS
        else "http"
    )

    # ---------------------------------------------------------
    # Rate limiting
    # ---------------------------------------------------------
    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://",
    )

    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_STRATEGY = "fixed-window"

    # ---------------------------------------------------------
    # Pepper de contraseñas (Nivel 2: almacenamiento)
    #
    # Secreto global del servidor que se combina con la
    # contraseña ANTES del hash Argon2id. A diferencia del
    # salt (único por usuario y almacenado junto al hash),
    # el pepper vive fuera de la base de datos: si la BD se
    # filtra, los hashes no pueden atacarse sin él.
    # ---------------------------------------------------------
    PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER") or (
        "local-development-pepper-change-me"
        if ENVIRONMENT != "production"
        else None
    )

    # ---------------------------------------------------------
    # MFA por código OTP (Nivel 4: lógica del login)
    # ---------------------------------------------------------
    OTP_LENGTH = 6
    OTP_TTL_SECONDS = int(
        os.getenv("OTP_TTL_SECONDS", "300")
    )
    OTP_MAX_ATTEMPTS = int(
        os.getenv("OTP_MAX_ATTEMPTS", "5")
    )

    # ---------------------------------------------------------
    # Correo saliente (canal del segundo factor)
    #
    # Con Gmail se debe usar una "contraseña de aplicación"
    # (requiere verificación en 2 pasos en la cuenta), nunca
    # la contraseña personal.
    # ---------------------------------------------------------
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "").strip()

    # Google muestra la contraseña de aplicación en cuatro
    # grupos de cuatro ("abcd efgh ijkl mnop"). Si se pega
    # tal cual, la autenticación falla con 535. Se eliminan
    # los espacios de forma transparente.
    SMTP_PASSWORD = (
        os.getenv("SMTP_PASSWORD", "")
        .strip()
        .replace(" ", "")
        .replace("\u00a0", "")
    )
    SMTP_USE_SSL = (
        os.getenv("SMTP_USE_SSL", "0") == "1"
    )
    MAIL_FROM = os.getenv(
        "MAIL_FROM",
        "SecureAuth Store <no-reply@secureauth.local>",
    )

    # ---------------------------------------------------------
    # Política de contraseñas (Nivel 4)
    # ---------------------------------------------------------
    PASSWORD_MIN_LENGTH = int(
        os.getenv("PASSWORD_MIN_LENGTH", "12")
    )

    # ---------------------------------------------------------
    # Microsoft Entra ID
    # Se conserva por compatibilidad, aunque ahora uses login local.
    # ---------------------------------------------------------
    ENTRA_TENANT_ID = os.getenv(
        "ENTRA_TENANT_ID",
        "",
    )

    ENTRA_CLIENT_ID = os.getenv(
        "ENTRA_CLIENT_ID",
        "",
    )

    ENTRA_CLIENT_SECRET = os.getenv(
        "ENTRA_CLIENT_SECRET",
        "",
    )

    ENTRA_AUTHORITY = os.getenv(
        "ENTRA_AUTHORITY",
        (
            "https://login.microsoftonline.com/"
            f"{ENTRA_TENANT_ID}"
            if ENTRA_TENANT_ID
            else ""
        ),
    )

    ENTRA_REDIRECT_URI = os.getenv(
        "ENTRA_REDIRECT_URI",
        "http://localhost:5000/auth/callback",
    )

    ENTRA_POST_LOGOUT_URI = os.getenv(
        "ENTRA_POST_LOGOUT_URI",
        "http://localhost:5000/",
    )

    # ---------------------------------------------------------
    # Azure Blob Storage
    # ---------------------------------------------------------
    AZURE_STORAGE_ACCOUNT_URL = os.getenv(
        "AZURE_STORAGE_ACCOUNT_URL",
        "",
    )

    AZURE_STORAGE_CONNECTION_STRING = os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "",
    )

    AZURE_STORAGE_CONTAINER = os.getenv(
        "AZURE_STORAGE_CONTAINER",
        "product-images",
    )

    # ---------------------------------------------------------
    # Auditoría
    # ---------------------------------------------------------
    AUDIT_HMAC_KEY = os.getenv(
        "AUDIT_HMAC_KEY",
        SECRET_KEY or "audit-local-only",
    )
        # ---------------------------------------------------------
    # Google OAuth / OpenID Connect
    # ---------------------------------------------------------
    GOOGLE_CLIENT_ID = os.getenv(
        "GOOGLE_CLIENT_ID",
        "",
    )

    GOOGLE_CLIENT_SECRET = os.getenv(
        "GOOGLE_CLIENT_SECRET",
        "",
    )

    GOOGLE_REDIRECT_URI = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:5000/auth/google/callback",
    )

    BOOTSTRAP_ADMIN_EMAIL = os.getenv(
        "BOOTSTRAP_ADMIN_EMAIL",
        "",
    ).strip().lower()