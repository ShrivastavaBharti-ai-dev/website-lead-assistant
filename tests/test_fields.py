"""Parsers for phone numbers, budgets, timelines, areas and names, plus lead scoring."""
import pytest

from leaddesk.profiles import interior as F
from leaddesk.profiles.interior import qualify


@pytest.mark.parametrize("text, expected", [
    ("call me on 98765 43210", "+919876543210"), ("+91-9876543210", "+919876543210"),
    ("09876543210", "+919876543210"), ("1234567890", None), ("I have a 2BHK", None), ("12345", None),
])
def test_phone(text, expected):
    assert F.parse_phone(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("around 8 lakh", "6_10l"), ("6-10 lakhs", "6_10l"), ("₹4,50,000", "3_6l"), ("under 3 lakh", "under_3l"),
    ("2.5 lakh", "under_3l"), ("5L", "3_6l"), ("10 lakh", "6_10l"), ("20 lakhs", "above_15l"),
    ("1.2 cr", "above_15l"), ("₹6–10 lakh", "6_10l"), ("no idea yet", None),
])
def test_budget(text, expected):
    assert F.budget_band(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("asap", "within_1m"), ("in 2 months", "1_3m"), ("maybe 4-5 months", "3_6m"), ("next month", "1_3m"),
    ("next year", "later"), ("1–3 months", "1_3m"), ("hello", None),
])
def test_timeline(text, expected):
    assert F.timeline_band(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("full home interiors for our new flat", "full_home"), ("need a modular kitchen", "kitchen"),
    ("Wardrobes", "wardrobes"), ("our clinic", "office"), ("master bedroom", "single_room"), ("hi", None),
])
def test_project_type(text, expected):
    assert F.project_type(text) == expected


def test_areas():
    assert F.match_area("flat in wakad") == "Wakad"
    assert F.match_area("PCMC") == "Pimpri-Chinchwad"
    assert F.match_area("Andheri, Mumbai") is None
    assert F.in_service_area("Koregaon Park") and not F.in_service_area("Nashik")


@pytest.mark.parametrize("text, asked, expected", [
    ("my name is rahul verma", False, "Rahul Verma"), ("Rahul", True, "Rahul"),
    ("Hi, I'm Sneha. We need a kitchen", False, "Sneha"), ("I'm looking for a kitchen", False, None),
    ("I'm planning", True, None), ("98765 43210", True, None), ("yes", True, None),
])
def test_name(text, asked, expected):
    assert F.parse_name(text, asked) == expected


def test_normalise_drops_invalid_values():
    out = F.normalise_fields({"name": "rahul", "phone": "12", "budget": "lots", "timeline": "1_3m", "area": "baner"})
    assert out == {"name": "Rahul", "timeline": "1_3m", "area": "Baner"}


def test_display_phone():
    assert F.display_phone("+919876543210") == "+91 98765 43210"


def lead(**kw):
    return {"area": "Baner", "budget": "6_10l", "timeline": "1_3m", "project_type": "full_home", **kw}


def test_scoring():
    assert qualify(lead()).temperature == "hot"
    assert qualify(lead(budget="3_6l", timeline="3_6m", project_type="kitchen")).temperature == "warm"
    assert qualify(lead(budget="under_3l", timeline="later", project_type="single_room")).temperature == "cold"


def test_outside_area_is_cold_with_reason():
    result = qualify(lead(area="Mumbai"))
    assert result.temperature == "cold" and "Outside the service area" in result.reasons[0]


def test_low_budget_for_full_home_is_flagged():
    result = qualify(lead(budget="3_6l"))
    assert any("low for a full home" in r for r in result.reasons)


def test_a_two_word_name_after_i_am():
    from leaddesk.fields import parse_name
    assert parse_name("Hi, I'm Priya Shah. Looking to rent", False) == "Priya Shah"
    assert parse_name("I'm not sure.", False) is None
