"""Alembic environment.

URL resolution priority:
1. Value supplied via `Config.set_main_option('sqlalchemy.url', ...)`
   (used by the test fixture, which points at a testcontainers Postgres).
2. `DATABASE_URL` env var (used by CI / local dev pointing at Neon).

We deliberately do not fall back to a placeholder default: if neither source
is set, the migration must fail loudly so a misconfigured deploy never
silently runs against the wrong database.

The Vercel Functions runtime never invokes Alembic; migrations are applied
out-of-band against Neon (CI job or developer machine), per ADR-008 / 009.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the `api` package importable regardless of CWD when alembic is invoked.
# The repo root contains both this `alembic/` directory and the `api/` package.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from api.common.models import Base  # noqa: E402  (import after sys.path tweak)

config = context.config

# Provide metadata so future autogenerate runs have a target. The current
# migrations are hand-written, but exposing target_metadata keeps autogenerate
# usable without further wiring.
target_metadata = Base.metadata


def _resolve_database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    raise RuntimeError(
        "DATABASE_URL is not configured for alembic. Set it via the env var "
        "or via Config.set_main_option('sqlalchemy.url', ...)."
    )


def run_migrations_offline() -> None:
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_database_url()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
