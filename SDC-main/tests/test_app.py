"""API behavior and validation, with isolated evidence and no external requests."""

from copy import deepcopy

import pytest

from app import create_app
from career.catalog import PROFILES, SKILLS


class MemorySource:
    def __init__(self):
        self.data = {
            "jobs": [{"id": "1", "title": "Data Analyst", "company": "Synthetic employer", "description": "Data analytics", "posted_at": "2026-10-15T12:00:00Z", "url": "https://example.org/synthetic-job", "active": True}],
            "ai_updates": [],
            "signal_status": {"status": "cached", "fetched_at": "2026-10-22T00:00:00Z", "jobs_count": 1, "source_name": "Synthetic test data", "windows": {"recent_start": "2026-09-23", "recent_end": "2026-10-23", "previous_start": "2026-08-24", "previous_end": "2026-09-23"}},
        }

    def snapshot(self):
        return deepcopy(self.data)

    def refresh(self):
        return self.snapshot(), False


@pytest.fixture
def client():
    app = create_app({"TESTING": True, "SOURCE_STORE": MemorySource()})
    return app.test_client()


def test_catalog_health_and_radar_are_available(client):
    assert client.get("/api/health").json["evidence_available"] is True
    catalog = client.get("/api/catalog").json
    assert len(catalog["sdgs"]) == 17
    assert len(catalog["roles"]) >= 6
    assert len(catalog["profiles"]) >= 3
    radar = client.get("/api/radar?scenario=fast")
    assert radar.status_code == 200
    assert radar.json["scenario"] == "fast"
    assert any(skill["recent_count"] for skill in radar.json["skills"])


def test_profile_to_ranked_roles_and_pathway(client):
    response = client.post("/api/match", json={**PROFILES[0], "scenario": "moderate"})
    assert response.status_code == 200
    data = response.json
    assert len(data["matches"]) >= 6
    assert data["matches"] == sorted(data["matches"], key=lambda role: (-role["score"], role["title"]))
    top = data["matches"][0]
    assert top["evidence"] and top["pathway"]["steps"]
    assert top["matched_skills"]
    assert data["profile"]["skills"] == PROFILES[0]["skills"]
    assert "label" not in data["profile"]  # no identifying profile data retained


@pytest.mark.parametrize("change", [
    {"skills": "python"}, {"skills": ["invented-skill"]}, {"skills": [None]},
    {"skills": [SKILLS[0]["id"], SKILLS[0]["id"]]},
    {"weekly_hours": 0}, {"weekly_hours": 41}, {"weekly_hours": True},
    {"weekly_hours": "6"}, {"weekly_hours": 2.5},
    {"interests": ["data"]}, {"interests": "x" * 1001},
    {"scenario": "certain-future"}, {"scenario": None},
])
def test_invalid_profiles_are_rejected(client, change):
    result = client.post("/api/match", json={"skills": [], "weekly_hours": 6, **change})
    assert result.status_code == 400
    assert result.json["error"]


def test_empty_profile_is_a_valid_exploratory_start(client):
    result = client.post("/api/match", json={})
    assert result.status_code == 200
    assert all(role["components"]["skill_coverage"] == 0 for role in result.json["matches"])


@pytest.mark.parametrize("body", ["[]", "null", "{invalid", '"text"'])
def test_non_object_or_malformed_json_is_rejected(client, body):
    result = client.post("/api/match", data=body, content_type="application/json")
    assert result.status_code == 400


def test_content_type_and_size_limits(client):
    assert client.post("/api/match", data="skills=python").status_code == 415
    assert client.post("/api/match", data='{"interests":"' + "x" * 20000 + '"}', content_type="application/json").status_code == 413


def test_scenarios_and_refresh_validate(client):
    assert client.get("/api/radar?scenario=bad").status_code == 400
    assert client.post("/api/signals/refresh", json={"scenario": "bad"}).status_code == 400
    response = client.post("/api/signals/refresh", json={"scenario": "fast"})
    assert response.status_code == 200
    assert response.json["refresh_attempted"] is False
    assert response.json["signal_status"]["status"] == "cached"


def test_security_headers_and_static_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"NextStep" in response.data
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/api/catalog").headers["Cache-Control"] == "no-store"


def test_harmful_profile_text_remains_data(client):
    result = client.post("/api/match", json={"interests": '<script>alert("test")</script>'})
    assert result.status_code == 200
    assert result.json["profile"]["interests"].startswith("<script>")
    assert all(0 <= role["score"] <= 100 for role in result.json["matches"])
