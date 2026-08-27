import logging
import threading
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

logger = logging.getLogger("contacts")


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _engine_kwargs(database_url: str) -> dict:
    if not database_url.startswith("sqlite"):
        return {}

    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in database_url or "mode=memory" in database_url:
        # A plain in-memory SQLite database lives and dies with its connection.
        # StaticPool keeps a single connection alive so every request — and every
        # thread FastAPI hands work to — sees the same data for the process's lifetime.
        kwargs["poolclass"] = StaticPool
    return kwargs


settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.sql_echo,
    **_engine_kwargs(settings.database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """Create tables, then add any column an older database predates.

    Called on startup; safe to call repeatedly. `create_all` only creates what is
    missing entirely — it never alters an existing table — so a file or Postgres
    database created before `photo` existed would keep a `contacts` table without
    it and fail on the first query. Adding the column is idempotent: it only runs
    when the table is already there and the column is not.
    """
    from app import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if not inspector.has_table("contacts"):
        return
    existing = {column["name"] for column in inspector.get_columns("contacts")}
    for column in Base.metadata.tables["contacts"].columns:
        if column.name in existing:
            continue
        # ponytail: ADD COLUMN only. Dropping or retyping a column needs a real
        # migration tool — add Alembic if this app ever ships stateful upgrades.
        ddl = f"ALTER TABLE contacts ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
        with engine.begin() as connection:
            connection.execute(text(ddl))
        logger.info("added missing column contacts.%s", column.name)


_db_lock = threading.Lock()
"""
StaticPool shares one raw sqlite3 connection across every thread FastAPI's
threadpool hands a request to; the sqlite3 module isn't safe against two
threads actually executing on that same connection at once, and Next.js
routinely fires two requests for a page in parallel (generateMetadata plus
the page itself), which was enough to trip a real "bad parameter or other
API misuse" error. A global lock serializes DB access — fine at this app's
traffic; drop the lock for a per-request connection if that ever changes.
"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session that is always closed."""
    with _db_lock:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
