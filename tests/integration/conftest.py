"""Fixtures for product-search integration tests.

Postgres is required: the search endpoint relies on tsvector, pg_trgm, and
ARRAY columns that SQLite does not support. testcontainers spins up a
session-scoped Postgres so the production-equivalent extensions and types
are exercised. Schema is applied via Alembic so migration scripts (the
production-ready code path) are tested rather than `Base.metadata.create_all`.

Fixtures defined here are scoped to `tests/integration/` so unit tests do
not pay the container startup cost.
"""
from __future__ import annotations

import os

import pytest

# `api.common.database` reads DATABASE_URL at import time. A placeholder is
# set before any app module is imported so import-time engine construction
# does not fail. The real Postgres URL is wired into `get_db` via
# `app.dependency_overrides`, so the placeholder is never actually connected.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://placeholder@localhost/placeholder"
)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from api.common.database import get_db
from api.common.models import Base, Product
from api.main import app


def _apply_alembic_migrations(database_url: str) -> None:
    # Alembic is imported lazily so this module can still load (and other
    # fixtures resolve) even if alembic itself has not been installed yet,
    # surfacing a clear error only when migrations are actually requested.
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def postgres_url():
    # Session-scoped: container startup + migration is the slowest part of
    # the suite and only needs to run once. Per-test isolation is handled
    # via `_clean_db` (TRUNCATE) below.
    with PostgresContainer("postgres:15-alpine") as container:
        url = container.get_connection_url()
        _apply_alembic_migrations(url)
        yield url


@pytest.fixture(scope="session")
def test_engine(postgres_url):
    engine = create_engine(postgres_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


@pytest.fixture
def _clean_db(test_engine):
    # Per-test cleanup. Iterate in reverse FK-dependency order so children
    # are deleted before parents. Restricting to `Base.metadata.sorted_tables`
    # leaves Alembic's `alembic_version` table untouched, so migrations stay
    # marked as applied across tests.
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db_session(session_factory, _clean_db):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory, _clean_db):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def make_product():
    """Factory for `Product` instances with sensible test defaults.

    Tests pass only the fields they care about; everything else gets a
    deterministic placeholder. `tags` defaults to `[]` (matching the
    column's NOT NULL design) and `in_stock` defaults to `True` (matching
    the model-level default).
    """

    def _make(
        name,
        description=None,
        jan_code=None,
        image_url=None,
        tags=None,
        in_stock=True,
        current_price=None,
    ):
        return Product(
            name=name,
            description=description,
            jan_code=jan_code,
            image_url=image_url,
            tags=tags if tags is not None else [],
            in_stock=in_stock,
            current_price=current_price,
        )

    return _make
