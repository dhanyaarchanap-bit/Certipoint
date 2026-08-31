"""
Activity Point Recommendation & KTU Rules Engine.
Maps student activity categories to KTU activity points, applies duration & role heuristics,
and validates maximum point caps.
"""

from typing import Dict, Any, List, Tuple
from utils.database import get_rules, get_rule_by_category


# Fallback default rules dictionary according to KTU Activity Point Guidelines
DEFAULT_KTU_RULES: Dict[str, Dict[str, Any]] = {
    "NPTEL Course": {
        "default_points": 20,
        "max_points": 50,
        "description": "NPTEL / SWAYAM / Coursera MOOC online certification courses with minimum 4-12 weeks duration.",
        "icon": "💻"
    },
    "Workshop": {
        "default_points": 10,
        "max_points": 20,
        "description": "Technical workshops organized by recognized colleges, universities, or tech organizations (1-5 days).",
        "icon": "🛠️"
    },
    "Internship": {
        "default_points": 20,
        "max_points": 40,
        "description": "Industrial / Corporate internship in recognized company or research organization (min 5-14 days).",
        "icon": "💼"
    },
    "Technical Quiz": {
        "default_points": 5,
        "max_points": 15,
        "description": "Inter-college or State/National level technical quiz and competition events.",
        "icon": "🧠"
    },
    "Hackathon": {
        "default_points": 15,
        "max_points": 30,
        "description": "Software or Hardware hackathon participation, finalist, or prize winner.",
        "icon": "🚀"
    },
    "Paper Presentation": {
        "default_points": 15,
        "max_points": 30,
        "description": "Technical paper publication or presentation in IEEE/Springer/National/International conference.",
        "icon": "📄"
    },
    "Industrial Visit": {
        "default_points": 5,
        "max_points": 10,
        "description": "Approved industrial training or industry visit organized by department.",
        "icon": "🏭"
    },
    "NSS / NCC / Community Service": {
        "default_points": 15,
        "max_points": 30,
        "description": "National Service Scheme, NCC camps, blood donation, or social outreach activities.",
        "icon": "🤝"
    },
    "Professional Body Activity": {
        "default_points": 10,
        "max_points": 20,
        "description": "Active membership and leadership in IEEE, CSI, ACM, IEDC, or ISTE student chapters.",
        "icon": "🌐"
    },
    "Sports / Cultural Competition": {
        "default_points": 10,
        "max_points": 25,
        "description": "University, State, or National level sports / arts / cultural competition representation.",
        "icon": "🏆"
    }
}


def get_all_categories() -> List[str]:
    """Return list of all supported activity categories."""
    try:
        db_rules = get_rules()
        if db_rules:
            return [r["category_name"] for r in db_rules]
    except Exception:
        pass
    return list(DEFAULT_KTU_RULES.keys())


def calculate_suggested_points(category: str, raw_text: str = "") -> Tuple[int, str]:
    """
    Calculate suggested KTU activity points based on category and textual heuristics
    (e.g., Prize winner, duration, Elite certification).
    Returns (suggested_points, explanation_reason).
    """
    category_clean = category.strip()
    rule = None
    try:
        rule = get_rule_by_category(category_clean)
    except Exception:
        pass

    if not rule and category_clean in DEFAULT_KTU_RULES:
        rule = DEFAULT_KTU_RULES[category_clean]

    if not rule:
        return 10, "Default activity points applied."

    base_points = rule["default_points"]
    max_cap = rule["max_points"]
    text_lower = (raw_text or "").lower()

    # Intelligent Heuristics based on Certificate Keywords
    bonus = 0
    reason_parts = [f"Base points for {category_clean}: {base_points} pts"]

    if category_clean == "Hackathon":
        if any(w in text_lower for w in ["winner", "first prize", "1st prize", "champion", "1st place"]):
            bonus += 15
            reason_parts.append("Awarded 1st Prize / Winner (+15 pts)")
        elif any(w in text_lower for w in ["runner up", "second prize", "2nd prize", "2nd place", "third prize", "3rd place"]):
            bonus += 10
            reason_parts.append("Awarded Podium / Runner-Up (+10 pts)")
        elif "finalist" in text_lower:
            bonus += 5
            reason_parts.append("Hackathon Finalist (+5 pts)")

    elif category_clean == "NPTEL Course":
        if "elite+gold" in text_lower or "gold medal" in text_lower:
            bonus += 15
            reason_parts.append("NPTEL Elite + Gold Certification (+15 pts)")
        elif "elite+silver" in text_lower or "silver medal" in text_lower:
            bonus += 10
            reason_parts.append("NPTEL Elite + Silver Certification (+10 pts)")
        elif "elite" in text_lower:
            bonus += 5
            reason_parts.append("NPTEL Elite Certification (+5 pts)")

    elif category_clean == "Internship":
        if any(w in text_lower for w in ["4 weeks", "1 month", "2 months", "30 days", "6 weeks", "8 weeks"]):
            bonus += 10
            reason_parts.append("Long-duration internship (>=4 weeks) (+10 pts)")

    elif category_clean == "Workshop":
        if any(w in text_lower for w in ["5 days", "1 week", "bootcamp", "faculty development program"]):
            bonus += 5
            reason_parts.append("Multi-day extended workshop/bootcamp (+5 pts)")

    total_suggested = min(base_points + bonus, max_cap)
    explanation = " | ".join(reason_parts)

    return total_suggested, explanation


def validate_awarded_points(category: str, points: int) -> Tuple[bool, str]:
    """Validate if faculty awarded points exceed KTU allowable caps for the category."""
    rule = None
    try:
        rule = get_rule_by_category(category)
    except Exception:
        pass

    if not rule and category in DEFAULT_KTU_RULES:
        rule = DEFAULT_KTU_RULES[category]

    if not rule:
        return True, "Valid"

    if points < 0:
        return False, "Points cannot be negative."
    if points > rule["max_points"]:
        return False, f"Points ({points}) exceed maximum KTU cap ({rule['max_points']}) for '{category}'."

    return True, f"Points within allowable KTU limit (Max: {rule['max_points']})."
