
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the backend directory is importable.
BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from config import get_settings  # noqa: E402
from database import Base  # noqa: E402
import models  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the application database URL. Escape percent signs because
# Alembic's Config uses ConfigParser interpolation internally.
database_url = get_settings().DATABASE_URL
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# Importing models above registers their tables with Base.metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL migrations without opening a database connection."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
