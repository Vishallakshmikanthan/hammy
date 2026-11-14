"""
HAMMY — Database Connection & Session Management (`infrastructure/database/connection.py`).
Provides:
  - Database engine and session factory with environment variable configuration (`DATABASE_URL`).
  - Automatic dialect handling (PostgreSQL for production/Supabase, SQLite for offline tests).
  - Declarative Base and schema initialization helpers.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base for all SQLAlchemy models
Base = declarative_base()

DEFAULT_DB_FILE = Path(__file__).resolve().parent.parent.parent / "hammy.db"
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_DB_FILE}"


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        return DEFAULT_SQLITE_URL
    # Normalize postgres:// to postgresql:// for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def create_db_engine(database_url: str | None = None, echo: bool = False):
    url = database_url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args, echo=echo)

    # For SQLite: enable foreign keys and setup immutability triggers
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session(db_engine=None) -> Generator[Session, None, None]:
    """Context manager for transactional database sessions."""
    s_maker = sessionmaker(autocommit=False, autoflush=False, bind=db_engine or engine)
    session = s_maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def setup_immutability_triggers(engine_instance):
    """
    Installs database-level triggers enforcing that world_events is append-only
    and cannot be updated (Acceptance Criterion 3).
    """
    from sqlalchemy import inspect

    dialect = engine_instance.dialect.name
    with engine_instance.begin() as conn:
        inspector = inspect(conn)
        if "world_events" not in inspector.get_table_names():
            return

        if dialect == "sqlite":
            conn.exec_driver_sql("""
                CREATE TRIGGER IF NOT EXISTS prevent_world_events_update
                BEFORE UPDATE ON world_events
                BEGIN
                    SELECT RAISE(ABORT, 'world_events is append-only and cannot be updated');
                END;
            """)
        elif dialect in ("postgresql", "postgres"):
            conn.exec_driver_sql("""
                CREATE OR REPLACE FUNCTION prevent_world_events_update_func()
                RETURNS TRIGGER AS $$
                BEGIN
                    RAISE EXCEPTION 'world_events is append-only and cannot be updated';
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_prevent_world_events_update ON world_events;
                CREATE TRIGGER trg_prevent_world_events_update
                BEFORE UPDATE ON world_events
                FOR EACH ROW
                EXECUTE FUNCTION prevent_world_events_update_func();
            """)


def init_db(engine_instance=None):
    """Initializes tables and immutability triggers."""
    target_engine = engine_instance or engine
    Base.metadata.create_all(bind=target_engine)
    setup_immutability_triggers(target_engine)
