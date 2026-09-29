"""SQLAlchemy engine, session factory and the get_db dependency.

The database comes from app.config.DATABASE_URL:
  - SQLite file (default, original server setup under DATA_DIR)
  - Postgres (e.g. Supabase) when DATABASE_URL is set, as on Vercel
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import DATABASE_URL as _CONFIGURED_URL


def _normalize_url(url: str) -> str:
    """Use the psycopg (v3) driver for Postgres URLs such as the ones
    Supabase and Vercel hand out (postgres:// or postgresql://)."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(_CONFIGURED_URL)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    # Serverless-friendly: no pooled connections kept between requests
    # (Supabase's pooler does the pooling), and no server-side prepared
    # statements, which the transaction pooler does not support.
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

Base = declarative_base()


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
