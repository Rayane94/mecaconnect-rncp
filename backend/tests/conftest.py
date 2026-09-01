import os

os.environ["DATABASE_URL"] = "sqlite:///./test_mecaconnect.db"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes-long"

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.seed import run as seed


@pytest.fixture(scope="session", autouse=True)
def db_setup():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()

    yield

    Base.metadata.drop_all(bind=engine)

    # Libère les connexions SQLite avant suppression sous Windows.
    engine.dispose()

    Path("test_mecaconnect.db").unlink(missing_ok=True)


@pytest.fixture()
def client():
    return TestClient(app)


def login(
    client,
    email="admin@mecaconnect.example.com",
    password="Admin-ChangeMe-2026!",
):
    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200
    return response