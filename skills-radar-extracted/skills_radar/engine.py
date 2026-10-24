"""Radar counting functions extracted from career/recommendations.py."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from math import log
from pathlib import Path
import json
import re

CATALOG = json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))
SKILLS, ROLES = CATALOG['skills'], CATALOG['roles']
DISCLAIMER = 'Counts and directions describe a dated international job sample, not a job forecast or Malaysian labour-market statistics. SDG mappings are curated.'

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

