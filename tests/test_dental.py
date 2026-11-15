"""The dental practice profile: the fixed urgent-care reply, the appointment questions, who reception calls
first, and whole chats with the rule-based extractor and offline answers (no API key)."""
import pytest

from docanswer.providers import OfflineAnswerModel, OfflineEmbedder
from leaddesk import Conversation, MemorySink, RulesExtractor, Session
from leaddesk.faq import FaqAnswerer
from leaddesk.profiles import dental as D
from leaddesk.profiles import estate, interior
from leaddesk.sinks import full_header


@pytest.mark.parametrize("text", [
    "I'm in pain", "I have terrible toothache", "my face is swollen", "there's swelling in my gum",
    "my son knocked out a tooth", "I think I have an abscess", "it won't stop bleeding", "I've broken my tooth",
    "my tooth has snapped", "I can’t sleep it's so bad", "is this an emergency?", "I need an urgent appointment",
    "I'm in so much pain", "I can't swallow", "my daughter fell and knocked her front tooth out what do i do",
    "he got hit in the mouth playing rugby", "two teeth came out after an accident", "I banged my jaw badly",
    "her tooth got knocked loose", "how much is an emergency appointment? I'm in agony",
])
def test_urgent_messages_are_caught_by_code(text):
    reply, fields = D.urgent(text)
    assert reply == D.URGENT_REPLY and fields == {"reason": "problem", "urgent": "yes"}


@pytest.mark.parametrize("text", [
    "How much is whitening?", "Are you taking new patients?", "Request an appointment", "I'd like a check-up",
    "Is whitening painful?", "do you do implants", "what are your opening hours", "Saturday morning",
    "I've lost a filling", "do you offer sedation", "can I book my daughter in for a check-up",
    "how much is an emergency appointment?", "do you have an accident and emergency?", "I hit the wrong button",
    "my friend fell in love with her smile after whitening",
])
def test_ordinary_messages_get_no_fixed_reply(text):
    assert D.urgent(text) is None


@pytest.mark.parametrize("text", [
    "what painkillers can I take?", "is it normal for gums to bleed when brushing?",
    "should I be worried about a lump on my gum", "do I need antibiotics", "what should I do about a mouth ulcer",
    "my lip is still numb, is that normal",
])
def test_requests_for_advice_get_the_no_advice_reply_and_record_nothing(text):
    assert D.urgent(text) == (D.ADVICE_REPLY, {})


def test_advice_reply_gives_no_advice():
    text = D.ADVICE_REPLY
    assert "can't give dental or medical advice" in text and "0113 496 0456" in text and "NHS 111" in text
    assert not any(word in text.lower() for word in ("ibuprofen", "paracetamol", "painkiller", "rinse", "you should"))


def test_urgent_reply_says_where_to_get_help_and_gives_no_advice():
    text = D.URGENT_REPLY
    assert all(part in text for part in ("0113 496 0456", "NHS 111", "999", "A&E", "can't give dental or medical advice"))
    assert not any(word in text.lower() for word in ("ibuprofen", "paracetamol", "painkiller", "rinse", "take "))


def test_other_businesses_have_no_urgent_reply():
    assert interior.urgent("I'm in pain") is None and estate.urgent("it's an emergency") is None


@pytest.mark.parametrize("text, asked, expected", [
    ("New patient", True, "new"), ("Existing patient", True, "existing"), ("no, first time", True, "new"),
    ("yes", True, "existing"), ("I'm looking for a new dentist", False, "new"),
    ("I'm already registered with you", False, "existing"), ("yes", False, None),
])
def test_patient_type(text, asked, expected):
    assert D.patient_type(text, asked) == expected


@pytest.mark.parametrize("text, expected", [
    ("Check-up", "checkup"), ("I need a checkup", "checkup"), ("Hygienist", "hygienist"), ("a scale and polish", "hygienist"),
    ("I've lost a filling", "problem"), ("terrible toothache", "problem"), ("teeth whitening", "whitening"),
    ("Teeth straightening", "straightening"), ("clear aligners", "straightening"), ("Implants", "implants"),
    ("I have a missing tooth", "implants"), ("Something else", "other"), ("hello", None),
    ("is whitening painful?", "whitening"),
])
def test_reason(text, expected):
    assert D.reason(text) == expected


