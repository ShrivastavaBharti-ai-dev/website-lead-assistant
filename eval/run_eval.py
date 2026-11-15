"""Score the assistant on 9 scripted visitor conversations and 11 questions.

    python eval/run_eval.py             # rules vs Gemini (if a key is set)
    python eval/run_eval.py --offline   # rules only, no API calls

Writes eval/results.md; a Gemini run also updates the table in README.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from docanswer import make_providers  # noqa: E402
from docanswer.providers import OfflineAnswerModel, OfflineEmbedder  # noqa: E402
from leaddesk import Conversation, GeminiExtractor, MemorySink, RulesExtractor, Session  # noqa: E402
from leaddesk.faq import FaqAnswerer  # noqa: E402
from leaddesk.fields import REQUIRED  # noqa: E402

README_START, README_END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def load(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / "eval" / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").replace("—", "-").replace("₹", "").split())


def run_setup(extractor, faq: FaqAnswerer, pause: float) -> dict:
    convs, questions = load("conversations.jsonl"), load("faq_questions.jsonl")
    field_hits = field_total = completed = temp_hits = 0
    turns_to_finish, rows = [], []
    for conv in convs:
        sink = MemorySink()
        chat, session = Conversation(extractor, faq, sink), Session()
        finished_at, temperature = None, None
        for n, message in enumerate(conv["messages"], 1):
            reply = chat.handle(session, message)
            if reply.lead_complete and finished_at is None:
                finished_at, temperature = n, reply.temperature
            time.sleep(pause)
        hits = sum(session.lead.get(k) == v for k, v in conv["expected"].items())
        field_hits += hits
        field_total += len(conv["expected"])
        completed += finished_at is not None
        temp_hits += temperature == conv["temperature"]
        if finished_at:
            turns_to_finish.append(finished_at)
        missing = [f for f in REQUIRED if not session.lead.get(f)]
        rows.append(f"| {conv['id']} | {hits}/{len(conv['expected'])} | {temperature or 'not finished'} "
                    f"(expected {conv['temperature']}) | {', '.join(missing) or '–'} |")
    faq_hits = refused_ok = answerable = unanswerable = 0
    for q in questions:
        answer = faq.answer(q["question"])
        time.sleep(pause)
        if q["answerable"]:
            answerable += 1
            faq_hits += answer is not None and all(norm(m) in norm(answer) for m in q["must_include"])
        else:
            unanswerable += 1
            refused_ok += answer is None
    return {
        "completed": f"{completed}/{len(convs)}",
        "fields": f"{field_hits}/{field_total}",
        "temperature": f"{temp_hits}/{len(convs)}",
        "turns": f"{sum(turns_to_finish) / len(turns_to_finish):.1f}" if turns_to_finish else "–",
        "faq": f"{faq_hits}/{answerable}",
        "refused": f"{refused_ok}/{unanswerable}",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between Gemini calls")
    parser.add_argument("--no-readme", action="store_true")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    offline_faq = FaqAnswerer(OfflineEmbedder(), OfflineAnswerModel(), ROOT / "business", "Terracotta Lane Interiors")
    setups = [("Rules only", RulesExtractor(), offline_faq, 0.0)]
    if not args.offline:
        embedder, model, live = make_providers()
        if live:
            faq = FaqAnswerer(embedder, model, ROOT / "business", "Terracotta Lane Interiors",
                              cache_path=ROOT / ".cache" / "embeddings.json")
            extractor = GeminiExtractor()
            setups.append((f"Gemini (`{extractor.model}`)", extractor, faq, args.pause))
        else:
            print("No GOOGLE_API_KEY found: running rules only.\n")

    results = {}
    for name, extractor, faq, pause in setups:
        print(f"Running {name}…", flush=True)
        results[name] = run_setup(extractor, faq, pause)

    names = list(results)
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for key, label in [("completed", "Conversations that ended with a saved lead"),
                       ("fields", "Lead details captured correctly"),
                       ("temperature", "Lead scored hot / warm / cold correctly"),
                       ("turns", "Visitor messages per saved lead (average)"),
                       ("faq", "Questions answered correctly from the documents"),
                       ("refused", "Declined questions the documents don't cover")]:
        lines.append(f"| {label} | " + " | ".join(results[n][key] for n in names) + " |")
    report = (f"Measured on {date.today():%d %b %Y} with 9 scripted visitor conversations (clean, messy, Hinglish, "
              "out-of-area and low-budget visitors) and 11 questions.\n\n" + "\n".join(lines))
    report += ("\n\nThe rule-based parsers were written alongside these test conversations, so their scores are "
               "optimistic. In rules-only mode, questions are answered with the best-matching passage, which is why "
               "it never declines.")

    detail = ["", "## Conversations", ""]
    for name in names:
        detail += [f"### {name}", "", "| Conversation | Details right | Lead score | Still missing |", "|---|---|---|---|"]
        detail += results[name]["rows"] + [""]
    (ROOT / "eval" / "results.md").write_text("# Evaluation results\n\n" + report + "\n" + "\n".join(detail),
                                               encoding="utf-8")
    print("\n" + report + "\n\nSaved eval/results.md")

    readme = ROOT / "README.md"
    if len(names) > 1 and not args.no_readme and readme.exists():
        text = readme.read_text(encoding="utf-8")
        if README_START in text and README_END in text:
            head, rest = text.split(README_START, 1)
            _, tail = rest.split(README_END, 1)
            readme.write_text(f"{head}{README_START}\n{report}\n{README_END}{tail}", encoding="utf-8")
            print("Updated the results table in README.md")


if __name__ == "__main__":
    main()
