"""Role, profile, application and interview integration tests.

All identities and vacancies are synthetic. These tests use isolated SQLite
databases and never send mail, contact a recruiter or create a video meeting.
"""

from datetime import datetime, timedelta, timezone
from math import ceil
import json
from pathlib import Path

from flask import Flask, jsonify
import pytest
from werkzeug.exceptions import HTTPException

from career.catalog import ROLES, SKILLS
from career.workflow import init_workflow, workflow_bp


def build_app(database):
    """Exercise the blueprint independently of live trend sources."""
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="workflow-test-secret",
        WORKFLOW_DATABASE=str(database),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    init_workflow(app)
    app.register_blueprint(workflow_bp)

    @app.errorhandler(HTTPException)
    def json_error(error):
        return jsonify(error=error.description), error.code

    return app


@pytest.fixture
def app(tmp_path):
    return build_app(tmp_path / "workflow.sqlite3")


@pytest.fixture
def client(app):
    return app.test_client()


def session_info(client):
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    return response.get_json()


def change(client, path, payload=None, method="POST"):
    token = session_info(client)["csrf_token"]
    return client.open(
        path,
        method=method,
        json={} if payload is None else payload,
        headers={"X-CSRF-Token": token},
    )


def demo(client, role):
    response = change(client, "/api/auth/demo", {"role": role})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    assert data["role"] == ("hr" if role == "moderator" else role)
    assert data["user"]["role"] == ("hr" if role == "moderator" else role)
    return data


def verify_employer(client):
    """Complete all explicit fictional checks before publishing test vacancies."""
    fixture = client.get("/api/workflow/verification/capabilities").get_json()["fixture"]
    submitted = change(client, "/api/workflow/company/verification", fixture, method="PUT")
    assert submitted.status_code == 200, submitted.get_json()
    company = submitted.get_json()["company"]
    token = company["verification"]["domain_challenge"]["token"]
    checked = change(client, "/api/workflow/company/verification/challenge", {"token": token})
    assert checked.status_code == 200, checked.get_json()
    moderator = client.application.test_client()
    demo(moderator, "moderator")
    reviewed = change(moderator, f"/api/workflow/moderation/companies/{company['id']}", {
        "status": "verified", "reason": "Synthetic company, domain and fictional authorization reviewed independently.",
        "registration_confirmed": True, "domain_control_confirmed": True, "recruiter_authorization_confirmed": True,
        "authorization_reference": f"https://{fixture['domain']}/team",
        "authorization_note": "Reviewed the fictional registry, DNS simulation and synthetic recruiter role reference.",
    }, method="PATCH")
    assert reviewed.status_code == 200, reviewed.get_json()
    assert reviewed.get_json()["company"]["verification"]["can_publish"] is True
    return reviewed.get_json()["company"]


def register(client, role="jobseeker", email="learner@example.invalid"):
    response = change(
        client,
        "/api/auth/register",
        {
            "email": email,
            "password": "SyntheticPassphrase23!",
            "display_name": "Synthetic Candidate" if role == "jobseeker" else "Synthetic Recruiter",
            "role": role,
        },
    )
    assert response.status_code in (200, 201), response.get_json()
    return response.get_json()


def resume(**updates):
    return {
        "display_name": "Synthetic Candidate",
        "headline": "Aspiring data analyst",
        "education": "Synthetic diploma in information systems",
        "experience": "Synthetic classroom project analysing an open dataset",
        "location": "Kuala Lumpur",
        "skills": ["excel", "data-analysis", "communication", "project-management"],
        "interests": "Data, responsible automation and sustainable operations",
        "weekly_hours": 6,
        **updates,
    }


def company(**updates):
    return {
        "name": "Synthetic Research Company",
        "industry": "Technology",
        "location": "Kuala Lumpur",
        "description": "A synthetic employer for the hackathon demonstration.",
        "website": "https://example.org/demo-company",
        **updates,
    }


