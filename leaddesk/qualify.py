"""Score a finished lead as hot, warm or cold, with the reasons in plain words.
Plain code, so the owner can see and change exactly how leads are ranked."""
from __future__ import annotations

from dataclasses import dataclass, field

from .fields import BUDGETS, PROJECT_TYPES, TIMELINES, in_service_area

BUDGET_POINTS = {"under_3l": 5, "3_6l": 20, "6_10l": 30, "10_15l": 35, "above_15l": 40}
TIMELINE_POINTS = {"within_1m": 25, "1_3m": 20, "3_6m": 10, "later": 0}
PROJECT_POINTS = {"full_home": 15, "kitchen": 10, "office": 10, "wardrobes": 5, "single_room": 5, "other": 0}
HOT, WARM = 70, 45


@dataclass
class Qualification:
    temperature: str            # "hot", "warm" or "cold"
    score: int
    reasons: list[str] = field(default_factory=list)


def qualify(lead: dict) -> Qualification:
    reasons: list[str] = []
    if not in_service_area(lead.get("area")):
        return Qualification("cold", 0, [f"Outside the service area ({lead.get('area') or 'unknown'})"])

    score = 20  # inside the service area
    budget, timeline, project = lead.get("budget"), lead.get("timeline"), lead.get("project_type")
    score += BUDGET_POINTS.get(budget, 0)
    score += TIMELINE_POINTS.get(timeline, 0)
    score += PROJECT_POINTS.get(project, 0)
    if budget:
        reasons.append(f"Budget {BUDGETS[budget]}")
    if timeline:
        reasons.append(f"Wants to start {TIMELINES[timeline].lower()}")
    if project:
        reasons.append(PROJECT_TYPES[project])
    if project == "full_home" and budget in ("under_3l", "3_6l"):
        score -= 15
        reasons.append("Budget may be low for a full home (a 2 BHK is usually ₹6–10 lakh)")
    if budget == "under_3l" and project not in ("kitchen", "wardrobes", "single_room"):
        reasons.append("Close to the ₹1.5 lakh minimum project value")
    temperature = "hot" if score >= HOT else "warm" if score >= WARM else "cold"
    return Qualification(temperature, max(0, min(100, score)), reasons)
