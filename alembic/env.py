import os
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ── Load .env from project root before anything reads environment vars ────────
# Walk up from this file's directory until we find a .env file
_here = Path(__file__).resolve().parent
for _candidate in [_here, _here.parent, _here.parent.parent]:
    _env_file = _candidate / ".env"
    if _env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=str(_env_file), override=False)
            print(f"[alembic/env.py] Loaded .env from {_env_file}")
        except ImportError:
            # Fallback: parse manually if python-dotenv not installed
            with open(_env_file) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _, _v = _line.partition("=")
                        os.environ.setdefault(_k.strip(), _v.strip())
            print(f"[alembic/env.py] Loaded .env (manual) from {_env_file}")
        break
# ─────────────────────────────────────────────────────────────────────────────

# Import your models' Base for autogenerate support
from venserver.datamodel.models import Base
from venserver.datamodel.database import build_db_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# Override sqlalchemy.url from alembic.ini with environment variables
config.set_main_option('sqlalchemy.url', build_db_url())


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
