"""Behavioural checks for matching; all market records below are synthetic."""

from copy import deepcopy
from math import ceil

import pytest

from career.catalog import PROFILES, ROLES, SDGS, SKILLS
from career.recommendations import build_radar, match_profile


@pytest.fixture
def snapshot():
    return {
        "signal_status": {"status": "cached", "windows": {
            "recent_start": "2026-09-22T00:00:00+00:00",
            "recent_end": "2026-10-22T00:00:00+00:00",
            "previous_start": "2026-08-23T00:00:00+00:00",
            "previous_end": "2026-09-22T00:00:00+00:00",
        }},
        "jobs": [], "ai_updates": [],
    }


def job(identifier, title="Data Scientist Python machine learning", date="2026-10-20T12:00:00+00:00"):
    return {"id": str(identifier), "title": title, "company": "Synthetic test company",
            "description": "Artificial intelligence and data analysis",
            "posted_at": date, "url": f"https://example.org/synthetic-job/{identifier}"}


def profile(**overrides):
    return {"skills": ["python", "communication"], "interests": "data science statistics prediction",
            "weekly_hours": 6, "scenario": "moderate", **overrides}


def by_id(items, identifier):
    return next(item for item in items if item["id"] == identifier)


def test_scores_recombine_from_displayed_components(snapshot):
    snapshot["jobs"] = [job(i) for i in range(6)]
    matches = match_profile(profile(), snapshot)["matches"]
    for item in matches:
        parts = item["components"]
        expected = 0.65 * parts["skill_coverage"] + 0.20 * parts["interest_alignment"] + 0.15 * parts["market_signal"]
        assert item["score"] == round(expected, 1)
        assert all(0 <= value <= 100 for value in parts.values())
        assert 0 <= item["score"] <= 100


def test_fresh_observations_change_actual_recommendation_scores(snapshot):
    before = match_profile(profile(), snapshot)
    updated = deepcopy(snapshot)
    updated["jobs"] = [job(i) for i in range(6)]
    after = match_profile(profile(), updated)
    assert by_id(after["matches"], "data-scientist")["score"] != by_id(before["matches"], "data-scientist")["score"]
    assert by_id(after["matches"], "data-scientist")["components"]["market_signal"] > 0
    assert by_id(build_radar(updated)["skills"], "python")["recent_count"] == 6


def test_scenarios_change_assumptions_without_rewriting_observations(snapshot):
    snapshot["jobs"] = [job(i) for i in range(6)]
    moderate = match_profile(profile(scenario="moderate"), snapshot)
    fast = match_profile(profile(scenario="fast"), snapshot)
    assert any(item["scenario_scores"]["fast"] != item["scenario_scores"]["moderate"] for item in moderate["matches"])
    assert by_id(fast["matches"], "data-scientist")["score"] == by_id(moderate["matches"], "data-scientist")["scenario_scores"]["fast"]
    radar_moderate = build_radar(snapshot, "moderate")
    radar_fast = build_radar(snapshot, "fast")
    assert radar_moderate["skills"] == radar_fast["skills"]
    assert radar_moderate["roles"] == radar_fast["roles"]


def test_missing_source_does_not_become_manufactured_market_support(snapshot):
    result = match_profile(profile(), snapshot)
    for item in result["matches"]:
        assert item["components"]["market_signal"] == 0
        assert item["evidence"][0]["kind"] == "occupation"
        assert item["evidence"][0]["url"].startswith("https://www.onetonline.org/")
    assert all(item["label"] == "insufficient" and item["momentum"] is None for item in build_radar(snapshot)["skills"])


def test_ai_release_evidence_changes_learning_priority_not_job_counts(snapshot):
    before = by_id(match_profile(profile(), snapshot)["matches"], "data-scientist")
    snapshot["ai_updates"] = [
        {"title": f"Transformers release {number}", "summary": "Deep learning model training",
         "published_at": "2026-10-19T12:00:00+00:00", "url": f"https://example.org/ai-release/{number}"}
        for number in range(6)
    ]
    snapshot["ai_updates"].append({"title": "Old machine learning release", "summary": "",
                                    "published_at": "2025-01-01T00:00:00+00:00", "url": "https://example.org/old"})
    radar = build_radar(snapshot)
    signal = by_id(radar["skills"], "machine-learning")
    assert signal["ai_update_count"] == 6  # count is not truncated to citation limit
    assert len(signal["evidence"]) == 2
    assert signal["recent_count"] == signal["previous_count"] == 0
    assert signal["label"] == "insufficient"
    after = by_id(match_profile(profile(), snapshot)["matches"], "data-scientist")
    assert after["components"]["skill_coverage"] < before["components"]["skill_coverage"]
    assert after["components"]["market_signal"] == before["components"]["market_signal"] == 0


