"""
Pruebas de los niveles 2 y 4:
- Pepper en el almacenamiento de contraseñas
- MFA por código OTP en el flujo de login
"""

import pytest
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app import auth as auth_module
from app.auth import hash_password, verify_password
from app.extensions import db
from app.models import User


PASSWORD = "Correcta#2026!"
FIXED_OTP = "123456"


@pytest.fixture()
def local_user(app):
    user = User(
        email="prueba@example.com",
        name="Usuario Prueba",
        password_hash=hash_password(PASSWORD),
        role="Customer",
        active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def fixed_otp(monkeypatch):
    monkeypatch.setattr(
        auth_module,
        "_generate_otp_code",
        lambda: FIXED_OTP,
    )
    return FIXED_OTP


# ---------------------------------------------------------
# Nivel 2 — pepper
# ---------------------------------------------------------

def test_hash_no_verifica_sin_pepper(app):
    """El hash almacenado no corresponde a la contraseña
    en claro: sin el pepper, Argon2 debe rechazarla."""
    stored = hash_password(PASSWORD)

    with pytest.raises(VerifyMismatchError):
        PasswordHasher().verify(stored, PASSWORD)


def test_verify_password_con_pepper(app):
    stored = hash_password(PASSWORD)

    ok, rehash = verify_password(stored, PASSWORD)
    assert ok is True
    assert rehash is False

    ok, _ = verify_password(stored, "Incorrecta#2026!")
    assert ok is False


def test_hash_legado_migra_a_pepper(app):
    """Un hash creado sin pepper sigue siendo válido y
    queda marcado para regenerarse."""
    legacy = PasswordHasher().hash(PASSWORD)

    ok, rehash = verify_password(legacy, PASSWORD)
    assert ok is True
    assert rehash is True


# ---------------------------------------------------------
# Nivel 4 — MFA por OTP
# ---------------------------------------------------------

def test_password_correcta_no_da_sesion_directa(
    client, local_user, fixed_otp
):
    response = client.post(
        "/auth/login",
        data={"email": local_user.email, "password": PASSWORD},
    )

    assert response.status_code == 302
    assert "/auth/otp" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert "user" not in sess
        assert "pending_mfa" in sess


def test_otp_correcto_concede_sesion(
    client, local_user, fixed_otp
):
    client.post(
        "/auth/login",
        data={"email": local_user.email, "password": PASSWORD},
    )

    response = client.post(
        "/auth/otp",
        data={"code": FIXED_OTP},
    )

    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert "user" in sess
        assert "pending_mfa" not in sess
        assert sess["user"]["username"] == local_user.email


def test_otp_incorrecto_es_rechazado(
    client, local_user, fixed_otp
):
    client.post(
        "/auth/login",
        data={"email": local_user.email, "password": PASSWORD},
    )

    response = client.post(
        "/auth/otp",
        data={"code": "000000"},
    )

    assert response.status_code == 401

    with client.session_transaction() as sess:
        assert "user" not in sess


def test_otp_se_bloquea_tras_agotar_intentos(
    client, local_user, fixed_otp, app
):
    client.post(
        "/auth/login",
        data={"email": local_user.email, "password": PASSWORD},
    )

    for _ in range(app.config["OTP_MAX_ATTEMPTS"]):
        response = client.post(
            "/auth/otp",
            data={"code": "000000"},
        )

    # Agotado: el desafío desaparece y redirige al login.
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    with client.session_transaction() as sess:
        assert "pending_mfa" not in sess
        assert "user" not in sess

    # El código correcto ya no sirve.
    response = client.post(
        "/auth/otp",
        data={"code": FIXED_OTP},
    )
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_acceso_directo_a_otp_sin_login_redirige(client):
    response = client.get("/auth/otp")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


# ---------------------------------------------------------
# Registro con verificación de correo
# ---------------------------------------------------------

NEW_ACCOUNT = {
    "name": "Nueva Usuaria",
    "email": "nueva@example.com",
    "password": "Nueva#Segura2026",
    "confirm": "Nueva#Segura2026",
}


def test_registro_exige_password_fuerte(client, app):
    debil = dict(NEW_ACCOUNT, password="corta1", confirm="corta1")

    response = client.post("/auth/registro", data=debil)

    assert response.status_code == 200
    with app.app_context():
        assert (
            db.session.query(User)
            .filter_by(email=NEW_ACCOUNT["email"])
            .first()
            is None
        )


def test_registro_exige_confirmacion_coincidente(client, app):
    distinta = dict(NEW_ACCOUNT, confirm="Otra#Distinta2026")

    response = client.post("/auth/registro", data=distinta)

    assert response.status_code == 200
    with app.app_context():
        assert (
            db.session.query(User)
            .filter_by(email=NEW_ACCOUNT["email"])
            .first()
            is None
        )


def test_registro_valido_pide_verificacion(
    client, app, fixed_otp
):
    response = client.post(
        "/auth/registro",
        data=NEW_ACCOUNT,
    )

    assert response.status_code == 302
    assert "/auth/otp" in response.headers["Location"]

    # La cuenta existe pero aún no hay sesión iniciada.
    with client.session_transaction() as sess:
        assert "user" not in sess
        assert "pending_mfa" in sess

    with app.app_context():
        user = (
            db.session.query(User)
            .filter_by(email=NEW_ACCOUNT["email"])
            .first()
        )
        assert user is not None
        # La contraseña quedó hasheada, nunca en claro.
        assert NEW_ACCOUNT["password"] not in user.password_hash


def test_registro_duplicado_no_revela_existencia(
    client, app, local_user
):
    """Registrarse con un correo ya usado devuelve la misma
    respuesta genérica: no permite enumerar cuentas."""
    response = client.post(
        "/auth/registro",
        data={
            "name": "Impostor",
            "email": local_user.email,
            "password": "Otra#Password2026",
            "confirm": "Otra#Password2026",
        },
    )

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    # La contraseña original del usuario no cambió.
    with app.app_context():
        user = db.session.get(User, local_user.id)
        ok, _ = verify_password(user.password_hash, PASSWORD)
        assert ok is True
