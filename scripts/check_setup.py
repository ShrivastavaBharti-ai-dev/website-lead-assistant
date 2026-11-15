"""Check packages, the Gemini key and (if set up) the Google Sheet webhook.

    python scripts/check_setup.py

Makes a few small Gemini calls, and adds one test row to a "Setup test" tab
in your Google Sheet if SHEETS_WEBHOOK_URL is set.
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
problems = 0


def report(ok: bool, message: str, hint: str = "") -> None:
    global problems
    print(f"{'[ OK ]' if ok else '[FAIL]'} {message}")
    if not ok:
        problems += 1
        if hint:
            print(f"       -> {hint}")


report(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}", "Install Python 3.10 or newer (3.12 recommended).")
for module, package in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("langchain_core", "langchain-core"),
                        ("langchain_google_genai", "langchain-google-genai"), ("pypdf", "pypdf"),
                        ("docx", "python-docx"), ("numpy", "numpy"), ("dotenv", "python-dotenv")]:
    try:
        version = getattr(importlib.import_module(module), "__version__", "")
        report(True, f"{package} {version}".strip())
    except ImportError:
        report(False, f"{package} is not installed", "Run: pip install -r requirements.txt")

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
report(bool(key), f"GOOGLE_API_KEY found (ends in ...{key[-4:]})" if key else "GOOGLE_API_KEY is missing",
       "Copy .env.example to .env and paste your key from https://aistudio.google.com/apikey")

if key and problems == 0:
    try:
        from leaddesk import GeminiExtractor
        from leaddesk.profiles import interior
        found = GeminiExtractor(interior).extract("I'm Rahul, need a kitchen in Baner, budget 5 lakh", None, {})
        report(found["fields"].get("project_type") == "kitchen", f"Gemini reads lead details: {found['fields']}")
    except Exception as error:  # noqa: BLE001
        report(False, f"Gemini call failed: {type(error).__name__}: {str(error)[:300]}",
               "Check the key. If the model is not found, set GEMINI_CHAT_MODEL in .env (e.g. gemini-3.1-flash-lite).")
    try:
        from docanswer import make_providers
        from leaddesk.faq import FaqAnswerer
        embedder, model, _ = make_providers(key)
        answer = FaqAnswerer(embedder, model, interior.DOCS, interior.BUSINESS,
                             cache_path=ROOT / ".cache" / "embeddings.json").answer("How much does a modular kitchen cost?")
        report(bool(answer), f"Gemini answers from the documents: {answer!r}"[:200])
    except Exception as error:  # noqa: BLE001
        report(False, f"Document answering failed: {type(error).__name__}: {str(error)[:300]}")

url, token = os.getenv("SHEETS_WEBHOOK_URL"), os.getenv("SHEETS_TOKEN")
if url and token:
    from leaddesk.sinks import SheetWebhookSink
    try:
        SheetWebhookSink(url, token, tab="Setup test").save(
            [datetime.now().isoformat(timespec="seconds"), "Setup check", "it works"], None)
        report(True, "Google Sheet webhook works: a row was added to the 'Setup test' tab")
    except Exception as error:  # noqa: BLE001
        report(False, f"Google Sheet webhook failed: {error}",
               "Check SHEETS_WEBHOOK_URL ends in /exec, SHEETS_TOKEN matches TOKEN in the script, "
               "and the deployment has 'Who has access: Anyone'.")
else:
    print("[ -- ] Google Sheet not set up yet (optional): leads are saved to leads/interior.csv")

print()
print("All good. Next: uvicorn server.main:app --reload" if problems == 0 else f"{problems} problem(s) to fix above.")
sys.exit(1 if problems else 0)
