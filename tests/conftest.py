import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "FORCE_HTTPS": False,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {},
            "RATELIMIT_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login_customer(client):
    with client.session_transaction() as sess:
        sess["user"] = {"oid": "customer-1", "name": "Cliente", "username": "cliente@example.com", "roles": ["Customer"]}
    return client


@pytest.fixture()
def login_admin(client):
    with client.session_transaction() as sess:
        sess["user"] = {"oid": "admin-1", "name": "Admin", "username": "admin@example.com", "roles": ["Admin"]}
    return client
