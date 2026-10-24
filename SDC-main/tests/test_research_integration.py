"""Public evidence and fairness guardrails at the application boundary."""

from copy import deepcopy

import pytest

from app import create_app


class EvidenceFixture:
    def snapshot(self):
        return deepcopy({"jobs": [], "ai_updates": [], "fetched_at": "2026-10-23T00:00:00Z", "signal_status": {
            "status": "offline", "jobs_count": 0, "fetched_at": "2026-10-23T00:00:00Z",
        }})

    def refresh(self, **kwargs):
        raise AssertionError("The evidence integration tests must stay offline.")


@pytest.fixture(scope="module")
def app():
    return create_app({"TESTING": True, "SOURCE_STORE": EvidenceFixture()})


def test_public_report_carries_sources_and_does_not_infer_personal_job_loss(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["private_marker"] = "SYNTHETIC_PRIVATE_ACCOUNT_DATA"
    result = client.get("/api/exposure/report/software-developer")
    assert result.status_code == 200
    assert "attachment" in result.headers["Content-Disposition"]
    assert "software-developer" in result.headers["Content-Disposition"]
    data = result.json
    assert data["personal_job_loss_probability"] is None
    assert data["research_evidence"]["source"]["year"] == 2025
    assert data["research_evidence"]["metric"]["is_probability"] is False
    assert data["research_evidence"]["licence"]["adaptation_disclaimer"]
    assert "SYNTHETIC_PRIVATE_ACCOUNT_DATA" not in result.get_data(as_text=True)


def test_published_research_never_changes_when_users_edit_planning_assumptions(app):
    client = app.test_client()
    baseline = client.get("/api/exposure?role_id=software-developer&scenario=moderate").json
    fast = client.get("/api/exposure?role_id=software-developer&scenario=fast").json
    tasks = {item["id"]: 100 for item in baseline["task_assessment"]["tasks"]}
    custom = client.post("/api/exposure/what-if", json={
        "role_id": "software-developer", "scenario": "fast", "task_assumptions": tasks,
    })
    assert custom.status_code == 200
    assert custom.json["task_assessment"]["percentage"] == 100
    assert baseline["research_evidence"] == fast["research_evidence"] == custom.json["research_evidence"]


def test_missing_mapping_is_explicit_and_never_replaced_by_a_neighbour_score(app):
    client = app.test_client()
    for role_id in ("business-intelligence-analyst", "project-management-specialist"):
        result = client.get(f"/api/exposure/evidence?role_id={role_id}")
        assert result.status_code == 200
        assert result.json["status"] == "unavailable"
        assert result.json["metric"] is None
        assert result.json["unavailable_reason"]
    assert client.get("/api/exposure/report/invented-occupation").status_code == 400
    assert client.get("/api/exposure/evidence?role_id=invented-occupation").status_code == 400


@pytest.mark.parametrize("identity", [
    {"age": 19, "gender": "woman", "ethnicity": "synthetic-group-a", "name": "Synthetic Person A"},
    {"age": 62, "gender": "man", "ethnicity": "synthetic-group-b", "name": "Synthetic Person B"},
])
def test_protected_identity_fields_do_not_change_the_skills_matching_result(app, identity):
    client = app.test_client()
    profile = {"skills": ["python", "data-analysis"], "interests": "Data and analysis", "weekly_hours": 6}
    reference = client.post("/api/match", json=profile)
    changed = client.post("/api/match", json={**profile, **identity})
    assert reference.status_code == changed.status_code == 200
    assert changed.json["profile"] == reference.json["profile"]
    assert changed.json["matches"] == reference.json["matches"]
    assert not set(identity) & set(changed.json["profile"])
