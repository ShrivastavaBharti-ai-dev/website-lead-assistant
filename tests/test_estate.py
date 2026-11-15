"""The estate agency profile: UK parsers, the questions each kind of visitor gets, scoring, and whole chats
with the rule-based extractor and offline answers (no API key)."""
import pytest

from docanswer.providers import OfflineAnswerModel, OfflineEmbedder
from leaddesk import Conversation, MemorySink, RulesExtractor, Session
from leaddesk.faq import FaqAnswerer
from leaddesk.profiles import estate as E
from leaddesk.sinks import full_header


@pytest.mark.parametrize("text, expected", [
    ("call me on 07700 900123", "+447700900123"), ("+44 7700 900123", "+447700900123"),
    ("+44 (0)7700 900123", "+447700900123"), ("0117 496 0123", "+441174960123"), ("07700-900-123", "+447700900123"),
    ("12345", None), ("7700 900123", None), ("budget £450,000", None), ("09876543210", None),
    ("077009001234", None),
])
def test_phone(text, expected):
    assert E.parse_phone(text) == expected


def test_display_phone():
    assert E.display_phone("+447700900123") == "07700 900123"


@pytest.mark.parametrize("text, asked, expected", [
    ("£350k", False, "buy_300_450k"), ("around 350,000", False, "buy_300_450k"), ("300-350k", False, "buy_300_450k"),
    ("£300,000", False, "buy_200_300k"), ("up to £1.2m", False, "buy_above_650k"), ("180k max", False, "buy_under_200k"),
    ("£1,200 pcm", False, "rent_1000_1500"), ("1500 a month", False, "rent_1000_1500"),
    ("£2,500 per month", False, "rent_above_2200"), ("900", True, "rent_under_1000"), ("425000", True, "buy_300_450k"),
    ("£300,000–£450,000", False, "buy_300_450k"), ("Under £1,000 pcm", False, "rent_under_1000"),
    ("a 2 bed flat", False, None), ("1200", False, None), ("my number is 07700 900123", True, None),
    ("is it 5 minutes from the station?", False, None),
])
def test_budget(text, asked, expected):
    assert E.budget_band(text, asked) == expected


@pytest.mark.parametrize("text, expected", [
    ("Buy", "buy"), ("I'm a first-time buyer", "buy"), ("looking to rent a flat", "rent"), ("Sell my property", "sell"),
    ("Get a free valuation", "sell"), ("what is my house worth", "sell"), ("I'm a landlord", "let_out"),
    ("I want to rent out my flat", "let_out"), ("Let my property", "let_out"),
    ("we want to buy but need to sell our flat first", "buy"), ("Need to sell first", "buy"),
    ("is it worth viewing?", None), ("hello", None),
])
def test_interest(text, expected):
    assert E.interest(text) == expected


@pytest.mark.parametrize("text, asked, expected", [
    ("Cash buyer", False, "cash"), ("we have a mortgage agreed in principle", False, "aip"), ("got an AIP", False, "aip"),
    ("I need to sell my house first", False, "sell_first"), ("not yet", True, "not_yet"), ("not yet", False, None),
    ("we've got a mortgage in principle", False, "aip"),
])
def test_buying_position(text, asked, expected):
    assert E.position(text, asked) == expected


def test_areas_match_whole_words_only():
    assert E.match_area("a flat in clifton") == "Clifton"
    assert E.match_area("westbury on trym") == "Westbury-on-Trym"
    assert E.match_area("anywhere in Bristol") == "Bristol"
    assert E.match_area("local knowledge") is None          # not Knowle
    assert E.in_service_area("Southville") and not E.in_service_area("Bath")


@pytest.mark.parametrize("text, asked, expected", [
    ("I need to move within a month", False, "within_1m"), ("moving in 2 months", False, "1_3m"),
    ("asap", True, "within_1m"), ("just looking", True, "later"),
    ("is the minimum tenancy 12 months?", False, None),
])
def test_move_in(text, asked, expected):
    assert E.move_in(text, asked) == expected


@pytest.mark.parametrize("text, asked, expected", [
    ("Saturday", True, "saturday"), ("Weekday evening", True, "weekday_evening"), ("mornings", True, "weekday_day"),
    ("Tuesday after 5pm", True, "Tuesday after 5pm"), ("any time", True, "any time"),
    ("ok saturday then", True, "saturday"), ("Saturday morning", True, "Saturday morning"),
    ("can I view it on Saturday?", False, "saturday"), ("I work evenings", False, None),
    ("=HYPERLINK(1)", True, "HYPERLINK(1)"),
])
def test_visit_time(text, asked, expected):
    assert E.visit_time(text, asked) == expected


