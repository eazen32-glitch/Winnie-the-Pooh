"""Salary, independent moderation and accountable application lifecycle checks."""

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from test_workflow import (
    app, client, application_for, applications, apply_to_demo_employer,
    build_app, change, company, demo, interview, register, resume, save_company, vacancy, verify_employer,
)


def moderator(client):
    response = change(client, "/api/auth/demo", {"role": "moderator"})
    assert response.status_code == 200
    assert response.get_json()["user"]["is_moderator"] is True


def evidence(**updates):
    return {
        "legal_name": "Verdant Labs (Demo)", "country": "MY", "lei": "SYNTHETIC00000000001",
        "domain": "verdant.example.invalid", "recruiter_email": "hr@verdant.example.invalid",
        "registration_number": "SYNTHETIC-REG-2026-01",
        "recruiter_identity": "Synthetic Recruiter / employee-demo-01",
        "evidence_note": "Fictional registration and recruiter check for the hackathon demonstration only.",
        **updates,
    }


@pytest.mark.parametrize("updates", [
    {"salary_min": None}, {"salary_max": None}, {"salary_min": 0},
    {"salary_min": -1}, {"salary_min": True}, {"salary_min": "3500"},
    {"salary_min": float("nan")}, {"salary_max": float("inf")},
    {"salary_min": 6000, "salary_max": 5000}, {"salary_currency": "BTC"},
    {"salary_period": "sometimes"}, {"salary_min": 0.001}, {"salary_min": 10**400},
])
def test_invalid_salary_never_publishes_and_policy_incident_survives_rejection(client, updates):
    demo(client, "hr")
    initial = client.get("/api/workflow/profile").get_json()["company"]["accountability"]
    jobs_before = client.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    response = change(client, "/api/workflow/jobs", vacancy(**updates))
    assert response.status_code == 400
    jobs_after = client.get("/api/workflow/jobs?mine=1").get_json()["jobs"]
    assert len(jobs_after) == len(jobs_before)
    accountability = client.get("/api/workflow/profile").get_json()["company"]["accountability"]
    assert accountability["violations"] == initial["violations"] + 1
    assert accountability["score"] == max(0, initial["score"] - 10)


def test_salary_edit_and_currency_are_returned_with_the_vacancy(client):
    demo(client, "hr")
    verify_employer(client)
    created = change(client, "/api/workflow/jobs", vacancy()).get_json()["job"]
    assert created["salary"] == {"minimum": 3500.0, "maximum": 5500.0, "currency": "MYR", "period": "month", "illustrative": True}
    response = change(client, f"/api/workflow/jobs/{created['id']}", {"salary_min": 4500, "salary_max": 6500, "salary_currency": "SGD", "salary_period": "month"}, method="PATCH")
    assert response.status_code == 200
    assert response.get_json()["job"]["salary_min"] == 4500
    assert response.get_json()["job"]["salary_currency"] == "SGD"


def test_out_of_range_database_identifiers_return_validation_errors(client):
    demo(client, "hr")
    oversized = 2**100
    assert change(client, f"/api/workflow/jobs/{oversized}", {"status": "closed"}, method="PATCH").status_code == 400
    assert change(client, f"/api/workflow/applications/{oversized}/viewed").status_code == 400
    assert change(client, f"/api/workflow/interviews/{oversized}", {"status": "cancelled"}, method="PATCH").status_code == 400
    assert change(client, "/api/workflow/notifications/read", {"ids": [oversized]}, method="PATCH").status_code == 400
    demo(client, "jobseeker")
    assert change(client, "/api/workflow/applications", {"job_id": oversized}).status_code == 400


