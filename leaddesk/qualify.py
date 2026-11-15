"""The result of scoring a finished lead. The scoring rules themselves are
plain code in each business profile (leaddesk/profiles/)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Qualification:
    temperature: str            # "hot", "warm" or "cold"
    score: int
    reasons: list[str] = field(default_factory=list)
