"""Where finished leads go.

* SheetWebhookSink: posts to a Google Apps Script web app that appends a row to
  a Google Sheet and emails the owner about hot leads (see integrations/).
* CsvSink: a local CSV file, used when no sheet is set up and as a backup.
"""
from __future__ import annotations

import csv
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

def full_header(lead_header: list[str]) -> list[str]:
    """A profile's own lead columns, wrapped in the columns every lead row has."""
    return ["Received", *lead_header, "Lead", "Score", "Why", "Questions asked", "Page", "Session"]


class SinkError(RuntimeError):
    pass


class LeadSink(Protocol):
    def save(self, row: list, notify: dict | None) -> None: ...


class MemorySink:
    def __init__(self):
        self.rows: list[list] = []
        self.notifications: list[dict] = []

    def save(self, row: list, notify: dict | None) -> None:
        self.rows.append(row)
        if notify:
            self.notifications.append(notify)


class CsvSink:
    def __init__(self, path: str | Path, header: list[str]):
        self.path, self.header = Path(path), header
        self._lock = threading.Lock()

    def save(self, row: list, notify: dict | None) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.path.exists()
            with self.path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if new:
                    writer.writerow(self.header)
                writer.writerow(row)


class SheetWebhookSink:
    """POST {token, tab, header, rows, notify} to the Apps Script web app."""

    def __init__(self, url: str, token: str, header: list[str], tab: str = "Leads", timeout: float = 20.0):
        self.url, self.token, self.header, self.tab, self.timeout = url, token, header, tab, timeout

    def save(self, row: list, notify: dict | None) -> None:
        payload = {"token": self.token, "tab": self.tab, "header": self.header, "rows": [row], "notify": notify}
        request = urllib.request.Request(self.url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            # Apps Script answers with a redirect; urllib follows it with a GET, which returns the result.
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as error:
            raise SinkError(f"Could not reach the Google Sheet webhook: {error}") from error
        try:
            result = json.loads(body)
        except json.JSONDecodeError as error:
            raise SinkError(f"Unexpected reply from the webhook: {body[:200]}") from error
        if not result.get("ok"):
            raise SinkError(f"The webhook refused the lead: {result.get('error', 'unknown error')}")


class BackupSink:
    """Try the main sink; if it fails, keep the lead in the backup so it is never lost."""

    def __init__(self, primary: LeadSink, backup: LeadSink):
        self.primary, self.backup = primary, backup
        self.last_error: str | None = None

    def save(self, row: list, notify: dict | None) -> None:
        try:
            self.primary.save(row, notify)
            self.last_error = None
        except Exception as error:  # noqa: BLE001
            self.last_error = str(error)
            self.backup.save(row, notify)


def make_sink(webhook_url: str | None, token: str | None, csv_path: str | Path, header: list[str],
              tab: str = "Leads") -> tuple[LeadSink, str]:
    """Returns (sink, description)."""
    if webhook_url and token:
        return BackupSink(SheetWebhookSink(webhook_url, token, header, tab), CsvSink(csv_path, header)), "Google Sheet"
    return CsvSink(csv_path, header), "local CSV file"
