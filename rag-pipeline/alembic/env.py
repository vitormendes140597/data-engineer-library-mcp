from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_engine_from_config

from alembic import context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config as app_config  # noqa: E402
from src.persistence.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve the configured database URL for migrations."""
    database_url = (
        app_config.DATABASE_URL
        or app_config.RAGConfig.from_env().database.connection_string
    )
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be set before running Alembic migrations."
        )
    return database_url


def configure_database_url() -> str:
    """Propagate the application database URL into Alembic config."""
    database_url = get_database_url()
    config.set_main_option("sqlalchemy.url", database_url)
    return database_url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=configure_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations using an existing SQLAlchemy connection."""
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with an async SQLAlchemy engine."""
    configure_database_url()
    connectable: AsyncEngine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_sync_migrations() -> None:
    """Run migrations with a sync SQLAlchemy engine."""
    configure_database_url()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
        return

    url = make_url(get_database_url())
    use_async = config.attributes.get("use_async")
    if use_async is None:
        use_async = url.drivername.endswith("+asyncpg") or url.drivername.endswith(
            "+aiosqlite"
        )
        use_async = (
            use_async or os.getenv("ALEMBIC_USE_ASYNC", "false").lower() == "true"
        )

    if use_async:
        asyncio.run(run_async_migrations())
    else:
        run_sync_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
