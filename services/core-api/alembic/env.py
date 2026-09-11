"""Alembic environment.

The database URL is resolved from `PostgresSettings` rather than from
`alembic.ini`, so the password arrives via the Docker secret and never appears in
a committed file.

Migrations run against a synchronous driver (`psycopg`) even though the
application uses `asyncpg`. Alembic's async support exists, but a migration is a
one-shot, strictly-ordered, transactional operation with no concurrency to gain
from — and the synchronous path produces far more legible failures when a DDL
statement is rejected.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mansour_common.config import PostgresSettings, load

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Milestone 3 introduces the ORM models and points this at their metadata, which
# is what enables `--autogenerate`. Until then, migrations are written by hand.
target_metadata = None


def _database_url() -> str:
    return load(PostgresSettings).dsn(driver="postgresql+psycopg")


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting.

    This is how a migration is reviewed before it is run against a production
    database that an event depends on.
    """
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # One transaction for the whole upgrade. A migration that fails
            # halfway must leave no partially-migrated schema behind.
            transaction_per_migration=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