@pytest.mark.parametrize("text, asked, expected", [
    ("Weekday morning", True, "weekday_morning"), ("Saturday morning", True, "saturday_morning"),
    ("afternoons", True, "weekday_afternoon"), ("Thursday after 3pm", True, "Thursday after 3pm"),
    ("any time", True, "any time"), ("I work mornings", False, None), ("not mondays", True, "not mondays"),
    ("whitening", True, None), ("Afternoons are best", False, "weekday_afternoon"),
    ("can I book an appointment on a Saturday?", False, "saturday_morning"),
])
def test_visit_time(text, asked, expected):
    assert D.visit_time(text, asked) == expected


def test_normalise_drops_invalid_values_and_never_keeps_symptoms():
    out = D.normalise_fields({"name": "sam", "phone": "12", "patient_type": "maybe", "reason": "my gum is bleeding",
                              "visit_time": "weekday_morning"})
    assert out == {"name": "Sam", "visit_time": "weekday_morning"}


def test_who_reception_calls_first():
    assert D.qualify({"patient_type": "new", "reason": "implants"}).temperature == "hot"
    assert D.qualify({"patient_type": "new", "reason": "straightening"}).temperature == "hot"
    assert D.qualify({"patient_type": "new", "reason": "problem"}).temperature == "hot"
    assert D.qualify({"patient_type": "new", "reason": "checkup"}).temperature == "warm"
    assert D.qualify({"patient_type": "existing", "reason": "implants"}).temperature == "warm"
    urgent = D.qualify({"patient_type": "existing", "reason": "problem", "urgent": "yes"})
    assert urgent.temperature == "hot" and urgent.score == 100 and "call first" in urgent.reasons[0]


def test_header_matches_the_columns():
    assert len(D.LEAD_HEADER) == len(D.lead_columns({"name": "A"}))


# ---------------------------------------------------------------- whole chats
@pytest.fixture(scope="module")
def faq():
    return FaqAnswerer(OfflineEmbedder(), OfflineAnswerModel(), D.DOCS, D.BUSINESS)


def talk(faq, messages, extractor=None):
    sink = MemorySink()
    chat, session = Conversation(D, extractor or RulesExtractor(D), faq, sink), Session()
    replies = [chat.handle(session, m) for m in messages]
    return session, replies, sink


COLUMN = {name: i for i, name in enumerate(full_header(D.LEAD_HEADER))}


def test_greeting_says_it_is_an_ai_assistant(faq):
    reply = Conversation(D, RulesExtractor(D), faq, MemorySink()).greet()
    assert "AI assistant" in reply.text and "I'm in pain" in reply.quick_replies


def test_new_patient_requests_implant_appointment(faq):
    session, replies, sink = talk(faq, ["Request an appointment", "Grace Hall", "07700 900555", "New patient",
                                        "Implants", "Weekday morning"])
    assert [r.quick_replies for r in replies[2:5]] == [
        list(D.PATIENT_TYPES.values()), list(D.REASONS.values()), list(D.VISIT_TIMES.values())]
    last, row = replies[-1], sink.rows[0]
    assert last.lead_complete and last.temperature == "hot" and "07700 900555" in last.text
    assert row[COLUMN["Patient"]] == "New patient" and row[COLUMN["Appointment for"]] == "Implants"
    assert row[COLUMN["Urgent"]] == "" and sink.notifications[0]["subject"] == "Call first: Grace Hall - Implants"


def test_existing_patient_check_up_is_saved_without_an_alert(faq):
    _, replies, sink = talk(faq, ["I'd like to book a check-up", "Ben Carter", "0113 496 0999", "Existing patient",
                                  "Thursday after 3pm"])
    assert replies[-1].lead_complete and replies[-1].temperature == "warm" and "Thursday after 3pm" in replies[-1].text
    assert sink.rows[0][COLUMN["Appointment for"]] == "Check-up" and sink.notifications == []


def test_pain_gets_the_fixed_reply_first_then_an_urgent_request(faq):
    session, replies, sink = talk(faq, ["I'm in pain", "Maya Singh", "07700 900666", "no, never been",
                                        "as early as possible"])
    assert replies[0].text.startswith(D.URGENT_REPLY) and "may I have your name" in replies[0].text
    assert D.URGENT_REPLY not in replies[1].text                       # shown once, not on every message
    assert "reason" not in [session.asked] and session.lead["reason"] == "problem"   # never asked what is wrong
    last, row = replies[-1], sink.rows[0]
    assert last.temperature == "hot" and "marked your request as urgent" in last.text and "NHS 111" in last.text
    assert row[COLUMN["Urgent"]] == "YES" and row[COLUMN["Lead"]] == "HOT"
    assert sink.notifications[0]["subject"].startswith("URGENT: Maya Singh")


