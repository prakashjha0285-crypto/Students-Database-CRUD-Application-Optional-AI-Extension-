"""AI tests use a fake model, so Ollama does NOT need to be running."""
import pytest
from fastapi.testclient import TestClient

from app import ai

STUDENTS = [
    ("Aarav Sharma", "2004-03-15", "Python Backend Development"),
    ("Diya Patel", "2005-11-02", "Python Backend Development"),
    ("Ananya Iyer", "2006-01-09", "Web Development"),
    ("Meera Nair", "2007-08-12", "Web Development"),
]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDENTS_DB_PATH", str(tmp_path / "ai.db"))
    from app.main import app

    with TestClient(app) as c:
        for i, (name, dob, course) in enumerate(STUDENTS):
            r = c.post(
                "/students",
                json={"name": name, "date_of_birth": dob, "course": course, "email": f"s{i}@example.com"},
            )
            assert r.status_code == 201
        yield c


@pytest.fixture()
def fake_model(monkeypatch):
    captured = {}

    def fake(messages):
        captured["messages"] = messages
        return "FAKE ANSWER"

    monkeypatch.setattr(ai, "chat_with_ollama", fake)
    return captured


def test_count_question_grounded_in_context(client, fake_model):
    r = client.post("/ai/ask", json={"question": "How many students are there?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "FAKE ANSWER"
    assert body["total_students_in_database"] == 4
    assert body["total_matching"] == 4
    assert '"total_students_in_database": 4' in fake_model["messages"][1]["content"]


def test_born_after_year_filter(client, fake_model):
    body = client.post("/ai/ask", json={"question": "List students born after 2005"}).json()
    assert body["filters_applied"]["born_after"] == "2005-12-31"
    assert {s["name"] for s in body["records_used"]} == {"Ananya Iyer", "Meera Nair"}


def test_born_in_year_filter(client, fake_model):
    body = client.post("/ai/ask", json={"question": "Who was born in 2004?"}).json()
    assert [s["name"] for s in body["records_used"]] == ["Aarav Sharma"]


def test_course_filter(client, fake_model):
    body = client.post("/ai/ask", json={"question": "How many students take Web Development?"}).json()
    assert body["total_matching"] == 2


def test_contact_details_hidden_unless_asked(client, fake_model):
    body = client.post("/ai/ask", json={"question": "List all students"}).json()
    assert "email" not in body["records_used"][0]
    body = client.post("/ai/ask", json={"question": "What is Diya's email?"}).json()
    assert "email" in body["records_used"][0]


def test_ollama_down_returns_503(client, monkeypatch):
    def boom(messages):
        raise ai.OllamaError("Cannot reach Ollama")

    monkeypatch.setattr(ai, "chat_with_ollama", boom)
    r = client.post("/ai/ask", json={"question": "How many students are there?"})
    assert r.status_code == 503
    assert "Ollama" in r.json()["detail"]


def test_question_validation(client):
    assert client.post("/ai/ask", json={"question": ""}).status_code == 422
