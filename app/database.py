"""SQLAlchemy engine, session factory and the get_db dependency."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# ======================================================
# SQLITE DATABASE
# ======================================================

DATABASE_URL = "sqlite:////app/data/registration_system.db"
# DATABASE_URL = "sqlite:///./registration_system.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
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
