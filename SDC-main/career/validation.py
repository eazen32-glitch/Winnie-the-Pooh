"""Shared validation for exploratory matching and the grounded assistant."""

from .catalog import SKILLS


def validate_profile(payload):
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object.")
    known_skills = {skill["id"] for skill in SKILLS}
    skills = payload.get("skills", [])
    if not isinstance(skills, list) or len(skills) > len(known_skills) or any(
        not isinstance(value, str) or value not in known_skills for value in skills
    ):
        raise ValueError("Select skills from the supplied catalog.")
    if len(set(skills)) != len(skills):
        raise ValueError("Each skill may be selected once.")
    interests = payload.get("interests", "")
    if not isinstance(interests, str) or len(interests) > 1000:
        raise ValueError("Interests must be text of at most 1,000 characters.")
    hours = payload.get("weekly_hours", 6)
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 40:
        raise ValueError("Weekly learning hours must be a whole number from 1 to 40.")
    scenario = payload.get("scenario", "moderate")
    if scenario not in ("moderate", "fast"):
        raise ValueError("Choose the moderate or fast scenario.")
    return {"skills": list(skills), "interests": interests.strip(), "weekly_hours": hours, "scenario": scenario}
