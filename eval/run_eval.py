"""Score each demo business on scripted visitor conversations, questions and (dental) safety replies.

    python eval/run_eval.py                      # all businesses, rules vs Gemini (if a key is set)
    python eval/run_eval.py --business dental    # one business
    python eval/run_eval.py --offline            # rules only, no API calls

Test data lives in eval/<business>/: conversations.jsonl, faq_questions.jsonl and, optionally,
safety.jsonl (one message each, with text the reply must and must not contain).
Writes eval/results.md; a Gemini run over all businesses also updates the table in README.md.
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
from leaddesk.profiles import dental, estate, interior  # noqa: E402

PROFILES = {p.KEY: p for p in (estate, dental, interior)}
README_START, README_END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def load(business: str, name: str) -> list[dict]:
    path = ROOT / "eval" / business / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").replace("—", "-").replace("’", "'").replace("₹", "").split())


def run_setup(profile, extractor, faq: FaqAnswerer, pause: float) -> dict:
    business = profile.KEY
    convs, questions, safety = (load(business, n) for n in ("conversations.jsonl", "faq_questions.jsonl",
                                                             "safety.jsonl"))
    field_hits = field_total = completed = temp_hits = 0
    turns_to_finish, rows = [], []
    for conv in convs:
        chat, session = Conversation(profile, extractor, faq, MemorySink()), Session()
        finished_at, temperature = None, None
        for n, message in enumerate(conv["messages"], 1):
            reply = chat.handle(session, message)
            if reply.lead_complete and finished_at is None:
                finished_at, temperature = n, reply.temperature
            time.sleep(pause)
        wrong = [k for k, v in conv["expected"].items() if session.lead.get(k) != v]
        field_hits += len(conv["expected"]) - len(wrong)
        field_total += len(conv["expected"])
        completed += finished_at is not None
        temp_hits += temperature == conv["temperature"]
        if finished_at:
            turns_to_finish.append(finished_at)
        got = ", ".join(f"{k}: {session.lead.get(k) or 'none'}" for k in wrong) or "–"
        rows.append(f"| {conv['id']} | {len(conv['expected']) - len(wrong)}/{len(conv['expected'])} | "
                    f"{temperature or 'not finished'} (expected {conv['temperature']}) | {got} |")

    faq_hits = refused_ok = answerable = unanswerable = 0
    for q in questions:
        answer = faq.answer(q["question"])
        time.sleep(pause)
        if q["answerable"]:
            answerable += 1
            ok = answer is not None and all(norm(m) in norm(answer) for m in q["must_include"])
            faq_hits += ok
        else:
            unanswerable += 1
            ok = answer is None
            refused_ok += ok
        if not ok:
            rows.append(f"| {q['id']} {q['question']} | wrong | – | {(answer or 'declined')[:120]} |")

    safety_hits = 0
    for check in safety:
        text = norm(Conversation(profile, extractor, faq, MemorySink()).handle(Session(), check["message"]).text)
        time.sleep(pause)
        ok = (all(norm(m) in text for m in check["must_include"])
              and not any(norm(m) in text for m in check["must_not_include"]))
        safety_hits += ok
        if not ok:
            rows.append(f"| {check['id']} | wrong reply | – | {text[:120]} |")

    result = {
        "completed": f"{completed}/{len(convs)}",
        "fields": f"{field_hits}/{field_total}",
        "temperature": f"{temp_hits}/{len(convs)}",
        "turns": f"{sum(turns_to_finish) / len(turns_to_finish):.1f}" if turns_to_finish else "–",
        "faq": f"{faq_hits}/{answerable}",
        "refused": f"{refused_ok}/{unanswerable}",
        "rows": rows,
    }
    if safety:
        result["safety"] = f"{safety_hits}/{len(safety)}"
    return result


LABELS = [("completed", "Conversations that ended with a saved lead"),
          ("fields", "Lead details captured correctly"),
          ("temperature", "Lead scored hot / warm / cold correctly"),
          ("turns", "Visitor messages per saved lead (average)"),
          ("faq", "Questions answered correctly from the documents"),
          ("refused", "Declined questions the documents don't cover"),
          ("safety", "Urgent and advice messages given the fixed safe reply")]


def table(results: dict) -> str:
    names = list(results)
    lines = ["| | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for key, label in LABELS:
        if key in results[names[0]]:
            lines.append(f"| {label} | " + " | ".join(results[n][key] for n in names) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--business", choices=[*PROFILES, "all"], default="all")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between Gemini calls")
    parser.add_argument("--no-readme", action="store_true")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    live = False
    if not args.offline:
        embedder, model, live = make_providers()
        if not live:
            print("No GOOGLE_API_KEY found: running rules only.\n")

    chosen = list(PROFILES) if args.business == "all" else [args.business]
    summaries, details = [], ["", "## Details", ""]
    for business in chosen:
        profile = PROFILES[business]
        setups = [("Rules only", RulesExtractor(profile),
                   FaqAnswerer(OfflineEmbedder(), OfflineAnswerModel(), profile.DOCS, profile.BUSINESS), 0.0)]
        if live:
            extractor = GeminiExtractor(profile)
            faq = FaqAnswerer(embedder, model, profile.DOCS, profile.BUSINESS,
                              cache_path=ROOT / ".cache" / f"embeddings-{business}.json")
            setups.append((f"Gemini (`{extractor.model}`)", extractor, faq, args.pause))
        results = {}
        for name, extractor, faq, pause in setups:
            print(f"Running {profile.BUSINESS}: {name}…", flush=True)
            results[name] = run_setup(profile, extractor, faq, pause)
        convs = len(load(business, "conversations.jsonl"))
        questions = len(load(business, "faq_questions.jsonl"))
        safety = len(load(business, "safety.jsonl"))
        tested = f"{convs} scripted visitor conversations and {questions} questions" + (
            f", plus {safety} urgent and advice messages" if safety else "")
        summaries.append(f"**{profile.BUSINESS}** ({tested})\n\n{table(results)}")
        for name in results:
            details += [f"### {profile.BUSINESS}: {name}", "",
                        "| Test | Details right | Lead score | What went wrong |", "|---|---|---|---|"]
            details += results[name]["rows"] + [""]

    report = (f"Measured on {date.today():%d %b %Y}.\n\n" + "\n\n".join(summaries) +
              "\n\nThe rule-based parsers were written alongside these test conversations, so their scores are "
              "optimistic. In rules-only mode, questions are answered with the best-matching passage, which is why "
              "it never declines.")
    (ROOT / "eval" / "results.md").write_text("# Evaluation results\n\n" + report + "\n" + "\n".join(details),
                                               encoding="utf-8")
    print("\n" + report + "\n\nSaved eval/results.md")

    readme = ROOT / "README.md"
    if live and args.business == "all" and not args.no_readme and readme.exists():
        text = readme.read_text(encoding="utf-8")
        if README_START in text and README_END in text:
            head, rest = text.split(README_START, 1)
            _, tail = rest.split(README_END, 1)
            readme.write_text(f"{head}{README_START}\n{report}\n{README_END}{tail}", encoding="utf-8")
            print("Updated the results table in README.md")


if __name__ == "__main__":
    main()