def test_real_sample_decline_is_distinct_from_insufficient_data(snapshot):
    snapshot["jobs"] = [job(i) for i in range(2)] + [job(i + 2, date="2026-09-01T12:00:00+00:00") for i in range(8)]
    python = by_id(build_radar(snapshot)["skills"], "python")
    assert (python["recent_count"], python["previous_count"]) == (2, 8)
    assert python["label"] == "declining"
    assert python["momentum"] == -75
    snapshot["jobs"] = [job(1, date="2026-09-01T12:00:00+00:00")]
    python = by_id(build_radar(snapshot)["skills"], "python")
    assert python["label"] == "insufficient"
    assert python["momentum"] is None


def test_date_windows_are_start_inclusive_end_exclusive(snapshot):
    snapshot["jobs"] = [job(1, date="2026-08-23T00:00:00+00:00"),
                        job(2, date="2026-09-22T00:00:00+00:00"),
                        job(3, date="2026-10-22T00:00:00+00:00"),
                        job(4, date="not-a-date")]
    python = by_id(build_radar(snapshot)["skills"], "python")
    assert (python["recent_count"], python["previous_count"]) == (1, 1)


def test_alias_boundaries_avoid_sql_inside_nosql_and_ai_inside_chair(snapshot):
    snapshot["jobs"] = [{**job(1, title="NoSQL chair designer"), "description": ""}]
    radar = build_radar(snapshot)
    assert by_id(radar["skills"], "sql")["recent_count"] == 0
    assert by_id(radar["skills"], "ai-literacy")["recent_count"] == 0
    snapshot["jobs"] = [{**job(1, title="SQL Python developer"), "description": ""}]
    assert by_id(build_radar(snapshot)["skills"], "sql")["recent_count"] == 1


def test_pathway_orders_prerequisites_and_excludes_existing_skills(snapshot):
    known = ["communication"]
    target = by_id(match_profile(profile(skills=known), snapshot)["matches"], "data-scientist")
    identifiers = [step["skill_id"] for step in target["pathway"]["steps"]]
    assert "communication" not in identifiers
    assert len(identifiers) == len(set(identifiers))
    for prerequisite in ("python", "statistics", "data-analysis"):
        assert identifiers.index(prerequisite) < identifiers.index("machine-learning")
    assert identifiers.index("excel") < identifiers.index("data-analysis")
    assert target["pathway"]["total_hours"] == sum(step["hours"] for step in target["pathway"]["steps"])
    assert target["pathway"]["weeks"] == ceil(target["pathway"]["total_hours"] / 6)


def test_time_budget_changes_schedule_without_inventing_more_learning(snapshot):
    slow = by_id(match_profile(profile(weekly_hours=2), snapshot)["matches"], "data-scientist")["pathway"]
    fast = by_id(match_profile(profile(weekly_hours=20), snapshot)["matches"], "data-scientist")["pathway"]
    assert slow["total_hours"] == fast["total_hours"]
    assert slow["weeks"] > fast["weeks"]
    assert slow["weeks"] == ceil(slow["total_hours"] / 2)
    assert fast["weeks"] == ceil(fast["total_hours"] / 20)
    assert all(step["week_start"] <= step["week_end"] for step in slow["steps"])


def test_all_known_skills_produce_no_fabricated_learning_gap(snapshot):
    result = match_profile(profile(skills=[skill["id"] for skill in SKILLS]), snapshot)
    for item in result["matches"]:
        assert item["components"]["skill_coverage"] == 100
        assert not item["missing_skills"]
        assert item["pathway"] == {"steps": [], "total_hours": 0, "weeks": 0}


def test_relevant_interest_text_changes_lexical_score(snapshot):
    security = by_id(match_profile(profile(interests="security privacy risk networks trust"), snapshot)["matches"], "information-security-analyst")
    unrelated = by_id(match_profile(profile(interests="climate sustainability environment energy"), snapshot)["matches"], "information-security-analyst")
    assert security["components"]["interest_alignment"] > unrelated["components"]["interest_alignment"]


def test_catalogue_has_valid_sdg_links_and_real_https_references():
    goals = {goal["id"] for goal in SDGS}
    skill_ids = {skill["id"] for skill in SKILLS}
    assert goals == set(range(1, 18))
    for skill in SKILLS:
        assert skill["sdgs"] and set(skill["sdgs"]) <= goals
        assert skill["resources"]
        for resource in skill["resources"]:
            assert resource["url"].startswith("https://")
            assert resource["hours"] > 0
    for role in ROLES:
        assert role["sdgs"] and set(role["sdgs"]) <= goals
        assert {item["id"] for item in role["skills"]} <= skill_ids
        assert role["source_url"].startswith("https://www.onetonline.org/")
        assert role["sdg_impact"]
    for demo in PROFILES:
        assert set(demo["skills"]) <= skill_ids