def test_vacancies_default_to_skills_coverage_and_offer_newest_order(client):
    demo(client, "hr")
    verify_employer(client)
    strongest = change(client, "/api/workflow/jobs", vacancy(title="Exact synthetic skills fit", required_skills=["excel"])).get_json()["job"]
    newest = change(client, "/api/workflow/jobs", vacancy(title="Newest synthetic low fit", required_skills=["sql"])).get_json()["job"]
    change(client, "/api/auth/logout")
    ranked = client.get("/api/workflow/jobs?skills=excel").get_json()["jobs"]
    assert ranked[0]["id"] == strongest["id"]
    assert [item["match"]["percentage"] for item in ranked] == sorted((item["match"]["percentage"] for item in ranked), reverse=True)
    recent = client.get("/api/workflow/jobs?skills=excel&sort=newest").get_json()["jobs"]
    assert recent[0]["id"] == newest["id"]
    assert client.get("/api/workflow/jobs?sort=unrecognised").status_code == 400


def test_company_verification_requires_independent_authorised_review_and_reason(app):
    hr, mod, outsider = (app.test_client() for _ in range(3))
    demo(hr, "hr")
    demo(outsider, "hr")
    moderator(mod)
    company_id = hr.get("/api/workflow/profile").get_json()["company"]["id"]
    assert outsider.get("/api/workflow/moderation").status_code == 403
    submitted = change(hr, "/api/workflow/company/verification", evidence(), method="PUT")
    assert submitted.status_code == 200
    assert submitted.get_json()["company"]["verification"]["status"] == "pending"
    assert change(hr, f"/api/workflow/moderation/companies/{company_id}", {"status": "verified", "reason": "Self approval"}, method="PATCH").status_code == 403
    assert change(mod, f"/api/workflow/moderation/companies/{company_id}", {"status": "verified"}, method="PATCH").status_code == 400
    approved = verify_employer(hr)
    assert approved["verification"]["simulation"] is True
    public = next(item for item in hr.get("/api/workflow/jobs").get_json()["jobs"] if item["company"]["id"] == company_id)
    assert public["company"]["verification"]["status"] == "verified"
    assert "registration_number" not in public["company"]
    assert "recruiter_identity" not in public["company"]
    audit = mod.get("/api/workflow/moderation").get_json()["audit"]
    assert [event["status"] for event in audit if event["company_id"] == company_id][:2] == ["verified", "pending"]
    updated = change(hr, "/api/workflow/profile", company(name="Changed Synthetic Company"), method="PUT")
    assert updated.get_json()["company"]["verification"]["status"] == "unverified"


def test_allowlisted_moderator_cannot_verify_their_own_company(app):
    hr = app.test_client()
    info = demo(hr, "hr")
    app.config["MODERATOR_USER_IDS"] = [info["user"]["id"]]
    submitted = change(hr, "/api/workflow/company/verification", evidence(), method="PUT").get_json()
    company_id = submitted["company"]["id"]
    assert hr.get("/api/workflow/moderation").status_code == 200
    response = change(hr, f"/api/workflow/moderation/companies/{company_id}", {"status": "verified", "reason": "Self review attempt"}, method="PATCH")
    assert response.status_code == 403


def test_moderator_demo_can_be_disabled_and_registration_cannot_claim_moderation(app):
    app.config["ENABLE_MODERATOR_DEMO"] = False
    client = app.test_client()
    assert change(client, "/api/auth/demo", {"role": "moderator"}).status_code == 403
    response = change(client, "/api/auth/register", {"email": "invented-mod@example.invalid", "password": "SyntheticSecret42!", "display_name": "Demo", "role": "moderator"})
    assert response.status_code == 400
    app.config["MODERATOR_EMAILS"] = ["unverified-admin@example.invalid"]
    registered = register(client, "hr", "unverified-admin@example.invalid")
    assert registered["user"]["is_moderator"] is False
    assert client.get("/api/workflow/moderation").status_code == 403