def vacancy(**updates):
    return {
        "title": "Synthetic Junior Data Analyst",
        "role_id": ROLES[0]["id"],
        "description": "A synthetic job supporting responsible data analysis.",
        "location": "Kuala Lumpur",
        "work_mode": "hybrid",
        "employment_type": "full-time",
        "required_skills": ["excel", "data-analysis", "sql"],
        "salary_min": 3500, "salary_max": 5500, "salary_currency": "MYR", "salary_period": "month",
        "deadline": (datetime.now(timezone.utc).date() + timedelta(days=30)).isoformat(),
        **updates,
    }


def save_resume(client, **updates):
    response = change(client, "/api/workflow/profile", resume(**updates), method="PUT")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def save_company(client, **updates):
    response = change(client, "/api/workflow/profile", company(**updates), method="PUT")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def applications(client):
    response = client.get("/api/workflow/applications")
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def application_for(data, identifier):
    return next(item for item in data["applications"] if item["id"] == identifier)


def apply_to_demo_employer(app):
    """Create one application visible to both role-scoped clients."""
    learner = app.test_client()
    employer = app.test_client()
    register(learner)
    save_resume(learner)
    demo(employer, "hr")
    jobs = employer.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    job = next(item for item in jobs if item["status"] == "open")
    response = change(learner, "/api/workflow/applications", {"job_id": job["id"]})
    assert response.status_code in (200, 201), response.get_json()
    submitted = next(item for item in applications(learner)["applications"] if item["job"]["id"] == job["id"])
    return learner, employer, submitted, job


