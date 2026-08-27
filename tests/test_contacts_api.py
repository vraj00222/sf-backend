BASE = "/api/v1/contacts"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "sqlite"


def test_create_contact(client, payload):
    response = client.post(BASE, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["email"] == "ada@example.com"
    assert body["full_name"] == "Ada Lovelace"
    assert body["created_at"] and body["updated_at"]


def test_create_requires_valid_email(client, payload):
    response = client.post(BASE, json={**payload, "email": "not-an-email"})
    assert response.status_code == 422


def test_create_requires_names(client, payload):
    response = client.post(BASE, json={**payload, "first_name": ""})
    assert response.status_code == 422


def test_duplicate_email_conflicts(client, payload):
    assert client.post(BASE, json=payload).status_code == 201
    response = client.post(BASE, json={**payload, "email": "ADA@example.com"})
    assert response.status_code == 409


def test_get_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.get(f"{BASE}/{contact_id}")
    assert response.status_code == 200
    assert response.json()["id"] == contact_id


def test_get_missing_contact_returns_404(client):
    assert client.get(f"{BASE}/9999").status_code == 404


def test_list_pagination_and_total(client, payload):
    for index in range(5):
        client.post(BASE, json={**payload, "email": f"user{index}@example.com"})

    response = client.get(BASE, params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 2


def test_list_search(client, payload):
    client.post(BASE, json=payload)
    client.post(
        BASE,
        json={**payload, "first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com", "company": "US Navy"},
    )

    hits = client.get(BASE, params={"search": "hopper"}).json()
    assert hits["total"] == 1
    assert hits["items"][0]["last_name"] == "Hopper"

    by_company = client.get(BASE, params={"search": "navy"}).json()
    assert by_company["total"] == 1

    misses = client.get(BASE, params={"search": "nobody"}).json()
    assert misses["total"] == 0


def test_list_sorting(client, payload):
    client.post(BASE, json={**payload, "last_name": "Zhang", "email": "z@example.com"})
    client.post(BASE, json={**payload, "last_name": "Adams", "email": "a@example.com"})

    names = [
        item["last_name"]
        for item in client.get(BASE, params={"sort_by": "last_name", "order": "asc"}).json()["items"]
    ]
    assert names == ["Adams", "Zhang"]


def test_list_rejects_bad_sort_field(client):
    assert client.get(BASE, params={"sort_by": "; DROP TABLE contacts"}).status_code == 422


def test_patch_updates_only_sent_fields(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+1-000-000-0000"
    assert body["first_name"] == "Ada"
    assert body["company"] == "Analytical Engines"


def test_patch_duplicate_email_conflicts(client, payload):
    first = client.post(BASE, json=payload).json()["id"]
    client.post(BASE, json={**payload, "email": "grace@example.com"})
    response = client.patch(f"{BASE}/{first}", json={"email": "grace@example.com"})
    assert response.status_code == 409


def test_patch_same_email_is_allowed(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"email": payload["email"]})
    assert response.status_code == 200


def test_put_replaces_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["company"] is None  # omitted fields are cleared by PUT


def test_put_missing_contact_returns_404(client):
    response = client.put(
        f"{BASE}/9999",
        json={"first_name": "A", "last_name": "B", "email": "ab@example.com"},
    )
    assert response.status_code == 404


def test_delete_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    assert client.get(f"{BASE}/{contact_id}").status_code == 404
    assert client.delete(f"{BASE}/{contact_id}").status_code == 404


def test_root_lists_entrypoints(client):
    body = client.get("/").json()
    assert body["contacts"] == BASE


# --- Photo -----------------------------------------------------------------

# 1x1 transparent PNG.
PHOTO = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_create_contact_with_photo(client, payload):
    response = client.post(BASE, json={**payload, "photo": PHOTO})
    assert response.status_code == 201
    assert response.json()["photo"] == PHOTO


def test_photo_defaults_to_none(client, payload):
    assert client.post(BASE, json=payload).json()["photo"] is None


def test_photo_rejects_non_data_url(client, payload):
    response = client.post(BASE, json={**payload, "photo": "https://example.com/me.png"})
    assert response.status_code == 422


def test_photo_rejects_non_image_data_url(client, payload):
    response = client.post(BASE, json={**payload, "photo": "data:text/html;base64,PGI+aGk8L2I+"})
    assert response.status_code == 422


def test_photo_rejects_invalid_base64(client, payload):
    response = client.post(BASE, json={**payload, "photo": "data:image/png;base64,@@not-base64@@"})
    assert response.status_code == 422


def test_photo_rejects_trailing_newline(client, payload):
    """`$` would accept a trailing newline and store it; the data URL must be exact."""
    response = client.post(BASE, json={**payload, "photo": "data:image/png;base64,aGVsbG8=\n"})
    assert response.status_code == 422


def test_photo_rejects_oversized_payload_without_decoding_it(client, payload):
    """A too-long data URL is refused on length, before it is decoded into memory."""
    from app.schemas import _MAX_PHOTO_CHARS

    huge = "data:image/png;base64," + "A" * _MAX_PHOTO_CHARS
    response = client.post(BASE, json={**payload, "photo": huge})
    assert response.status_code == 422


def test_oversized_request_body_is_refused_before_parsing(client, payload):
    from app.main import MAX_REQUEST_BYTES

    response = client.post(
        BASE,
        content=b"{}" + b" " * (MAX_REQUEST_BYTES + 1),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_init_db_adds_photo_to_an_older_database(tmp_path):
    """A database created before `photo` existed must gain the column, not break."""
    import sqlalchemy

    from app import database

    db_file = tmp_path / "legacy.db"
    legacy = sqlalchemy.create_engine(f"sqlite+pysqlite:///{db_file}")
    with legacy.begin() as connection:
        connection.execute(
            sqlalchemy.text(
                "CREATE TABLE contacts ("
                "id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,"
                "email TEXT NOT NULL UNIQUE, phone TEXT, company TEXT, job_title TEXT,"
                "address TEXT, city TEXT, state TEXT, postal_code TEXT, country TEXT, notes TEXT,"
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )
    legacy.dispose()

    upgraded = sqlalchemy.create_engine(f"sqlite+pysqlite:///{db_file}")
    original_engine = database.engine
    database.engine = upgraded
    try:
        database.init_db()
        columns = {c["name"] for c in sqlalchemy.inspect(upgraded).get_columns("contacts")}
        assert "photo" in columns
        database.init_db()  # idempotent: a second startup must not fail
    finally:
        database.engine = original_engine
        upgraded.dispose()


def test_photo_rejects_oversized_image(client, payload):
    import base64

    from app.schemas import MAX_PHOTO_BYTES

    too_big = base64.b64encode(b"\0" * (MAX_PHOTO_BYTES + 1)).decode()
    response = client.post(BASE, json={**payload, "photo": f"data:image/png;base64,{too_big}"})
    assert response.status_code == 422


def test_patch_updates_photo_only(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"photo": PHOTO})
    assert response.status_code == 200
    body = response.json()
    assert body["photo"] == PHOTO
    assert body["first_name"] == "Ada"


def test_put_without_photo_clears_it(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["photo"] is None  # PUT is a full replace


def test_put_carrying_photo_preserves_it(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]
    response = client.put(f"{BASE}/{contact_id}", json={**payload, "photo": PHOTO})
    assert response.status_code == 200
    assert response.json()["photo"] == PHOTO


# --- Addresses -------------------------------------------------------------


def test_create_contact_with_multiple_addresses(client, payload):
    addresses = [
        {"type": "Home", "city": "San Francisco", "state": "CA"},
        {"type": "Work", "street": "1 Market St", "city": "San Francisco"},
        {"type": "Other", "city": "Tahoe"},
    ]
    response = client.post(BASE, json={**payload, "addresses": addresses})
    assert response.status_code == 201
    body = response.json()
    assert [a["type"] for a in body["addresses"]] == ["Home", "Work", "Other"]
    assert all(a["id"] > 0 for a in body["addresses"])


def test_addresses_default_to_empty_list(client, payload):
    response = client.post(BASE, json={k: v for k, v in payload.items() if k != "addresses"})
    assert response.status_code == 201
    assert response.json()["addresses"] == []


def test_address_rejects_unknown_type(client, payload):
    response = client.post(
        BASE, json={**payload, "addresses": [{"type": "Vacation", "city": "Tahoe"}]}
    )
    assert response.status_code == 422


def test_address_rejects_all_blank_fields(client, payload):
    response = client.post(BASE, json={**payload, "addresses": [{"type": "Home"}]})
    assert response.status_code == 422


def test_address_rejects_whitespace_only_fields(client, payload):
    response = client.post(
        BASE, json={**payload, "addresses": [{"type": "Home", "city": "   "}]}
    )
    assert response.status_code == 422


def test_put_replaces_address_list(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={**payload, "addresses": [{"type": "Work", "city": "Oakland"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["addresses"]) == 1
    assert body["addresses"][0]["city"] == "Oakland"


def test_put_without_addresses_clears_them(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["addresses"] == []  # PUT is a full replace


def test_patch_without_addresses_keeps_them(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    assert len(response.json()["addresses"]) == 1


def test_patch_addresses_replaces_the_list(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(
        f"{BASE}/{contact_id}",
        json={"addresses": [{"type": "Other", "city": "Tahoe"}, {"type": "Home", "city": "SF"}]},
    )
    assert response.status_code == 200
    assert [a["type"] for a in response.json()["addresses"]] == ["Other", "Home"]


def test_patch_null_addresses_clears_them(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"addresses": None})
    assert response.status_code == 200
    assert response.json()["addresses"] == []


def test_deleting_contact_deletes_its_addresses(client, payload):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import Address

    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204

    with SessionLocal() as db:
        orphans = db.execute(select(func.count()).select_from(Address)).scalar_one()
    assert orphans == 0  # no orphaned address rows