@pytest.mark.parametrize("status", ["accepted", "rejected"])
def test_final_decision_requires_reason_and_preserves_history_and_notifications(app, status):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    path = f"/api/workflow/applications/{submitted['id']}"
    before = learner.get("/api/workflow/updates").get_json()["revision"]
    assert change(hr, path, {"status": status}, method="PATCH").status_code == 400
    assert application_for(applications(learner), submitted["id"])["status"] == "submitted"
    reason = "Synthetic evaluation: strong evidence on the stated requirements." if status == "accepted" else "Synthetic evaluation: SQL evidence is still required."
    response = change(hr, path, {"status": status, "reason": reason}, method="PATCH")
    assert response.status_code == 200
    saved = application_for(applications(learner), submitted["id"])
    assert saved["decision_reason"] == reason
    assert saved["history"][-1]["status"] == status
    assert saved["history"][-1]["reason"] == reason
    assert saved["sla"]["active"] is False
    updates = learner.get("/api/workflow/updates").get_json()
    assert updates["revision"] != before
    assert any(reason in item["title"] for item in updates["notifications"])
    assert change(hr, path, {"status": status, "reason": "Rewritten history"}, method="PATCH").status_code == 409


def test_opening_profile_marks_viewed_once_without_list_get_side_effects(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    path = f"/api/workflow/applications/{submitted['id']}/viewed"
    assert application_for(applications(hr), submitted["id"])["status"] == "submitted"
    assert application_for(applications(learner), submitted["id"])["viewed_at"] is None
    assert change(learner, path).status_code == 403
    assert change(hr, path).status_code == 200
    assert change(hr, path).status_code == 200
    saved = application_for(applications(learner), submitted["id"])
    assert saved["status"] == "viewed"
    assert saved["viewed_at"]
    assert len([event for event in saved["history"] if event["status"] == "viewed"]) == 1
    assert applications(hr)["pending_count"] >= 1


def test_overdue_response_escalates_once_and_notifications_are_owner_scoped(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    with app.extensions["workflow"].connection() as con:
        con.execute("UPDATE applications SET response_due_at=? WHERE id=?", (old, submitted["id"]))
    first = learner.get("/api/workflow/updates").get_json()
    second = learner.get("/api/workflow/updates").get_json()
    assert first["revision"] == second["revision"]
    assert len([item for item in first["notifications"] if item["kind"] == "sla"]) == 1
    saved = application_for(applications(learner), submitted["id"])
    assert saved["sla"]["overdue"] is True and saved["sla"]["escalated"] is True
    assert hr.get("/api/workflow/profile").get_json()["company"]["accountability"]["overdue_applications"] == 1
    own_ids = [item["id"] for item in first["notifications"]]
    assert change(hr, "/api/workflow/notifications/read", {"ids": own_ids}, method="PATCH").status_code == 200
    assert learner.get("/api/workflow/updates").get_json()["unread_count"] == first["unread_count"]
    assert change(learner, "/api/workflow/notifications/read", {"ids": own_ids}, method="PATCH").status_code == 200
    assert learner.get("/api/workflow/updates").get_json()["unread_count"] == 0
    guest = app.test_client()
    assert guest.get("/api/workflow/updates").status_code == 401


def test_interview_can_generate_unique_join_link_and_in_app_invitation(app):
    learner, hr, submitted, _ = apply_to_demo_employer(app)
    result = change(hr, f"/api/workflow/applications/{submitted['id']}/interview", interview(meeting_url="", generate_link=True))
    assert result.status_code == 200
    booking = result.get_json()["application"]["interview"]
    prefix = "https://meet.jit.si/NextStep-Synthetic-"
    assert booking["meeting_url"].startswith(prefix)
    assert len(booking["meeting_url"].removeprefix(prefix)) >= 20
    notifications = learner.get("/api/workflow/updates").get_json()["notifications"]
    assert any("interview invitation" in item["title"] for item in notifications)


def test_additive_migration_preserves_accounts_and_hides_unpaid_legacy_vacancies(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    first = build_app(database)
    hr = first.test_client()
    demo(hr, "hr")
    verify_employer(hr)
    created = change(hr, "/api/workflow/jobs", vacancy()).get_json()["job"]
    with sqlite3.connect(database) as con:
        con.execute("UPDATE jobs SET salary_min=NULL,salary_max=NULL,salary_currency=NULL,salary_period=NULL WHERE id=?", (created["id"],))
    second = build_app(database)
    second_hr = second.test_client()
    demo(second_hr, "hr")
    own = next(item for item in second_hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"] if item["id"] == created["id"])
    assert own["status"] == "closed" and own["salary_min"] is None
    assert created["id"] not in {item["id"] for item in second_hr.get("/api/workflow/jobs").get_json()["jobs"]}
    count = second_hr.get("/api/workflow/profile").get_json()["company"]["accountability"]["violations"]
    third = build_app(database)
    third_hr = third.test_client()
    demo(third_hr, "hr")
    assert third_hr.get("/api/workflow/profile").get_json()["company"]["accountability"]["violations"] == count


def test_original_schema_is_upgraded_without_resetting_resume_or_decision(tmp_path):
    database = tmp_path / "original-schema.sqlite3"
    current = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    deadline = (datetime.now(timezone.utc) + timedelta(days=20)).date().isoformat()
    snapshot = resume()
    with sqlite3.connect(database) as con:
        con.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password_hash TEXT,display_name TEXT,role TEXT,onboarding_complete INTEGER,resume_json TEXT,profile_version INTEGER,demo_key TEXT UNIQUE);
            CREATE TABLE companies(id INTEGER PRIMARY KEY,owner_id INTEGER UNIQUE,name TEXT,industry TEXT,location TEXT,description TEXT DEFAULT '',website TEXT DEFAULT '',synthetic INTEGER DEFAULT 1);
            CREATE TABLE jobs(id INTEGER PRIMARY KEY,company_id INTEGER,title TEXT,role_id TEXT,description TEXT,location TEXT,work_mode TEXT,employment_type TEXT,required_skills_json TEXT,deadline TEXT,status TEXT DEFAULT 'open',created_at TEXT);
            CREATE TABLE applications(id INTEGER PRIMARY KEY,job_id INTEGER,applicant_id INTEGER,resume_json TEXT,resume_version INTEGER,status TEXT DEFAULT 'submitted',created_at TEXT,updated_at TEXT,UNIQUE(job_id,applicant_id));
            CREATE TABLE interviews(id INTEGER PRIMARY KEY,application_id INTEGER UNIQUE,start TEXT,end TEXT,meeting_url TEXT,notes TEXT DEFAULT '',status TEXT DEFAULT 'scheduled');
        """)
        con.execute("INSERT INTO users VALUES(1,'old-candidate@example.invalid','unused','Original Candidate','jobseeker',1,?,1,'jobseeker')", (json.dumps(snapshot),))
        con.execute("INSERT INTO users VALUES(2,'old-hr@example.invalid','unused','Original HR','hr',1,NULL,0,'hr')")
        con.execute("INSERT INTO companies VALUES(1,2,'Original Synthetic Employer','Technology','Penang','','',1)")
        con.execute("INSERT INTO jobs VALUES(1,1,'Original Vacancy','business-intelligence-analyst','Employer-entered synthetic vacancy','Penang','hybrid','full-time','[\"excel\"]',?,'open',?)", (deadline, current))
        con.execute("INSERT INTO applications VALUES(1,1,1,?,1,'accepted',?,?)", (json.dumps(snapshot), current, current))
    app = build_app(database)
    client = app.test_client()
    demo(client, "jobseeker")
    assert client.get("/api/workflow/profile").get_json()["resume"] == snapshot
    saved = applications(client)["applications"][0]
    assert saved["status"] == "accepted"
    assert saved["applicant"]["resume"] == snapshot
    assert "Imported current state" in saved["history"][0]["reason"]
    assert saved["job"]["status"] == "closed"
    assert client.get("/api/workflow/jobs").get_json()["jobs"] == []
