from __future__ import annotations

import contextlib

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        in_memory = ":memory:" in database_url or database_url.rstrip("/").endswith("sqlite+pysqlite:")
        connect_args = {"check_same_thread": False}
        if not in_memory:
            connect_args["timeout"] = 30
        engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=StaticPool if in_memory else None,
        )
        event.listen(engine, "connect", _configure_sqlite)
        return engine
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _configure_sqlite(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    with contextlib.suppress(Exception):
        cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
