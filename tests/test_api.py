"""HTTP layer. Needs fastapi and httpx (pip install -r requirements-dev.txt)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client(monkeypatch_module):
    from server.main import app, service
    from leaddesk import MemorySink
    service.conversation.sink = MemorySink()
    return TestClient(app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    # Empty values (not deleted) so load_dotenv() can't fill them from your .env: tests stay offline and free.
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "SHEETS_WEBHOOK_URL", "SHEETS_TOKEN"):
        mp.setenv(name, "")
    yield mp
    mp.undo()


def test_pages_and_health(client):
    assert client.get("/").status_code == 200
    widget = client.get("/widget.js")
    assert widget.status_code == 200 and "javascript" in widget.headers["content-type"]
    assert client.get("/api/health").json()["ok"] is True
    assert client.get("/api/greeting").json()["quick_replies"]


def test_chat_round_trip(client):
    first = client.post("/api/chat", json={"message": "Book a free consultation"}).json()
    assert "name" in first["reply"]
    second = client.post("/api/chat", json={"message": "Priya", "session_id": first["session_id"]}).json()
    assert second["session_id"] == first["session_id"] and "Priya" in second["reply"]


def test_chat_validation(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422
    assert client.post("/api/chat", json={"message": "x" * 600}).status_code == 422


def test_cors_allows_embedding(client):
    response = client.options("/api/chat", headers={"Origin": "https://example.com",
                                                    "Access-Control-Request-Method": "POST"})
    assert response.status_code == 200
