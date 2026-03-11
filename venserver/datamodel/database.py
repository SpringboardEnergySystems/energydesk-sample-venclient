"""
Database connection and session management for VEN Server
"""
import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from venserver.datamodel.models import Base


# ── Load .env from project root (once, at import time) ───────────────────────
def _load_dotenv_if_needed():
    """Load .env file from project root if python-dotenv is available."""
    _here = Path(__file__).resolve().parent
    for _candidate in [_here, _here.parent, _here.parent.parent, _here.parent.parent.parent]:
        _env_file = _candidate / ".env"
        if _env_file.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=str(_env_file), override=False)
            except ImportError:
                # Manual fallback
                with open(_env_file) as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if _line and not _line.startswith("#") and "=" in _line:
                            _k, _, _v = _line.partition("=")
                            os.environ.setdefault(_k.strip(), _v.strip())
            break

_load_dotenv_if_needed()
# ─────────────────────────────────────────────────────────────────────────────


def build_db_url() -> str:
    """
    Build PostgreSQL connection URL from environment variables.
    Supports both POSTGRES_* and DB_* environment variable prefixes.
    """
    dbuser = os.environ.get("POSTGRES_USER") or os.environ.get("DB_USER", "postgres")
    dbpwd  = os.environ.get("POSTGRES_PASSWORD") or os.environ.get("DB_PASSWORD", "postgres")
    dbhost = os.environ.get("POSTGRES_HOST") or os.environ.get("DB_HOST", "localhost")
    dbport = os.environ.get("POSTGRES_PORT") or os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or os.environ.get("DB_NAME", "vendb")

    url = f"postgresql+psycopg2://{dbuser}:{dbpwd}@{dbhost}:{dbport}/{dbname}"
    return url


# ── Lazy engine / session factory ────────────────────────────────────────────
# Build these once, but AFTER .env has been loaded above so the correct
# POSTGRES_PORT (e.g. 5431) is already in os.environ.

def _make_engine():
    return create_engine(
        build_db_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )

engine = _make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI routes to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def drop_all():
    """Drop all tables. Use with caution! Only for development/testing."""
    Base.metadata.drop_all(bind=engine)
