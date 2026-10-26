from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        in_memory = ":memory:" in database_url or database_url.rstrip("/").endswith("sqlite+pysqlite:")
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if in_memory else None,
        )
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
