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


def test_each_business_has_its_own_page_and_assistant(client):
    for business, name in (("estate", "Harbour & Finch"), ("dental", "Amberwick Dental")):
        assert client.get(f"/{business}").status_code == 200
        assert name in client.get(f"/api/{business}/greeting").json()["reply"]
        assert client.get(f"/api/{business}/health").json()["ok"] is True
    assert client.get("/nowhere").status_code == 404
    assert client.get("/api/nowhere/greeting").status_code == 404
    assert client.post("/api/nowhere/chat", json={"message": "hi"}).status_code == 404


def test_pitch_pages_load_their_own_assistant(client):
    for niche, business in (("estate-agents", "estate"), ("dental-practices", "dental")):
        page = client.get(f"/for/{niche}")
        assert page.status_code == 200 and f'data-business="{business}"' in page.text
    assert client.get("/landing.css").status_code == 200
    assert client.get("/for/plumbers").status_code == 404


def test_dental_urgent_reply_over_http(client):
    from server.main import services
    from leaddesk import MemorySink
    services["dental"].conversation.sink = MemorySink()
    reply = client.post("/api/dental/chat", json={"message": "my tooth got knocked out"}).json()["reply"]
    assert "0113 496 0456" in reply and "111" in reply


def test_one_rate_limit_across_businesses():
    from server.main import services
    limiters = {id(s.limiter) for s in services.values()}
    assert len(limiters) == 1