def test_each_kind_of_visitor_gets_its_own_questions():
    assert E.required({}) == ["name", "phone", "interest"]
    assert E.required({"interest": "buy"})[3:] == ["area", "budget", "position", "visit_time"]
    assert E.required({"interest": "rent"})[3:] == ["area", "budget", "move_in", "visit_time"]
    assert E.required({"interest": "sell"})[3:] == E.required({"interest": "let_out"})[3:] == ["area", "visit_time"]
    assert E.question("budget", {"interest": "rent"})[1] == list(E.RENT_BUDGETS.values())
    assert E.question("budget", {"interest": "buy"})[1] == list(E.BUY_BUDGETS.values())
    assert "your property" in E.question("area", {"interest": "sell"})[0]


def test_normalise_drops_invalid_values():
    out = E.normalise_fields({"name": "sam", "phone": "12", "interest": "invest", "budget": "lots",
                              "position": "cash", "area": "clifton", "visit_time": "weekday_day"})
    assert out == {"name": "Sam", "position": "cash", "area": "Clifton", "visit_time": "weekday_day"}


def lead(**kw):
    return {"interest": "buy", "area": "Clifton", "budget": "buy_300_450k", "position": "cash", **kw}


def test_scoring():
    assert E.qualify(lead()).temperature == "hot"
    assert E.qualify(lead(position="aip", budget="buy_200_300k")).temperature == "hot"
    assert E.qualify(lead(position="not_yet", budget="buy_450_650k")).temperature == "warm"
    assert E.qualify(lead(position="not_yet", budget="buy_under_200k")).temperature == "cold"
    rent = {"interest": "rent", "area": "Easton"}
    assert E.qualify({**rent, "budget": "rent_1000_1500", "move_in": "within_1m"}).temperature == "hot"
    assert E.qualify({**rent, "budget": "rent_under_1000", "move_in": "1_3m"}).temperature == "warm"
    assert E.qualify({**rent, "budget": "rent_under_1000", "move_in": "later"}).temperature == "cold"


def test_sellers_and_landlords_are_always_hot_and_a_chain_buyer_is_a_valuation_lead():
    assert E.qualify({"interest": "sell", "area": "Redland"}).temperature == "hot"
    assert E.qualify({"interest": "let_out", "area": "Bedminster"}).temperature == "hot"
    result = E.qualify(lead(position="sell_first", budget="buy_under_200k"))
    assert result.temperature == "hot" and "offer a valuation" in " ".join(result.reasons)


def test_outside_bristol_is_cold_whatever_else():
    result = E.qualify({"interest": "sell", "area": "Bath"})
    assert result.temperature == "cold" and "Outside Bristol" in result.reasons[0]


def test_header_matches_the_columns():
    assert len(E.LEAD_HEADER) == len(E.lead_columns(lead()))


# ---------------------------------------------------------------- whole chats
@pytest.fixture(scope="module")
def faq():
    return FaqAnswerer(OfflineEmbedder(), OfflineAnswerModel(), E.DOCS, E.BUSINESS)


def talk(faq, messages):
    sink = MemorySink()
    chat, session = Conversation(E, RulesExtractor(E), faq, sink), Session()
    replies = [chat.handle(session, m) for m in messages]
    return session, replies, sink


COLUMN = {name: i for i, name in enumerate(full_header(E.LEAD_HEADER))}


def test_greeting_says_it_is_an_ai_assistant(faq):
    reply = Conversation(E, RulesExtractor(E), faq, MemorySink()).greet()
    assert "AI assistant" in reply.text and len(reply.quick_replies) == 3


def test_cash_buyer_books_a_viewing(faq):
    session, replies, sink = talk(faq, ["Book a viewing", "Hannah Price", "07700 900123", "Buy", "Clifton",
                                        "£300,000–£450,000", "Cash buyer", "Saturday"])
    assert [r.quick_replies for r in replies[2:7]] == [
        list(E.INTERESTS.values()), [], list(E.BUY_BUDGETS.values()), list(E.POSITIONS.values()),
        list(E.VISIT_TIMES.values())]
    last, row = replies[-1], sink.rows[0]
    assert last.lead_complete and last.temperature == "hot" and "07700 900123" in last.text
    assert "sales team" in last.text and "saturday" in last.text
    assert row[COLUMN["Interest"]] == "Buy" and row[COLUMN["Buying position"]] == "Cash buyer"
    assert row[COLUMN["Best time"]] == "Saturday" and row[COLUMN["Lead"]] == "HOT"
    assert "Hot lead: Hannah Price - Buy in Clifton" == sink.notifications[0]["subject"]


