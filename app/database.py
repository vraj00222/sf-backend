import logging
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


# Columns that held a contact's single address before it became its own table.
# Keys are the legacy `contacts` column names, values the Address field each maps to.
LEGACY_ADDRESS_COLUMNS = {
    "address": "street",
    "city": "city",
    "state": "state",
    "postal_code": "postal_code",
    "country": "country",
}


def migrate_legacy_addresses(connection, legacy_columns: dict[str, str]) -> int:
    """Copy pre-Address-table flat address columns into the addresses table.

    Returns the number of contacts migrated. Idempotent: only contacts that do
    not already own an address row are touched, so repeated startups are a
    no-op. The legacy columns are left in place — SQLite cannot drop a column
    without rewriting the table, and they are harmless once every contact owns
    a real Address row.
    """
    if not legacy_columns:
        return 0

    selected = ", ".join(f"c.{name}" for name in legacy_columns)
    rows = (
        connection.execute(
            text(
                f"SELECT c.id, {selected} FROM contacts c "
                "WHERE NOT EXISTS (SELECT 1 FROM addresses a WHERE a.contact_id = c.id)"
            )
        )
        .mappings()
        .all()
    )

    migrated = 0
    for row in rows:
        values = {
            field: (row[name] or "").strip() or None
            for name, field in legacy_columns.items()
        }
        if not any(values.values()):
            continue
        connection.execute(
            text(
                "INSERT INTO addresses (contact_id, type, street, city, state, postal_code, country) "
                "VALUES (:contact_id, 'Home', :street, :city, :state, :postal_code, :country)"
            ),
            {"contact_id": row["id"], **{f: values.get(f) for f in
              ("street", "city", "state", "postal_code", "country")}},
        )
        migrated += 1
    return migrated


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

    # A database written before addresses became their own table still holds the
    # values in the old flat columns. create_all() creates the new table but
    # cannot move data, so without this every pre-existing contact would come
    # back with an empty address list while its real address sat stranded in a
    # column the ORM no longer maps.
    legacy = {name: field for name, field in LEGACY_ADDRESS_COLUMNS.items() if name in existing}
    if legacy:
        with engine.begin() as connection:
            migrated = migrate_legacy_addresses(connection, legacy)
        if migrated:
            logger.info("migrated %d legacy contact address(es) into addresses", migrated)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
