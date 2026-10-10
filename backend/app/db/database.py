"""
Database setup.

One SQLAlchemy engine + sessionmaker, built from a database URL (see
app/core/config.py's `database_url` setting). SQLite by default - a
single file, zero setup, exactly the "simple local-dev option" the
project's database requirement asks for. Point DATABASE_URL at Postgres
(e.g. "postgresql://...") for a production-style setup; nothing else in
this file needs to change.

No migration framework (Alembic etc.) - `Base.metadata.create_all()`
creates any missing tables on startup, which is enough for a learning
project with two small tables. A real production service would want
migrations; this is a deliberate, named simplification (see
BUILD_VERIFICATION.md).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


def create_session_factory(database_url: str):
    """
    Build a sessionmaker bound to `database_url`, creating tables if they
    don't exist yet. Call once at startup (or once per test) and reuse
    the returned factory - each call to it opens a new Session.
    """
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine_kwargs = {"connect_args": connect_args}

    # An in-memory SQLite DB is per-connection by default, which would
    # give every new Session its own empty database. StaticPool keeps
    # them all on the one connection, which is what tests need.
    if is_sqlite and ":memory:" in database_url:
        engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