def test_buyer_who_must_sell_first_is_offered_a_valuation(faq):
    _, replies, sink = talk(faq, ["Book a viewing", "Owen Hughes", "07700 900456", "Buy", "Bishopston",
                                  "£450,000–£650,000", "Need to sell first", "Weekday evening"])
    assert replies[-1].temperature == "hot" and "free valuation" in replies[-1].text
    assert "offer a valuation" in sink.rows[0][COLUMN["Why"]]


def test_tenant_is_asked_rent_and_move_in_not_buying_position(faq):
    session, replies, sink = talk(faq, ["I'd like to rent a flat, can I book a viewing?", "Priya Shah",
                                        "07700 900789", "Easton", "£1,000–£1,500 pcm", "Within a month",
                                        "Tuesday after 5pm"])
    assert "position" not in session.lead and replies[-1].lead_complete
    assert "lettings team" in replies[-1].text and "Tuesday after 5pm" in replies[-1].text
    assert sink.rows[0][COLUMN["Move-in"]] == "Within a month" and sink.rows[0][COLUMN["Lead"]] == "HOT"


def test_valuation_request_is_short_and_hot(faq):
    session, replies, sink = talk(faq, ["Get a free valuation", "Tom Baker", "0117 496 0777", "Redland",
                                        "Weekday daytime"])
    assert replies[-1].lead_complete and replies[-1].temperature == "hot" and "valuers" in replies[-1].text
    assert "your property" in replies[2].text and "valuation visit" in replies[3].text
    assert sink.rows[0][COLUMN["Budget"]] == "" and sink.notifications


def test_everything_in_one_message(faq):
    session, replies, _ = talk(faq, ["Hi, I'm Aisha. I'm a cash buyer looking in Southville, budget £350k. "
                                     "Can I book a viewing on Saturday? My number is 07700 900321"])
    assert replies[0].lead_complete and replies[0].temperature == "hot"
    assert session.lead == {"phone": "+447700900321", "name": "Aisha", "interest": "buy", "position": "cash",
                            "budget": "buy_300_450k", "area": "Southville", "visit_time": "saturday"}


def test_outside_bristol_is_told_politely_and_nobody_is_alerted(faq):
    _, replies, sink = talk(faq, ["I want to sell my house, can you value it?", "Gareth", "07700 900654", "Bath",
                                  "Saturday"])
    assert replies[-1].temperature == "cold" and "only cover Bristol" in replies[-1].text
    assert sink.notifications == []


def test_a_surname_that_is_also_an_everyday_word_is_accepted():
    assert E.parse_name("Hannah Price", True) == "Hannah Price"
    assert E.parse_name("price", True) is None and E.parse_name("House prices", True) is None


def test_an_area_or_a_day_is_not_taken_as_the_name():
    assert "name" not in E.rule_fields("Fishponds", "name") and "name" not in E.rule_fields("Thursday morning", "name")
    assert E.rule_fields("Clifton James", "name")["name"] == "Clifton James"


def test_landlord_asking_about_fees_then_wanting_a_valuation(faq):
    session, replies, sink = talk(faq, ["I'm a landlord with a flat in Bedminster, what are your fees?",
                                        "ok can someone come and value it", "Mark Ellis", "0117 496 0555",
                                        "Thursday morning"])
    assert replies[-1].lead_complete and replies[-1].temperature == "hot"
    assert "Thursday morning" in replies[-1].text
    assert sink.rows[0][COLUMN["Interest"]] == "Let my property" and sink.rows[0][COLUMN["Area"]] == "Bedminster"


def test_asking_what_a_house_is_worth_gets_the_valuation_offer(faq):
    session, replies, _ = talk(faq, ["what's my house worth?"])
    # Offline answers are only the closest passage, so the answer's wording is checked in the Gemini evaluation.
    assert E.OFFER in replies[0].text and "Get a free valuation" in replies[0].quick_replies
    assert session.lead == {"interest": "sell"}


def test_bad_phone_is_asked_again(faq):
    session, replies, _ = talk(faq, ["Book a viewing", "Farah", "12345"])
    assert "didn't quite get" in replies[-1].text and session.asked == "phone"


def test_fee_question_is_answered_then_offers_to_book(faq):
    _, replies, _ = talk(faq, ["What are your selling fees?"])
    assert "1.44%" in replies[0].text and E.OFFER in replies[0].text


def test_a_listing_is_found_by_its_code(faq):
    _, replies, _ = talk(faq, ["How much is HF-S103?"])
    assert "£245,000" in replies[0].text


def test_documents_are_split_one_listing_per_passage(faq):
    listings = [c for c in faq.engine.chunks if "Property HF-" in c.text]
    assert len(listings) == 15 and all(c.text.count("Property HF-") == 1 for c in listings)
