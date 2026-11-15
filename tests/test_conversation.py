"""Conversation flow with the rule-based extractor and offline answers (no API key)."""
import pytest

from docanswer.providers import OfflineAnswerModel, OfflineEmbedder
from leaddesk import Conversation, MemorySink, RulesExtractor, Session
from leaddesk.conversation import OFFER
from leaddesk.faq import FaqAnswerer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def faq():
    return FaqAnswerer(OfflineEmbedder(), OfflineAnswerModel(), ROOT / "business", "Terracotta Lane Interiors")


def talk(faq, messages):
    sink = MemorySink()
    chat, session = Conversation(RulesExtractor(), faq, sink), Session()
    replies = [chat.handle(session, m) for m in messages]
    return session, replies, sink


def test_greeting_has_choices():
    assert len(Conversation.greet().quick_replies) == 3


def test_price_question_is_answered_then_offers_consultation(faq):
    _, replies, _ = talk(faq, ["How much does a modular kitchen cost?"])
    assert "2.5 lakh" in replies[0].text and OFFER in replies[0].text
    assert "Book a free consultation" in replies[0].quick_replies


def test_full_booking_saves_one_hot_lead_and_alerts(faq):
    session, replies, sink = talk(faq, ["Book a free consultation", "Priya Kulkarni", "98220 12345", "Full home",
                                        "Baner", "₹6–10 lakh", "1–3 months"])
    assert replies[-1].lead_complete and replies[-1].temperature == "hot"
    assert len(sink.rows) == 1 and sink.rows[0][1] == "Priya Kulkarni" and sink.rows[0][10] == "HOT"
    assert sink.notifications and "Hot lead" in sink.notifications[0]["subject"]
    assert "+91 98220 12345" in replies[-1].text


def test_details_in_one_message_skip_questions(faq):
    session, replies, _ = talk(faq, ["Hi, I'm Sneha. We need a modular kitchen in Kothrud, budget around 4 lakh, "
                                     "starting within a month. My number is 91234 56789"])
    assert replies[0].lead_complete and session.lead["name"] == "Sneha"


def test_bad_phone_is_asked_again(faq):
    session, replies, _ = talk(faq, ["Book a consultation", "Farhan", "12345"])
    assert "didn't quite get" in replies[-1].text and session.asked == "phone"


def test_out_of_area_lead_is_cold_and_told_politely(faq):
    _, replies, sink = talk(faq, ["I want a quote for my office in Mumbai", "Anil", "9988776655", "Andheri, Mumbai",
                                  "20 lakh", "asap"])
    assert replies[-1].temperature == "cold" and "Pune region" in replies[-1].text
    assert sink.notifications == []


def test_declining_the_offer_stops_asking(faq):
    session, replies, _ = talk(faq, ["How much does a 2 BHK cost?", "no thanks"])
    assert not session.collecting and "No problem" in replies[-1].text


def test_after_submission_questions_still_answered_and_no_second_lead(faq):
    _, replies, sink = talk(faq, ["Book a free consultation", "Meena", "9000012345", "just my bedroom", "Aundh",
                                  "under 3 lakh", "just exploring", "What warranty do you give?", "Rahul 9876543210"])
    assert "warranty" in replies[-2].text.lower() and len(sink.rows) == 1


def test_spreadsheet_formula_text_is_kept_as_plain_text_by_name_parser(faq):
    session, _, _ = talk(faq, ["Book a consultation", "=HYPERLINK(\"x\")"])
    assert "name" not in session.lead