def test_an_urgent_question_is_never_answered_from_the_documents(faq):
    _, replies, _ = talk(faq, ["My face is swollen, what should I take for it?"])
    assert replies[0].text.startswith(D.URGENT_REPLY) and "Here's what I found" not in replies[0].text


def test_urgent_in_the_middle_of_a_request_marks_it_urgent(faq):
    session, replies, sink = talk(faq, ["Request an appointment", "Leo Marsh", "07700 900777", "Existing patient",
                                        "actually my tooth has snapped and it's bleeding", "Saturday morning"])
    assert D.URGENT_REPLY in replies[4].text and session.lead["urgent"] == "yes"
    assert sink.rows[0][COLUMN["Urgent"]] == "YES"


class BrokenExtractor:
    name, live = "broken", True

    def extract(self, message, asked, lead):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


def test_urgent_reply_is_shown_even_when_the_ai_service_fails(faq):
    session, replies, _ = talk(faq, ["I have terrible toothache"], extractor=BrokenExtractor())
    assert replies[0].text.startswith(D.URGENT_REPLY) and session.lead["urgent"] == "yes"
    with pytest.raises(RuntimeError):
        talk(faq, ["How much is whitening?"], extractor=BrokenExtractor())


def test_after_a_saved_request_pain_still_gets_the_fixed_reply(faq):
    _, replies, sink = talk(faq, ["Request an appointment", "Ana Costa", "07700 900888", "New patient", "Check-up",
                                  "Saturday morning", "now I'm in agony"])
    assert replies[-1].text.startswith(D.URGENT_REPLY) and len(sink.rows) == 1


def test_advice_questions_always_get_the_fixed_reply_never_the_documents(faq):
    session, replies, _ = talk(faq, ["what painkillers can I take?", "is it normal for gums to bleed when brushing?",
                                     "ok but now my face is swollen"])
    assert replies[0].text == replies[1].text == D.ADVICE_REPLY
    assert replies[2].text.startswith(D.URGENT_REPLY) and session.lead["urgent"] == "yes"


def test_a_question_about_the_emergency_service_is_answered_from_the_documents(faq):
    session, replies, _ = talk(faq, ["how much is an emergency appointment?"])
    assert "£85" in replies[0].text and D.URGENT_REPLY not in replies[0].text
    assert session.lead == {} and not session.collecting


def test_parent_reporting_a_knocked_out_tooth(faq):
    _, replies, sink = talk(faq, ["my daughter fell and knocked her front tooth out what do i do", "Sarah Lee",
                                  "07700 900303", "yes we're patients", "now"])
    assert replies[0].text.startswith(D.URGENT_REPLY) and replies[-1].lead_complete
    assert sink.rows[0][COLUMN["Name"]] == "Sarah Lee" and sink.rows[0][COLUMN["Urgent"]] == "YES"
    assert sink.rows[0][COLUMN["Patient"]] == "Existing patient" and sink.rows[0][COLUMN["Best time"]] == "now"


def test_everything_in_one_message(faq):
    session, replies, sink = talk(faq, ["Hi I'm Raj, I've got a missing tooth and want to ask about implants. Never "
                                        "been to you before. Can you call me on 07700 900202? Afternoons are best"])
    assert replies[0].lead_complete and replies[0].temperature == "hot"
    assert session.lead == {"phone": "+447700900202", "name": "Raj", "patient_type": "new", "reason": "implants",
                            "visit_time": "weekday_afternoon"}


def test_fee_question_is_answered_then_offers_an_appointment(faq):
    _, replies, _ = talk(faq, ["How much is a new patient examination?"])
    assert "£65" in replies[0].text and D.OFFER in replies[0].text


def test_a_day_or_a_treatment_is_not_taken_as_the_name():
    assert "name" not in D.rule_fields("Saturday morning", "name") and "name" not in D.rule_fields("Implants", "name")
    assert D.rule_fields("Grace Hall", "name")["name"] == "Grace Hall"


def test_a_price_question_does_not_start_taking_details(faq):
    session, replies, _ = talk(faq, ["how much is a hygienist appointment?"])
    assert "£72" in replies[0].text and not session.collecting and D.OFFER in replies[0].text


def test_bad_phone_is_asked_again(faq):
    session, replies, _ = talk(faq, ["Request an appointment", "Farah", "12345"])
    assert "didn't quite get" in replies[-1].text and session.asked == "phone"
