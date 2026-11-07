"""Configuration des tests.

Les tests d'intégration utilisent une VRAIE base PostgreSQL de test (recréée à chaque
lancement) et exécutent les tâches Celery directement dans le processus.
Sécurité : on refuse de lancer si le nom de la base ne finit pas par "_test",
pour ne jamais effacer la vraie base.
"""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/maintai_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def database():
    url = make_url(os.environ["DATABASE_URL"])
    if not url.database.endswith("_test"):
        pytest.exit(f"Refus : la base de test doit finir par _test (reçu {url.database})")
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    from app.db.migrate import main as migrate
    migrate()
    yield


@pytest.fixture
def client(database):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
