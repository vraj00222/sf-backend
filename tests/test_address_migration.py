"""Regression tests for the three findings Qodo raised on the Address PR."""

from sqlalchemy import create_engine, text

from app.database import LEGACY_ADDRESS_COLUMNS, migrate_legacy_addresses

LEGACY_SCHEMA = """
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    address TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT
);
CREATE TABLE addresses (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    street TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT
);
"""


def _legacy_db():
    """An engine holding the pre-Address-table schema with legacy rows."""
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for statement in filter(None, (s.strip() for s in LEGACY_SCHEMA.split(";"))):
            connection.execute(text(statement))
    return engine


def _rows(engine):
    with engine.begin() as connection:
        return connection.execute(
            text("SELECT contact_id, type, street, city, country FROM addresses ORDER BY id")
        ).mappings().all()


def test_legacy_address_is_copied_into_the_addresses_table():
    engine = _legacy_db()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO contacts (id, address, city, state, postal_code, country) "
                "VALUES (1, '1 Market St', 'San Francisco', 'CA', '94105', 'USA')"
            )
        )
        assert migrate_legacy_addresses(connection, LEGACY_ADDRESS_COLUMNS) == 1

    (row,) = _rows(engine)
    assert row["contact_id"] == 1
    assert row["type"] == "Home"
    assert row["street"] == "1 Market St"
    assert row["city"] == "San Francisco"
    assert row["country"] == "USA"


def test_migration_is_idempotent():
    engine = _legacy_db()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO contacts (id, city) VALUES (1, 'Austin')"))
        assert migrate_legacy_addresses(connection, LEGACY_ADDRESS_COLUMNS) == 1
    with engine.begin() as connection:
        assert migrate_legacy_addresses(connection, LEGACY_ADDRESS_COLUMNS) == 0
    assert len(_rows(engine)) == 1


def test_contacts_with_no_legacy_address_are_skipped():
    engine = _legacy_db()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO contacts (id) VALUES (1)"))
        connection.execute(text("INSERT INTO contacts (id, city) VALUES (2, '   ')"))
        assert migrate_legacy_addresses(connection, LEGACY_ADDRESS_COLUMNS) == 0
    assert _rows(engine) == []


def test_no_legacy_columns_is_a_no_op():
    engine = _legacy_db()
    with engine.begin() as connection:
        assert migrate_legacy_addresses(connection, {}) == 0


# --- Whitespace-only address fields (Qodo: "Reject blank address locations") ---

BASE = "/api/v1/contacts"


def test_whitespace_only_address_is_rejected(client, payload):
    response = client.post(
        BASE, json={**payload, "addresses": [{"type": "Home", "city": "   \t "}]}
    )
    assert response.status_code == 422


def test_whitespace_around_address_fields_is_trimmed(client, payload):
    response = client.post(
        BASE,
        json={
            **payload,
            "addresses": [{"type": "Home", "city": "  Austin  ", "state": "   "}],
        },
    )
    assert response.status_code == 201
    (address,) = response.json()["addresses"]
    assert address["city"] == "Austin"
    # A field that was only whitespace is stored as absent, not as "   ".
    assert address["state"] is None


# --- updated_at on address-only edits (Qodo: "Address updates keep stale timestamp") ---


def test_patching_only_addresses_advances_updated_at(client, payload):
    created = client.post(BASE, json=payload).json()
    before = created["updated_at"]

    response = client.patch(
        f"{BASE}/{created['id']}",
        json={"addresses": [{"type": "Work", "city": "Seattle"}]},
    )

    assert response.status_code == 200
    assert response.json()["updated_at"] > before


def test_put_with_unchanged_scalars_still_advances_updated_at(client, payload):
    created = client.post(BASE, json=payload).json()
    before = created["updated_at"]

    # Every scalar field identical; only the address list differs, so nothing
    # would mark the contacts row dirty on its own.
    replacement = {
        key: created[key]
        for key in ("first_name", "last_name", "email", "phone", "company", "job_title", "notes")
        if key in created
    }
    response = client.put(
        f"{BASE}/{created['id']}",
        json={**replacement, "addresses": [{"type": "Other", "city": "Denver"}]},
    )

    assert response.status_code == 200
    assert response.json()["updated_at"] > before
