"""Lead storage (CSV, Google Sheet webhook incl. Apps Script's redirect) and the service limits."""
import csv
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from leaddesk import CsvSink, LeadService, MemorySink, RateLimiter, SheetWebhookSink
from leaddesk.sinks import BackupSink, SinkError, full_header

HEADER = full_header(["Name", "Phone"])


class FakeAppsScript(BaseHTTPRequestHandler):
    """Behaves like an Apps Script web app: POST runs the script, then 302 to a URL that returns the output."""
    received = []
    answer = {"ok": True, "added": 1}

    def do_POST(self):
        FakeAppsScript.received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(302)
        self.send_header("Location", "/echo")
        self.end_headers()

    def do_GET(self):
        body = json.dumps(FakeAppsScript.answer).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def webhook():
    server = HTTPServer(("127.0.0.1", 0), FakeAppsScript)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    FakeAppsScript.received.clear()
    FakeAppsScript.answer = {"ok": True, "added": 1}
    yield f"http://127.0.0.1:{server.server_port}/exec"
    server.shutdown()


def test_webhook_follows_redirect_and_sends_token(webhook):
    SheetWebhookSink(webhook, "secret", HEADER).save(["a", "b"], {"subject": "Hot lead", "body": "x"})
    sent = FakeAppsScript.received[0]
    assert sent["token"] == "secret" and sent["rows"] == [["a", "b"]] and sent["header"] == HEADER
    assert sent["notify"]["subject"] == "Hot lead"


def test_webhook_refusal_raises(webhook):
    FakeAppsScript.answer = {"ok": False, "error": "wrong token"}
    with pytest.raises(SinkError, match="wrong token"):
        SheetWebhookSink(webhook, "bad", HEADER).save(["a"], None)


def test_backup_keeps_lead_when_sheet_fails(tmp_path):
    backup = CsvSink(tmp_path / "leads.csv", HEADER)
    sink = BackupSink(SheetWebhookSink("http://127.0.0.1:9/exec", "t", HEADER, timeout=1), backup)
    sink.save(["Priya", "+919822012345"], None)
    rows = list(csv.reader((tmp_path / "leads.csv").open(encoding="utf-8")))
    assert rows[0] == HEADER and rows[1] == ["Priya", "+919822012345"] and sink.last_error


def test_rate_limiter():
    limiter = RateLimiter(limit=2, window=60)
    assert limiter.allow("ip", 0) and limiter.allow("ip", 1) and not limiter.allow("ip", 2)
    assert limiter.allow("ip", 70) and limiter.allow("other", 2)


class EchoConversation:
    def __init__(self):
        self.calls = 0

    @staticmethod
    def greet():
        from leaddesk.conversation import Reply
        return Reply("hello", ["a"])

    def handle(self, session, message):
        from leaddesk.conversation import Reply
        self.calls += 1
        return Reply(f"echo {message}", [])


def service(**kw):
    return LeadService(EchoConversation(), "test", "memory", **kw)


def test_service_validates_and_keeps_sessions():
    svc = service()
    assert svc.chat({"message": " "}, "ip")[0] == 400
    assert svc.chat({"message": "x" * 501}, "ip")[0] == 400
    status, first = svc.chat({"message": "hi", "page": "https://example.com/contact"}, "ip")
    assert status == 200 and first["reply"] == "echo hi" and first["session_id"]
    status, second = svc.chat({"message": "again", "session_id": first["session_id"]}, "ip")
    assert second["session_id"] == first["session_id"] and svc.health()["sessions"] == 1


def test_service_rate_limit_and_message_cap():
    svc = service(limiter=RateLimiter(limit=1, window=60))
    assert svc.chat({"message": "a"}, "ip")[0] == 200
    assert svc.chat({"message": "b"}, "ip")[0] == 429
    capped = service(max_messages=1)
    sid = capped.chat({"message": "a"}, "ip2")[1]["session_id"]
    capped.conversation.handle = lambda s, m: (_ for _ in ()).throw(AssertionError("should not be called"))
    s = capped._sessions[sid]
    s.messages = 1
    assert "end of this chat" in capped.chat({"message": "b", "session_id": sid}, "ip2")[1]["reply"]


def test_service_turns_errors_into_friendly_messages():
    svc = service()
    svc.conversation.handle = lambda s, m: (_ for _ in ()).throw(RuntimeError("429 RESOURCE_EXHAUSTED"))
    status, body = svc.chat({"message": "hi"}, "ip")
    assert status == 503 and "busy" in body["error"]


def test_old_sessions_are_dropped():
    svc = service(max_sessions=2)
    ids = [svc.chat({"message": str(i)}, f"ip{i}")[1]["session_id"] for i in range(3)]
    assert len(svc._sessions) == 2 and ids[0] not in svc._sessions