def interview(**updates):
    return {
        "start": (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat(),
        "duration_minutes": 45,
        "meeting_url": "https://example.org/demo-interview",
        "notes": "Synthetic online interview; no meeting is created by this app.",
        **updates,
    }


def test_guest_can_explore_synthetic_jobs_with_transparent_skill_matches(client):
    info = session_info(client)
    assert info["user"] is None and info["role"] == "guest"
    assert info["csrf_token"]
    response = client.get("/api/workflow/jobs?skills=excel,data-analysis")
    assert response.status_code == 200
    jobs = response.get_json()["jobs"]
    assert len(jobs) >= 6
    for job in jobs:
        assert job["synthetic"] is True
        assert job["company"]["name"]
        requirements = {item["id"] for item in job["required_skills"]}
        matched = {item["id"] for item in job["match"]["matched_skills"]}
        missing = {item["id"] for item in job["match"]["missing_skills"]}
        assert matched | missing == requirements
        assert not matched & missing
        assert job["match"]["percentage"] == pytest.approx(100 * len(matched) / len(requirements), abs=0.1)
        assert job["application_id"] is None


@pytest.mark.parametrize("path", ["/api/workflow/profile", "/api/workflow/applications", "/api/workflow/calendar", "/api/workflow/calendar.ics"])
def test_guest_cannot_read_private_workflow_data(client, path):
    assert client.get(path).status_code == 401


def test_guest_cannot_apply_even_with_valid_csrf(client):
    job = client.get("/api/workflow/jobs").get_json()["jobs"][0]
    result = change(client, "/api/workflow/applications", {"job_id": job["id"]})
    assert result.status_code == 401


def test_auth_mutations_require_and_rotate_csrf_tokens(client):
    initial = session_info(client)["csrf_token"]
    assert client.post("/api/auth/demo", json={"role": "hr"}).status_code == 403
    assert client.post("/api/auth/demo", json={"role": "hr"}, headers={"X-CSRF-Token": "wrong-token"}).status_code == 403
    signed_in = demo(client, "hr")
    assert signed_in["csrf_token"] != initial
    stale = client.post("/api/auth/logout", json={}, headers={"X-CSRF-Token": initial})
    assert stale.status_code == 403
    assert session_info(client)["role"] == "hr"
    signed_out = change(client, "/api/auth/logout").get_json()
    assert signed_out["role"] == "guest"
    assert signed_out["csrf_token"] != signed_in["csrf_token"]


def test_registration_login_and_logout_preserve_stored_role(client):
    registered = register(client)
    assert registered["user"]["onboarding_complete"] is False
    assert "password" not in json.dumps(registered).lower()
    change(client, "/api/auth/logout")
    wrong = change(client, "/api/auth/login", {"email": "learner@example.invalid", "password": "wrongpassphrase"})
    assert wrong.status_code == 401
    assert session_info(client)["user"] is None
    login = change(client, "/api/auth/login", {"email": "learner@example.invalid", "password": "SyntheticPassphrase23!", "role": "hr"})
    assert login.status_code == 200
    assert login.get_json()["role"] == "jobseeker"
    duplicate = change(client, "/api/auth/register", {"email": "learner@example.invalid", "password": "SyntheticPassphrase23!", "display_name": "Other person", "role": "hr"})
    assert duplicate.status_code == 409


def test_password_is_hashed_in_persistent_storage(app):
    person = app.test_client()
    register(person)
    database = Path(app.config["WORKFLOW_DATABASE"])
    # Check SQLite and any journal/WAL files without depending on table names.
    for file in database.parent.glob(database.name + "*"):
        if file.is_file():
            assert b"SyntheticPassphrase23!" not in file.read_bytes()


@pytest.mark.parametrize("method,path,payload", [
    ("PUT", "/api/workflow/profile", resume()),
    ("POST", "/api/workflow/applications", {"job_id": 1}),
    ("PATCH", "/api/workflow/applications/1", {"status": "withdrawn"}),
    ("POST", "/api/workflow/jobs", vacancy()),
    ("PATCH", "/api/workflow/jobs/1", {"status": "closed"}),
    ("POST", "/api/workflow/applications/1/interview", interview()),
    ("PATCH", "/api/workflow/interviews/1", {"status": "confirmed"}),
])
def test_every_workflow_mutation_requires_csrf(client, method, path, payload):
    demo(client, "jobseeker")
    assert client.open(path, method=method, json=payload).status_code == 403


@pytest.mark.parametrize("field,value", [("role", "admin"), ("role", "guest"), ("email", "invalid-email"), ("password", "short"), ("display_name", "")])
def test_registration_rejects_invalid_values(client, field, value):
    body = {"email": "valid@example.invalid", "password": "SyntheticPassphrase23!", "display_name": "Synthetic Person", "role": "jobseeker", field: value}
    response = change(client, "/api/auth/register", body)
    assert response.status_code == 400
    assert session_info(client)["user"] is None


def test_demo_role_is_validated(client):
    assert change(client, "/api/auth/demo", {"role": "admin"}).status_code == 400


def test_resume_save_completes_onboarding_and_versions_edits(client):
    register(client)
    first = save_resume(client)
    assert first["user"]["onboarding_complete"] is True
    assert first["resume"]["skills"] == resume()["skills"]
    assert first["company"] is None
    second = save_resume(client, headline="Edited synthetic headline")
    assert second["resume"]["version"] == first["resume"]["version"] + 1
    assert client.get("/api/workflow/profile").get_json()["resume"]["headline"] == "Edited synthetic headline"


@pytest.mark.parametrize("updates", [{"skills": ["unknown-skill"]}, {"skills": "python"}, {"weekly_hours": 0}, {"weekly_hours": True}, {"weekly_hours": 41}])
def test_profile_validation_preserves_previous_data(client, updates):
    demo(client, "jobseeker")
    original = client.get("/api/workflow/profile").get_json()["resume"]
    assert change(client, "/api/workflow/profile", resume(**updates), method="PUT").status_code == 400
    assert client.get("/api/workflow/profile").get_json()["resume"] == original


def test_hr_can_save_company_but_cannot_apply(client):
    register(client, "hr", "new-hr@example.invalid")
    profile = save_company(client)
    assert profile["user"]["onboarding_complete"] is True
    assert profile["company"]["name"] == company()["name"]
    assert profile["resume"] is None
    job = client.get("/api/workflow/jobs").get_json()["jobs"][0]
    assert change(client, "/api/workflow/applications", {"job_id": job["id"]}).status_code == 403


def test_job_creation_is_owned_and_closing_prevents_applications(app):
    hr, learner = app.test_client(), app.test_client()
    register(hr, "hr", "new-hr@example.invalid")
    save_company(hr)
    verify_employer(hr)
    result = change(hr, "/api/workflow/jobs", vacancy())
    assert result.status_code in (200, 201), result.get_json()
    owned = hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    assert len(owned) == 1 and owned[0]["title"] == vacancy()["title"]
    job = owned[0]
    assert change(hr, f"/api/workflow/jobs/{job['id']}", {"status": "closed"}, method="PATCH").status_code == 200
    register(learner)
    save_resume(learner)
    denied = change(learner, "/api/workflow/applications", {"job_id": job["id"]})
    assert denied.status_code in (400, 409)
    assert applications(learner)["applications"] == []


def test_jobseekers_cannot_create_jobs(client):
    demo(client, "jobseeker")
    assert change(client, "/api/workflow/jobs", vacancy()).status_code == 403


def test_application_requires_completed_resume_and_prevents_duplicates(app):
    learner = app.test_client()
    register(learner)
    job = learner.get("/api/workflow/jobs").get_json()["jobs"][0]
    incomplete = change(learner, "/api/workflow/applications", {"job_id": job["id"]})
    assert incomplete.status_code in (400, 409)
    save_resume(learner)
    assert change(learner, "/api/workflow/applications", {"job_id": job["id"]}).status_code in (200, 201)
    assert change(learner, "/api/workflow/applications", {"job_id": job["id"]}).status_code == 409
    assert len(applications(learner)["applications"]) == 1


def test_submitted_resume_is_an_immutable_snapshot(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    before = application_for(applications(hr), submitted["id"])
    snapshot = before["applicant"]["resume"]
    saved_match = before["match"]
    save_resume(learner, skills=[skill["id"] for skill in SKILLS], display_name="Edited Synthetic Candidate")
    after = application_for(applications(hr), submitted["id"])
    assert after["applicant"]["resume"] == snapshot
    assert after["match"] == saved_match
    assert after["applicant"]["resume"]["display_name"] == "Synthetic Candidate"


def test_hr_cannot_read_or_mutate_another_company_applicants(app):
    learner, first_hr, submitted, job = apply_to_demo_employer(app)
    other_hr = app.test_client()
    register(other_hr, "hr", "other-hr@example.invalid")
    save_company(other_hr, name="Other Synthetic Company")
    assert applications(other_hr)["applications"] == []
    assert change(other_hr, f"/api/workflow/applications/{submitted['id']}", {"status": "accepted", "reason": "Synthetic offer based on stated skills."}, method="PATCH").status_code in (403, 404)
    assert change(other_hr, f"/api/workflow/applications/{submitted['id']}/interview", interview()).status_code in (403, 404)
    assert change(other_hr, f"/api/workflow/jobs/{job['id']}", {"status": "closed"}, method="PATCH").status_code in (403, 404)
    assert application_for(applications(first_hr), submitted["id"])["status"] == submitted["status"]
    assert len(applications(learner)["applications"]) == 1


def test_jobseeker_cannot_accept_their_own_application(app):
    learner, _, submitted, _ = apply_to_demo_employer(app)
    assert change(learner, f"/api/workflow/applications/{submitted['id']}", {"status": "accepted", "reason": "Synthetic offer based on stated skills."}, method="PATCH").status_code == 403


def test_hr_decisions_are_visible_to_applicant(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    for status in ("under_review", "shortlisted", "accepted"):
        result = change(hr, f"/api/workflow/applications/{submitted['id']}", {"status": status, "reason": "Synthetic role review completed."}, method="PATCH")
        assert result.status_code == 200, result.get_json()
        assert application_for(applications(learner), submitted["id"])["status"] == status


def test_interview_scheduling_confirmation_and_calendar_are_consistent(app):
    learner, hr, submitted, job = apply_to_demo_employer(app)
    body = interview()
    scheduled = change(hr, f"/api/workflow/applications/{submitted['id']}/interview", body)
    assert scheduled.status_code in (200, 201), scheduled.get_json()
    record = application_for(applications(learner), submitted["id"])
    assert record["status"] == "interview_scheduled"
    booking = record["interview"]
    assert booking["status"] == "scheduled"
    assert booking["meeting_url"] == body["meeting_url"]
    assert datetime.fromisoformat(booking["start"].replace("Z", "+00:00")) == datetime.fromisoformat(body["start"])
    confirmed = change(learner, f"/api/workflow/interviews/{booking['id']}", {"status": "confirmed"}, method="PATCH")
    assert confirmed.status_code == 200
    for person in (learner, hr):
        calendar = person.get("/api/workflow/calendar")
        assert calendar.status_code == 200
        events = calendar.get_json()["events"]
        own_interview = next(item for item in events if item["type"] == "interview" and item["application_id"] == submitted["id"])
        assert own_interview["status"] == "confirmed"
        assert own_interview["timezone"] == "Asia/Kuala_Lumpur"
        assert own_interview["job_id"] == job["id"]
        calendar_file = person.get("/api/workflow/calendar.ics")
        assert calendar_file.status_code == 200
        assert calendar_file.mimetype == "text/calendar"
        assert b"BEGIN:VCALENDAR" in calendar_file.data
        assert b"BEGIN:VEVENT" in calendar_file.data
        assert "attachment" in calendar_file.headers["Content-Disposition"]


def test_interview_rescheduling_reuses_one_booking(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    path = f"/api/workflow/applications/{submitted['id']}/interview"
    assert change(hr, path, interview()).status_code in (200, 201)
    original = application_for(applications(learner), submitted["id"])["interview"]
    new_time = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0).isoformat()
    assert change(hr, path, interview(start=new_time)).status_code in (200, 201)
    updated = application_for(applications(learner), submitted["id"])["interview"]
    assert updated["id"] == original["id"]
    assert datetime.fromisoformat(updated["start"].replace("Z", "+00:00")) == datetime.fromisoformat(new_time)
    events = learner.get("/api/workflow/calendar").get_json()["events"]
    assert len([item for item in events if item["type"] == "interview" and item["application_id"] == submitted["id"]]) == 1


@pytest.mark.parametrize("updates", [
    {"start": "2026-10-22T12:00:00"},
    {"start": "not-a-date"},
    {"start": "2000-01-01T12:00:00+00:00"},
    {"duration_minutes": 0},
    {"duration_minutes": True},
    {"duration_minutes": 181},
    {"meeting_url": "javascript:alert(1)"},
    {"meeting_url": "http://example.org/demo"},
    {"meeting_url": "https://example.org/demo meeting"},
    {"start": "9999-12-31T23:59:00+00:00", "duration_minutes": 180},
])
def test_invalid_interview_input_cannot_create_a_booking(app, updates):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    result = change(hr, f"/api/workflow/applications/{submitted['id']}/interview", interview(**updates))
    assert result.status_code == 400
    assert application_for(applications(learner), submitted["id"])["interview"] is None


@pytest.mark.parametrize("terminal,actor", [("withdrawn", "learner"), ("rejected", "hr")])
def test_withdrawal_or_rejection_cancels_interview_and_blocks_reschedule(app, terminal, actor):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    path = f"/api/workflow/applications/{submitted['id']}"
    assert change(hr, path + "/interview", interview()).status_code in (200, 201)
    person = learner if actor == "learner" else hr
    assert change(person, path, {"status": terminal, "reason": "Synthetic role review completed."}, method="PATCH").status_code == 200
    record = application_for(applications(learner), submitted["id"])
    assert record["status"] == terminal
    assert record["interview"]["status"] == "cancelled"
    assert change(hr, path + "/interview", interview()).status_code in (400, 409)


def test_interview_cancellation_resets_nonterminal_application(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    path = f"/api/workflow/applications/{submitted['id']}/interview"
    assert change(hr, path, interview()).status_code in (200, 201)
    booking = application_for(applications(learner), submitted["id"])["interview"]
    result = change(learner, f"/api/workflow/interviews/{booking['id']}", {"status": "cancelled"}, method="PATCH")
    assert result.status_code == 200
    record = application_for(applications(learner), submitted["id"])
    assert record["status"] == "under_review"
    assert record["interview"]["status"] == "cancelled"


def test_calendar_and_pending_counts_are_role_scoped(app):
    _, hr, _, _ = apply_to_demo_employer(app)
    mine = hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    own_ids = {job["id"] for job in mine}
    assert own_ids
    calendar = hr.get("/api/workflow/calendar").get_json()["events"]
    assert all(event["job_id"] in own_ids for event in calendar)
    before = applications(hr)
    pending = next(item for item in before["applications"] if item["status"] in {"submitted", "under_review", "shortlisted", "interview_scheduled"})
    assert change(hr, f"/api/workflow/applications/{pending['id']}", {"status": "rejected", "reason": "Synthetic decision: another profile fits the requirements."}, method="PATCH").status_code == 200
    assert applications(hr)["pending_count"] == before["pending_count"] - 1


def test_seed_initialization_preserves_saved_profiles_and_does_not_duplicate(app):
    hr = app.test_client()
    demo(hr, "hr")
    initial_jobs = hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    initial_apps = applications(hr)["applications"]
    save_company(hr, name="Edited Synthetic Employer")
    second_app = build_app(app.config["WORKFLOW_DATABASE"])
    second_hr = second_app.test_client()
    demo(second_hr, "hr")
    assert second_hr.get("/api/workflow/profile").get_json()["company"]["name"] == "Edited Synthetic Employer"
    assert len(second_hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"]) == len(initial_jobs)
    assert len(applications(second_hr)["applications"]) == len(initial_apps)


@pytest.mark.parametrize("path,method,payload", [
    ("/api/auth/register", "POST", {"email": "malformed@example.invalid", "password": "SyntheticPassphrase23!", "display_name": "Synthetic Person", "role": []}),
    ("/api/auth/demo", "POST", {"role": {}}),
    ("/api/workflow/jobs", "POST", vacancy(role_id=[])),
    ("/api/workflow/jobs", "POST", vacancy(work_mode={})),
    ("/api/workflow/jobs", "POST", vacancy(employment_type=[])),
    ("/api/workflow/jobs/1", "PATCH", {"status": {}}),
    ("/api/workflow/applications/1", "PATCH", {"status": []}),
    ("/api/workflow/interviews/1", "PATCH", {"status": {}}),
])
def test_enum_payload_types_are_rejected_without_server_errors(client, path, method, payload):
    demo(client, "hr")
    response = change(client, path, payload, method=method)
    assert 400 <= response.status_code < 500
    assert response.get_json()["error"]


def test_workflow_routes_are_registered_in_the_actual_app_factory(tmp_path):
    from app import create_app

    integrated = create_app({
        "TESTING": True,
        "SECRET_KEY": "integration-test-secret",
        "WORKFLOW_DATABASE": str(tmp_path / "integrated.sqlite3"),
    }).test_client()
    assert integrated.get("/api/health").status_code == 200
    assert integrated.get("/api/catalog").get_json()["skills"]
    assert session_info(integrated)["role"] == "guest"
    assert demo(integrated, "jobseeker")["role"] == "jobseeker"
    assert integrated.get("/api/workflow/profile").status_code == 200
    assert applications(integrated)["applications"]


def test_non_ascii_csrf_input_is_rejected_without_server_error(client):
    session_info(client)
    response = client.post(
        "/api/auth/demo", json={"role": "hr"},
        headers={"X-CSRF-Token": "synthetic-令牌"},
    )
    assert response.status_code == 403


def test_company_cannot_double_book_interviews(app):
    _, hr, submitted, _ = apply_to_demo_employer(app)
    other = next(item for item in applications(hr)["applications"] if item["id"] != submitted["id"])
    body = interview()
    assert change(hr, f"/api/workflow/applications/{submitted['id']}/interview", body).status_code in (200, 201)
    conflict = change(hr, f"/api/workflow/applications/{other['id']}/interview", body)
    assert conflict.status_code == 409
    assert application_for(applications(hr), other["id"])["interview"] is None


def test_unrepresentable_calendar_deadline_cannot_be_posted(client):
    demo(client, "hr")
    before = client.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    result = change(client, "/api/workflow/jobs", vacancy(deadline="9999-12-31"))
    assert result.status_code == 400
    assert client.get("/api/workflow/jobs?mine=1").get_json()["jobs"] == before


def test_company_website_with_embedded_newline_is_rejected(client):
    demo(client, "hr")
    before = client.get("/api/workflow/profile").get_json()["company"]
    response = change(
        client, "/api/workflow/profile",
        company(website="https://example.org/demo\ncompany"), method="PUT",
    )
    assert response.status_code == 400
    assert client.get("/api/workflow/profile").get_json()["company"] == before


def test_custom_job_pathway_uses_actual_requirements_and_stored_learning_budget(app):
    """An employer-added skill outside the occupation profile must be planned."""
    hr, learner = app.test_client(), app.test_client()
    register(hr, "hr", "custom-pathway-hr@example.invalid")
    save_company(hr)
    verify_employer(hr)
    assert "machine-learning" not in {item["id"] for item in ROLES[0]["skills"]}
    created = change(hr, "/api/workflow/jobs", vacancy(required_skills=["communication", "machine-learning"]))
    assert created.status_code == 201
    job_id = created.get_json()["job"]["id"]
    register(learner)
    save_resume(learner, skills=["communication", "python"], weekly_hours=2)
    # Authenticated jobseekers use their saved profile, ignoring query attempts
    # to substitute requirements coverage or a more convenient time budget.
    response = learner.get("/api/workflow/jobs?skills=machine-learning&weekly_hours=40")
    job = next(item for item in response.get_json()["jobs"] if item["id"] == job_id)
    plan = job["pathway"]
    skills = [step["skill_id"] for step in plan["steps"]]
    assert job["match"]["percentage"] == 50
    assert "machine-learning" in skills
    assert not {"communication", "python"} & set(skills)
    assert {"excel", "data-analysis", "statistics"} <= set(skills)
    assert skills.index("excel") < skills.index("data-analysis") < skills.index("machine-learning")
    assert skills.index("statistics") < skills.index("machine-learning")
    assert plan["weekly_hours"] == 2
    assert plan["total_hours"] == sum(step["hours"] for step in plan["steps"])
    assert plan["weeks"] == ceil(plan["total_hours"] / 2)
    assert all(step["resources"] and step["sdgs"] for step in plan["steps"])


def test_guest_job_pathway_respects_the_temporary_learning_budget(client):
    slow = client.get("/api/workflow/jobs?skills=communication,python&weekly_hours=2").get_json()
    fast = client.get("/api/workflow/jobs?skills=communication,python&weekly_hours=20").get_json()
    assert slow["profile"]["weekly_hours"] == 2
    assert fast["profile"]["weekly_hours"] == 20
    slow_jobs = {job["id"]: job for job in slow["jobs"]}
    assert any(job["pathway"]["weeks"] < slow_jobs[job["id"]]["pathway"]["weeks"] for job in fast["jobs"])
    for job in fast["jobs"]:
        assert job["pathway"]["total_hours"] == slow_jobs[job["id"]]["pathway"]["total_hours"]
        assert job["pathway"]["weeks"] == ceil(job["pathway"]["total_hours"] / 20)


@pytest.mark.parametrize("hours", ["0", "41", "-2", "2.5", "true", ""])
def test_guest_learning_budget_query_is_validated(client, hours):
    response = client.get("/api/workflow/jobs", query_string={"weekly_hours": hours})
    assert response.status_code == 400
    assert response.get_json()["error"]
