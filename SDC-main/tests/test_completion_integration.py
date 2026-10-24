"""Integration boundaries for the completed prototype, with no external calls."""

from copy import deepcopy

import pytest

from app import create_app
from career.catalog import ROLES


class OfflineEvidence:
    def snapshot(self):
        return deepcopy({"jobs": [], "ai_updates": [], "signal_status": {
            "status": "offline", "jobs_count": 0,
            "fetched_at": "2026-10-23T00:00:00Z",
        }})

    def refresh(self, **kwargs):
        raise AssertionError("Tests must not automatically contact public feeds.")


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SOURCE_STORE": OfflineEvidence()})


def test_testing_never_starts_external_source_monitor(app):
    client = app.test_client()
    response = client.get("/api/monitor/status")
    assert response.status_code == 200
    assert response.json["running"] is False
    assert response.json["enabled"] is False
    discoveries = client.get("/api/monitor/discoveries")
    assert discoveries.status_code == 200
    assert discoveries.json["items"] == []


def test_online_assistant_requires_csrf_before_model_code_is_called(app, monkeypatch):
    calls = []

    def fake_reply(*args, **kwargs):
        calls.append(kwargs)
        return {"answer": "Synthetic grounded reply", "sources": []}

    monkeypatch.setattr("career.llm.enhanced_reply", fake_reply)
    client = app.test_client()
    payload = {"message": "Suggest roles", "use_model": True, "external_consent": True}
    assert client.post("/api/assistant", json=payload).status_code == 403
    assert calls == []
    token = client.get("/api/auth/session").json["csrf_token"]
    result = client.post("/api/assistant", json=payload, headers={"X-CSRF-Token": token})
    assert result.status_code == 200
    assert calls[0]["use_model"] is True and calls[0]["consent"] is True


@pytest.mark.parametrize("field", ["use_model", "external_consent"])
def test_model_opt_in_rejects_non_boolean_flags(app, field):
    response = app.test_client().post("/api/assistant", json={"message": "Help", field: "false"})
    assert response.status_code == 400


def test_what_if_exposure_uses_explicit_assumptions_and_validates_bounds(app):
    client = app.test_client()
    role_id = ROLES[0]["id"]
    base = client.get(f"/api/exposure?role_id={role_id}")
    assert base.status_code == 200
    tasks = base.json["task_assessment"]["tasks"]
    assumptions = {task["id"]: 0 for task in tasks}
    result = client.post("/api/exposure/what-if", json={"role_id": role_id, "task_assumptions": assumptions})
    assert result.status_code == 200
    assert result.json["task_assessment"]["percentage"] == 0
    assumptions[tasks[0]["id"]] = 101
    assert client.post("/api/exposure/what-if", json={"role_id": role_id, "task_assumptions": assumptions}).status_code == 400
    assert client.post("/api/exposure/what-if", json={"role_id": [role_id]}).status_code == 400


def test_guest_cannot_read_messages_and_new_views_render(app):
    client = app.test_client()
    assert client.get("/api/messages/threads").status_code == 401
    page = client.get("/")
    assert page.status_code == 200
    assert b'data-section="messages"' in page.data
    assert b'data-demo-role="moderator"' in page.data
