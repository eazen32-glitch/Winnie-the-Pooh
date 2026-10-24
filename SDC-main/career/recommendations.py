"""Explainable, source-linked matching and learning plans.

This is a transparent retrieval baseline, not a language model or validated
labour-market forecaster. TF-IDF measures lexical overlap with a small role
catalogue. Scenarios change editorial weights, never observed source counts.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from math import ceil, log, sqrt
import re

from .catalog import ROLES, SKILLS

DISCLAIMER = (
    "Exploratory career support, not a hiring decision or a validated job forecast. "
    "Signals describe a limited global early-career job sample, not Malaysian labour-market statistics. "
    "Moderate and fast scenarios are planning assumptions. Skill requirements, SDG links "
    "and learning hours are curated estimates; real course resources and occupation sources are cited. "
    "No language model is used: matching combines weighted skills, TF-IDF lexical interest relevance "
    "and observed source-sample support."
)
SKILL_BY_ID = {skill["id"]: skill for skill in SKILLS}
_TECH_SKILLS = {"ai-literacy", "machine-learning", "prompting", "ai-ethics", "automation", "cloud"}
_ORDER = {skill["id"]: n for n, skill in enumerate(SKILLS)}
_PREREQUISITES = {
    "data-analysis": ["excel"],
    "data-visualisation": ["data-analysis"],
    "machine-learning": ["python", "statistics", "data-analysis"],
    "prompting": ["ai-literacy"],
    "ai-ethics": ["ai-literacy"],
    "automation": ["ai-literacy"],
}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from", "i", "in", "is",
    "it", "me", "my", "of", "on", "or", "the", "to", "with", "want", "enjoy", "learn", "learning",
    "work", "working", "use", "using", "people", "help", "helping", "new", "more", "that", "into",
}


def _date(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _windows(snapshot):
    windows = snapshot.get("signal_status", {}).get("windows") or {}
    end = _date(windows.get("recent_end")) or datetime.now(timezone.utc)
    recent = _date(windows.get("recent_start")) or end - timedelta(days=30)
    previous = _date(windows.get("previous_start")) or recent - timedelta(days=30)
    previous_end = _date(windows.get("previous_end")) or recent
    return recent, end, previous, previous_end


@lru_cache(maxsize=128)
def _alias_pattern(aliases):
    return re.compile(r"(?<![\w])(?:" + "|".join(re.escape(alias) for alias in aliases if alias) + r")(?![\w])", re.IGNORECASE)


def _contains(text, aliases):
    """Boundaries prevent e.g. AI matching 'chair', SQL matching 'NoSQL'."""
    return bool(aliases) and bool(_alias_pattern(tuple(aliases)).search(text))


def _evidence(job):
    return {"title": f"{job.get('title', 'Job posting')} · {job.get('company', 'Public posting')}",
            "url": job.get("url", ""), "date": str(job.get("posted_at", ""))[:10], "kind": "job"}


def _counts(jobs, predicate, windows):
    recent_start, recent_end, previous_start, previous_end = windows
    recent, previous, evidence = 0, 0, []
    for job in jobs:
        posted = job.get("_parsed_posted") or _date(job.get("posted_at"))
        if posted is None or not predicate(job):
            continue
        if recent_start <= posted < recent_end:
            recent += 1
            if len(evidence) < 3:
                evidence.append(_evidence(job))
        elif previous_start <= posted < previous_end:
            previous += 1
            if len(evidence) < 3:
                evidence.append(_evidence(job))
    return recent, previous, evidence


def _momentum(recent, previous):
    # Five observations is still exploratory; small samples never become a
    # colourful 'declining' prediction simply because the feed has no new jobs.
    if recent + previous < 5 or previous < 2:
        return None, "insufficient"
    delta = round(100.0 * (recent - previous) / previous, 1)
    return delta, "rising" if delta >= 15 else "declining" if delta <= -15 else "stable"


def _score(count, maximum):
    return round(100 * log(1 + count) / log(1 + maximum), 1) if maximum else 0.0


def build_radar(snapshot, scenario="moderate"):
    """Count mentions in two equal source windows; do not invent growth data."""
    windows = _windows(snapshot)
    # Parse dates once and ignore records outside both windows before matching
    # aliases. This keeps refresh/match requests quick with the full public feed.
    jobs = []
    for job in snapshot.get("jobs", []):
        posted = _date(job.get("posted_at"))
        if posted is not None and windows[2] <= posted < windows[1]:
            jobs.append({**job, "_parsed_posted": posted})
    jobs.sort(key=lambda job: job["_parsed_posted"], reverse=True)
    updates = [update for update in snapshot.get("ai_updates", [])
               if (published := _date(update.get("published_at"))) is not None
               and windows[2] <= published < windows[1]]
    skills, roles = [], []
    for skill in SKILLS:
        recent, previous, evidence = _counts(
            jobs, lambda job: _contains(f"{job.get('title', '')} {job.get('description', '')}", skill["aliases"]), windows)
        matching_updates = [update for update in updates
                            if _contains(f"{update.get('title', '')} {update.get('summary', '')}", skill["aliases"])]
        release_evidence = [
            {"title": update.get("title", "AI release"), "url": update.get("url", ""),
             "date": str(update.get("published_at", ""))[:10], "kind": "ai_release"}
            for update in matching_updates
        ][:2]
        momentum, label = _momentum(recent, previous)
        skills.append({"id": skill["id"], "name": skill["name"], "sdgs": skill["sdgs"],
                       "recent_count": recent, "previous_count": previous,
                       "momentum": momentum, "label": label, "evidence": evidence + release_evidence,
                       "ai_update_count": len(matching_updates)})
    for role in ROLES:
        recent, previous, evidence = _counts(jobs, lambda job: _contains(job.get("title", ""), role["aliases"]), windows)
        momentum, label = _momentum(recent, previous)
        roles.append({"id": role["id"], "title": role["title"], "sdgs": role["sdgs"],
                      "recent_count": recent, "previous_count": previous, "count": recent + previous,
                      "momentum": momentum, "label": label, "evidence": evidence})
    maximum = max((item["recent_count"] for item in skills), default=0)
    for item in skills:
        item["score"] = _score(item["recent_count"], maximum)
    maximum = max((item["recent_count"] for item in roles), default=0)
    for item in roles:
        item["score"] = _score(item["recent_count"], maximum)
    return {"signal_status": snapshot.get("signal_status", {}),
            "skills": sorted(skills, key=lambda item: (-item["score"], item["name"])),
            "roles": sorted(roles, key=lambda item: (-item["score"], item["title"])),
            "scenario": scenario, "disclaimer": DISCLAIMER}


def _tokens(text):
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1 and token not in _STOP_WORDS]


def _interest_scores(interests):
    """Smoothed TF-IDF cosine similarity against the curated role documents."""
    documents = [" ".join([role["title"], role["summary"], *role["interests"],
                           *[SKILL_BY_ID[skill["id"]]["name"] for skill in role["skills"]]]) for role in ROLES]
    counts = [Counter(_tokens(document)) for document in documents]
    doc_frequency = Counter(token for count in counts for token in count)
    idf = {token: log((1 + len(documents)) / (1 + frequency)) + 1 for token, frequency in doc_frequency.items()}

    def vector(count):
        return {token: (1 + log(frequency)) * idf[token] for token, frequency in count.items() if token in idf}

    query = vector(Counter(_tokens(interests)))
    q_norm = sqrt(sum(value * value for value in query.values()))
    scores = {}
    for role, count in zip(ROLES, counts):
        candidate = vector(count)
        norm = sqrt(sum(value * value for value in candidate.values()))
        similarity = sum(value * candidate.get(token, 0) for token, value in query.items()) / (q_norm * norm) if q_norm and norm else 0
        scores[role["id"]] = round(max(0.0, min(100.0, 100 * similarity)), 1)
    return scores


def _skill_view(identifier):
    skill = SKILL_BY_ID[identifier]
    return {"id": identifier, "name": skill["name"], "sdgs": skill["sdgs"]}


def _pathway(missing, known, weekly_hours):
    """Topological prerequisites, then a continuous hours budget across weeks."""
    required = {item["id"] for item in missing}
    steps, ordered, seen = [], [], set()

    def visit(identifier):
        if identifier in seen or identifier in known:
            return
        seen.add(identifier)
        for prerequisite in _PREREQUISITES.get(identifier, []):
            visit(prerequisite)
        ordered.append(identifier)

    for identifier in sorted(required, key=lambda identifier: _ORDER[identifier]):
        visit(identifier)
    hours_so_far = 0
    for identifier in ordered:
        skill = SKILL_BY_ID[identifier]
        hours = skill["resources"][0]["hours"]
        steps.append({"skill_id": identifier, "name": skill["name"], "hours": hours,
                      "week_start": hours_so_far // weekly_hours + 1,
                      "week_end": ceil((hours_so_far + hours) / weekly_hours),
                      "resources": skill["resources"], "sdgs": skill["sdgs"],
                      "is_prerequisite": identifier not in required})
        hours_so_far += hours
    return {"steps": steps, "total_hours": hours_so_far, "weeks": ceil(hours_so_far / weekly_hours)}


def build_skill_pathway(required_ids, known_ids, weekly_hours=6):
    """Plan the explicit gaps of a vacancy, including curated prerequisites.

    A company may require different skills from the broad occupation profile.
    Keeping this entry point separate prevents that distinction being hidden.
    """
    if any(identifier not in SKILL_BY_ID for identifier in required_ids):
        raise ValueError("Vacancy requirements must use known catalogue skills.")
    if isinstance(weekly_hours, bool) or not isinstance(weekly_hours, int) or not 1 <= weekly_hours <= 40:
        raise ValueError("Learning time must be a whole number from 1 to 40 hours.")
    known = set(known_ids)
    missing = [_skill_view(identifier) for identifier in dict.fromkeys(required_ids) if identifier not in known]
    return _pathway(missing, known, weekly_hours)


def _components(role, known, interests, skill_signals, role_signal, scenario):
    weighted_total = 0.0
    weighted_known = 0.0
    for requirement in role["skills"]:
        identifier = requirement["id"]
        signal = skill_signals[identifier]
        observed = signal["score"] / 100.0
        # Fast adoption prioritises AI-adjacent capabilities. These multipliers
        # are sensitivity assumptions, never estimated displacement rates.
        technology = identifier in _TECH_SKILLS
        scenario_factor = 1 + ((0.50 if scenario == "fast" else 0.10) * role["ai_exposure"] if technology else 0)
        # Recent software releases modestly raise learning priority, with a cap
        # at five corroborating releases. They are never employer demand counts.
        release_support = min(signal.get("ai_update_count", 0), 5) / 5.0
        release_priority = 0.10 * release_support * (1.5 if scenario == "fast" else 1.0)
        weight = requirement["weight"] * (1 + observed * 0.20 + release_priority) * scenario_factor
        weighted_total += weight
        if identifier in known:
            weighted_known += weight
    coverage = round(100 * weighted_known / weighted_total, 1) if weighted_total else 0
    # Direct occupation-title evidence and required-skill evidence are both
    # visible source support. AI releases support the explanation separately;
    # they do not count as employer demand.
    skill_support = sum(skill_signals[item["id"]]["score"] * item["weight"] for item in role["skills"]) / sum(item["weight"] for item in role["skills"])
    market = round(0.7 * role_signal["score"] + 0.3 * skill_support, 1)
    return {"skill_coverage": coverage, "interest_alignment": interests[role["id"]], "market_signal": market}


def _combined(components):
    return round(0.65 * components["skill_coverage"] + 0.20 * components["interest_alignment"] + 0.15 * components["market_signal"], 1)


def match_profile(profile, snapshot):
    """Return ranked roles, decomposable scores, gaps and estimated pathways."""
    scenario = profile.get("scenario", "moderate")
    known = set(profile.get("skills", []))
    weekly_hours = max(1, min(40, int(profile.get("weekly_hours", 6))))
    radar = build_radar(snapshot, scenario)
    skills = {item["id"]: item for item in radar["skills"]}
    roles = {item["id"]: item for item in radar["roles"]}
    interests = _interest_scores(profile.get("interests", ""))
    matches = []
    for role in ROLES:
        role_signal = roles[role["id"]]
        components = _components(role, known, interests, skills, role_signal, scenario)
        matched = [_skill_view(item["id"]) for item in role["skills"] if item["id"] in known]
        missing = [_skill_view(item["id"]) for item in role["skills"] if item["id"] not in known]
        evidence = [{"title": f"O*NET occupation: {role['title']}", "url": role["source_url"], "date": "", "kind": "occupation"}]
        evidence.extend(role_signal["evidence"][:2])
        # Retain one directly relevant skill/release citation even if the role
        # itself has few exact-title matches in this sample.
        seen_urls = {item["url"] for item in evidence}
        for requirement in role["skills"]:
            for item in skills[requirement["id"]]["evidence"]:
                if item["url"] and item["url"] not in seen_urls and len(evidence) < 6:
                    evidence.append(item)
                    seen_urls.add(item["url"])
        scenario_scores = {
            assumption: _combined(_components(role, known, interests, skills, role_signal, assumption))
            for assumption in ("moderate", "fast")
        }
        sample_count = role_signal["recent_count"]
        matches.append({
            "id": role["id"], "title": role["title"], "summary": role["summary"],
            "score": _combined(components), "components": components,
            "matched_skills": matched, "missing_skills": missing, "sdgs": role["sdgs"],
            "sdg_impact": role["sdg_impact"], "source_url": role["source_url"], "evidence": evidence,
            "explanation": (
                f"You cover {len(matched)} of {len(role['skills'])} curated skills. "
                f"Weighted skills coverage contributes 65%, lexical interest relevance 20%, "
                f"and source-sample support 15% of the score. {sample_count} recent sampled postings "
                f"match this occupation's title aliases; required-skill mentions also contribute to source support. "
                f"Recent AI releases can modestly raise a skill's learning priority, never employer demand. "
                f"The {scenario} scenario changes assumed AI-skill priorities, not observed job counts."
            ),
            "pathway": _pathway(missing, known, weekly_hours),
            "scenario_scores": scenario_scores,
            "trend": {"label": role_signal["label"], "momentum": role_signal["momentum"]},
        })
    return {"matches": sorted(matches, key=lambda item: (-item["score"], item["title"])),
            "profile": profile, "scenario": scenario, "signal_status": snapshot.get("signal_status", {}),
            "disclaimer": DISCLAIMER}
