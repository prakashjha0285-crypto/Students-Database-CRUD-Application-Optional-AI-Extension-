import pytest
from fastapi.testclient import TestClient

VALID = {
    "name": "Test Student",
    "date_of_birth": "2004-05-20",
    "email": "test.student@example.com",
    "phone": "+91 90000 11111",
    "course": "Data Science",
    "enrollment_date": "2024-07-01",
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def make(client, **overrides):
    payload = {**VALID, **overrides}
    return client.post("/students", json=payload)


# ----------------------------------------------------------------- CREATE
def test_create_student(client):
    r = make(client)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1
    assert body["name"] == "Test Student"
    assert body["email"] == "test.student@example.com"


def test_create_normalizes_email_and_strips_name(client):
    r = make(client, name="  Padded Name  ", email="UPPER@Example.COM")
    assert r.status_code == 201
    assert r.json()["name"] == "Padded Name"
    assert r.json()["email"] == "upper@example.com"


def test_create_requires_email_or_phone(client):
    r = make(client, email=None, phone=None)
    assert r.status_code == 422


def test_create_phone_only_is_allowed(client):
    r = make(client, email=None)
    assert r.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": ""},
        {"email": "not-an-email"},
        {"phone": "abc"},
        {"date_of_birth": "2999-01-01"},
        {"date_of_birth": "not-a-date"},
        {"enrollment_date": "1999-01-01"},  # before date_of_birth
    ],
)
def test_create_validation_errors(client, overrides):
    assert make(client, **overrides).status_code == 422


def test_create_missing_required_field(client):
    payload = {k: v for k, v in VALID.items() if k != "name"}
    assert client.post("/students", json=payload).status_code == 422


def test_duplicate_email_conflict(client):
    assert make(client).status_code == 201
    assert make(client, name="Someone Else").status_code == 409


# ------------------------------------------------------------------- READ
def test_get_student_and_404(client):
    sid = make(client).json()["id"]
    assert client.get(f"/students/{sid}").json()["name"] == "Test Student"
    r = client.get("/students/999")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"]


def test_get_student_invalid_id_type(client):
    assert client.get("/students/abc").status_code == 422


def test_list_and_filters(client):
    make(client, name="Aarav Sharma", email="a@example.com", course="Data Science", date_of_birth="2004-01-01")
    make(client, name="Diya Patel", email="d@example.com", course="Web Development", date_of_birth="2006-06-06")
    make(client, name="Rohan Das", email="r@example.com", course="Data Science", date_of_birth="2007-07-07")

    r = client.get("/students")
    assert r.status_code == 200
    assert len(r.json()) == 3
    assert r.headers["X-Total-Count"] == "3"

    assert len(client.get("/students", params={"course": "data"}).json()) == 2
    assert [s["name"] for s in client.get("/students", params={"name": "diya"}).json()] == ["Diya Patel"]
    assert len(client.get("/students", params={"born_after": "2005-12-31"}).json()) == 2
    assert len(client.get("/students", params={"born_before": "2005-01-01"}).json()) == 1
    assert client.get("/students", params={"email": "R@example.com"}).json()[0]["name"] == "Rohan Das"

    page = client.get("/students", params={"limit": 2, "offset": 2})
    assert len(page.json()) == 1
    assert page.headers["X-Total-Count"] == "3"


def test_list_rejects_bad_pagination(client):
    assert client.get("/students", params={"limit": 0}).status_code == 422
    assert client.get("/students", params={"limit": 1000}).status_code == 422


def test_like_wildcards_are_escaped(client):
    make(client, name="Plain Name")
    assert client.get("/students", params={"name": "%"}).json() == []


# ----------------------------------------------------------------- UPDATE
def test_put_replaces_student(client):
    sid = make(client).json()["id"]
    new = {**VALID, "name": "Renamed", "course": None, "email": "renamed@example.com"}
    r = client.put(f"/students/{sid}", json=new)
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["course"] is None


def test_put_404(client):
    assert client.put("/students/42", json=VALID).status_code == 404


def test_patch_partial_update(client):
    sid = make(client).json()["id"]
    r = client.patch(f"/students/{sid}", json={"course": "Cloud Computing"})
    assert r.status_code == 200
    body = r.json()
    assert body["course"] == "Cloud Computing"
    assert body["name"] == "Test Student"  # untouched


def test_patch_cannot_remove_all_contact_info(client):
    sid = make(client).json()["id"]
    r = client.patch(f"/students/{sid}", json={"email": None, "phone": None})
    assert r.status_code == 422


def test_patch_cannot_null_name(client):
    sid = make(client).json()["id"]
    assert client.patch(f"/students/{sid}", json={"name": None}).status_code == 422


def test_patch_duplicate_email_and_404(client):
    make(client, email="one@example.com")
    sid2 = make(client, name="Two", email="two@example.com").json()["id"]
    assert client.patch(f"/students/{sid2}", json={"email": "one@example.com"}).status_code == 409
    assert client.patch("/students/999", json={"course": "X"}).status_code == 404


# ----------------------------------------------------------------- DELETE
def test_delete_student(client):
    sid = make(client).json()["id"]
    assert client.delete(f"/students/{sid}").status_code == 204
    assert client.get(f"/students/{sid}").status_code == 404
    assert client.delete(f"/students/{sid}").status_code == 404


# ------------------------------------------------------------ PERSISTENCE
def test_data_persists_across_app_restarts(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "persist.db"))
    from app.main import app

    with TestClient(app) as first:
        sid = first.post("/students", json=VALID).json()["id"]
    with TestClient(app) as second:  # fresh startup, same file
        assert second.get(f"/students/{sid}").json()["name"] == "Test Student"
