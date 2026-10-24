"""Trust checks exercise fictional identities and isolated databases only."""

from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from career import workflow
from career.verification import check_registry
from test_workflow import (
    app, client, build_app, change, company, demo, register, save_company,
    vacancy, verify_employer,
)


@pytest.fixture
def employer(client):
    demo(client, "hr")
    return client


@pytest.fixture
def moderator(app):
    person = app.test_client()
    demo(person, "moderator")
    return person


def evidence(client, **updates):
    fixture = client.get("/api/workflow/verification/capabilities").get_json()["fixture"]
    return {**fixture, **updates}


def submit(client, **updates):
    response = change(client, "/api/workflow/company/verification", evidence(client, **updates), method="PUT")
    assert response.status_code == 200, response.get_json()
    return response.get_json()["company"]


def challenge(client, submitted):
    token = submitted["verification"]["domain_challenge"]["token"]
    return change(client, "/api/workflow/company/verification/challenge", {"token": token})


def review_payload(**updates):
    return {
        "status": "verified", "reason": "Independent review of the fictional employer and representative completed.",
        "registration_confirmed": True, "domain_control_confirmed": True,
        "recruiter_authorization_confirmed": True,
        "authorization_reference": "https://verdant.example.invalid/team",
        "authorization_note": "Reviewed fictional employer authorization reference and the explicit DNS simulation.",
        **updates,
    }


def review(moderator, company_id, **updates):
    return change(moderator, f"/api/workflow/moderation/companies/{company_id}", review_payload(**updates), method="PATCH")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def test_default_public_mode_and_publishing_policy_are_honest(employer):
    capabilities = employer.get("/api/workflow/verification/capabilities").get_json()
    assert capabilities["mode"] == "synthetic"
    assert capabilities["simulation"] is True
    assert capabilities["publishing_requires_verification"] is True
    assert any("not Malaysia's SSM" in item for item in capabilities["limitations"])
    assert employer.get("/api/workflow/jobs").get_json()["jobs"]  # Keep legacy synthetic browsing.
    denied = change(employer, "/api/workflow/jobs", vacancy())
    assert denied.status_code == 409
    assert "registry" in denied.get_json()["error"]


def test_submission_does_not_approve_registry_or_domain_automatically(employer, moderator):
    pending = submit(employer)
    trust = pending["verification"]
    assert trust["status"] == "pending" and trust["can_publish"] is False
    assert trust["checks"] == {"registry": "matched", "domain": "unchecked", "moderator": "pending"}
    assert review(moderator, pending["id"]).status_code == 409
    assert challenge(employer, pending).get_json()["company"]["verification"]["checks"]["domain"] == "matched"
    approved = review(moderator, pending["id"])
    assert approved.status_code == 200
    trust = approved.get_json()["company"]["verification"]
    assert trust["status"] == "verified" and trust["can_publish"] is True
    assert trust["label"] == "Synthetic checks complete" and trust["simulation"] is True
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 201


@pytest.mark.parametrize("claims", [
    {"legal_name": "Unrelated Fictional Employer"}, {"country": "SG"},
    {"registration_number": "SYNTHETIC-FAKE-REFERENCE"}, {"lei": "SYNTHETIC00000000002"},
])
def test_registry_compares_fixed_independent_record_and_cannot_be_overridden(employer, moderator, claims):
    pending = submit(employer, **claims)
    assert pending["verification"]["checks"]["registry"] == "mismatch"
    assert pending["verification"]["registry_snapshot"]["record"]["legal_name"] == "Verdant Labs (Demo)"
    assert challenge(employer, pending).status_code == 200
    assert review(moderator, pending["id"]).status_code == 409


def test_unavailable_registry_never_falls_back_to_a_verified_badge(employer, moderator, monkeypatch):
    def unavailable(claims, **kwargs):
        snapshot = check_registry(claims, **kwargs)
        snapshot.update(status="unavailable", record=None, matches={}, error="Public provider unavailable.")
        snapshot.pop("sha256")
        snapshot["sha256"] = digest(snapshot)
        return snapshot
    monkeypatch.setattr(workflow, "check_registry", unavailable)
    pending = submit(employer)
    assert pending["verification"]["checks"]["registry"] == "unavailable"
    assert "unavailable" in pending["verification"]["reason"]
    assert challenge(employer, pending).status_code == 200
    assert review(moderator, pending["id"]).status_code == 409
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 409


@pytest.mark.parametrize("field,value", [
    ("registration_confirmed", False), ("domain_control_confirmed", 1),
    ("recruiter_authorization_confirmed", "true"),
    ("authorization_reference", "https://unrelated.example.invalid/team"),
    ("authorization_reference", "https://verdant.example.invalid@attacker.example.invalid/"),
    ("authorization_note", "Trust me"), ("reason", ""),
])
def test_moderator_must_document_each_independent_check(employer, moderator, field, value):
    pending = submit(employer)
    assert challenge(employer, pending).status_code == 200
    assert review(moderator, pending["id"], **{field: value}).status_code == 400
    assert employer.get("/api/workflow/profile").get_json()["company"]["verification"]["status"] == "pending"


def test_domain_challenge_is_exact_bound_and_expires(app, employer, moderator, monkeypatch):
    pending = submit(employer)
    assert change(employer, "/api/workflow/company/verification/challenge", {"token": "incorrect-token"}).status_code == 400
    original = workflow._now()
    monkeypatch.setattr(workflow, "_now", lambda: original + timedelta(minutes=31))
    assert challenge(employer, pending).status_code == 409
    renewed = submit(employer)
    assert renewed["verification"]["domain_challenge"]["token"] != pending["verification"]["domain_challenge"]["token"]
    assert challenge(employer, renewed).status_code == 200
    assert review(moderator, pending["id"]).status_code == 200


def test_synthetic_domain_provider_does_not_echo_unrelated_domain_claim(employer, moderator):
    pending = submit(employer, domain="other.example.invalid", recruiter_email="hr@other.example.invalid")
    checked = challenge(employer, pending)
    assert checked.get_json()["company"]["verification"]["checks"]["domain"] == "missing"
    assert review(moderator, pending["id"]).status_code == 409


def test_public_trust_summary_hides_private_claims_tokens_and_review(app, employer):
    company = verify_employer(employer)
    public = next(item["company"] for item in employer.get("/api/workflow/jobs").get_json()["jobs"] if item["company"]["id"] == company["id"])
    assert public["verification"]["can_publish"] is True
    serialized = json.dumps(public)
    for secret in ("recruiter_email", "domain_challenge", "registry_snapshot", "authorization_reference", "authorization_note", "owner_id"):
        assert secret not in serialized
    source = public["verification"]["registry_source"]
    assert source["record"]["legal_name"] == "Verdant Labs (Demo)"
    assert source["record"]["registration_number"] == "SYNTHETIC-REG-2026-01"
    assert source["source_url"].startswith("synthetic://")
    assert source["checked_at"] and source["expires_at"] and source["sha256"]
    with app.extensions["workflow"].connection() as con:
        events = con.execute("SELECT * FROM verification_evidence_events WHERE company_id=? ORDER BY id", (company["id"],)).fetchall()
    assert [event["kind"] for event in events] == ["submission", "domain_check", "moderator_review"]
    for event in events:
        assert event["sha256"] == hashlib.sha256(event["payload_json"].encode()).hexdigest()
    assert "sha256" in json.loads(events[0]["payload_json"])["registry"]


def test_expired_approval_cannot_publish_or_reopen(app, employer, monkeypatch):
    approved = verify_employer(employer)
    created = change(employer, "/api/workflow/jobs", vacancy(deadline=(datetime.now(timezone.utc) + timedelta(days=60)).date().isoformat())).get_json()["job"]
    assert change(employer, f"/api/workflow/jobs/{created['id']}", {"status": "closed"}, method="PATCH").status_code == 200
    future = workflow._now() + timedelta(days=31)
    monkeypatch.setattr(workflow, "_now", lambda: future)
    trust = employer.get("/api/workflow/profile").get_json()["company"]["verification"]
    assert trust["status"] == "expired" and trust["can_publish"] is False
    assert change(employer, "/api/workflow/jobs", vacancy(deadline=(future + timedelta(days=20)).date().isoformat())).status_code == 409
    assert change(employer, f"/api/workflow/jobs/{created['id']}", {"status": "open"}, method="PATCH").status_code == 409
    assert approved["verification"]["expires_at"]


def test_provider_mode_changes_invalidate_existing_approval(app, employer):
    verify_employer(employer)
    app.config["EMPLOYER_VERIFICATION_MODE"] = "gleif"
    trust = employer.get("/api/workflow/profile").get_json()["company"]["verification"]
    assert trust["status"] == "unverified" and trust["can_publish"] is False
    assert trust["checks"]["registry"] == "unchecked"
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 409


def test_profile_changes_invalidate_active_checks_preserving_evidence_history(app, employer, moderator):
    approved = verify_employer(employer)
    updated = save_company(employer, name="Changed Synthetic Employer")
    trust = updated["company"]["verification"]
    assert trust["status"] == "unverified" and trust["can_publish"] is False
    assert not trust["registry_snapshot"] and not trust["domain_challenge"]
    assert review(moderator, approved["id"]).status_code == 409
    with app.extensions["workflow"].connection() as con:
        kinds = [row["kind"] for row in con.execute("SELECT kind FROM verification_evidence_events WHERE company_id=?", (approved["id"],))]
    assert kinds == ["submission", "domain_check", "moderator_review", "profile_changed"]


def test_recheck_requires_independent_reapproval_and_revocation_stops_publishing(employer, moderator):
    approved = verify_employer(employer)
    rechecked = change(employer, "/api/workflow/company/verification/recheck")
    trust = rechecked.get_json()["company"]["verification"]
    assert trust["status"] == "pending" and trust["can_publish"] is False and not trust["review"]
    assert review(moderator, approved["id"]).status_code == 200
    revoked = review(moderator, approved["id"], status="revoked", reason="Synthetic authorization withdrawn after independent review.")
    assert revoked.status_code == 200
    assert revoked.get_json()["company"]["verification"]["status"] == "revoked"
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 409


def test_legal_entity_cannot_be_approved_under_two_owners_without_transfer(app, employer, moderator):
    first = verify_employer(employer)
    other = app.test_client()
    register(other, "hr", "another-hr@example.invalid")
    save_company(other)
    pending = submit(other)
    assert challenge(other, pending).status_code == 200
    conflict = review(moderator, pending["id"])
    assert conflict.status_code == 409 and "another company account" in conflict.get_json()["error"]
    assert review(moderator, first["id"], status="revoked", reason="Independent reviewer approved a fictional account transfer.").status_code == 200
    assert review(moderator, pending["id"]).status_code == 200
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 409


def test_tampered_snapshot_checksum_cannot_keep_or_receive_approval(app, employer, moderator):
    approved = verify_employer(employer)
    with app.extensions["workflow"].connection() as con:
        snapshot = json.loads(con.execute("SELECT registry_snapshot_json FROM companies WHERE id=?", (approved["id"],)).fetchone()[0])
        snapshot["record"]["legal_name"] = "Tampered record"
        con.execute("UPDATE companies SET registry_snapshot_json=? WHERE id=?", (json.dumps(snapshot), approved["id"]))
    assert employer.get("/api/workflow/profile").get_json()["company"]["verification"]["can_publish"] is False
    assert change(employer, "/api/workflow/jobs", vacancy()).status_code == 409


def test_legacy_text_only_badge_is_invalidated_once_without_erasing_accounts(tmp_path):
    database = tmp_path / "older.sqlite3"
    first = build_app(database)
    employer = first.test_client()
    demo(employer, "hr")
    original = employer.get("/api/workflow/profile").get_json()["company"]
    with first.extensions["workflow"].connection() as con:
        con.execute("UPDATE companies SET verification_status='verified',verification_mode='',registration_number='OLD-SYNTHETIC-REF',evidence_note='Original retained fictional evidence.' WHERE id=?", (original["id"],))
    second = build_app(database)
    owner = second.test_client()
    demo(owner, "hr")
    migrated = owner.get("/api/workflow/profile").get_json()["company"]
    assert migrated["id"] == original["id"] and migrated["name"] == original["name"]
    assert migrated["registration_number"] == "OLD-SYNTHETIC-REF"
    assert migrated["verification"]["status"] == "unverified"
    third = build_app(database)
    with third.extensions["workflow"].connection() as con:
        assert con.execute("SELECT COUNT(*) FROM verification_audit WHERE company_id=?", (original["id"],)).fetchone()[0] == 1


@pytest.mark.parametrize("path,method", [
    ("/api/workflow/company/verification", "PUT"),
    ("/api/workflow/company/verification/challenge", "POST"),
    ("/api/workflow/company/verification/recheck", "POST"),
])
def test_new_verification_mutations_require_csrf_and_authentication(client, path, method):
    assert client.open(path, method=method, json={}).status_code == 403
    assert change(client, path, {}, method=method).status_code == 401


def test_real_individual_email_and_unknown_provider_never_trigger_lookup(employer, app, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid or personal evidence must not trigger a provider request")
    monkeypatch.setattr(workflow, "check_registry", unexpected)
    response = change(employer, "/api/workflow/company/verification", evidence(employer, recruiter_email="real.person@real-employer.com"), method="PUT")
    assert response.status_code == 400
    app.config["EMPLOYER_VERIFICATION_MODE"] = ["arbitrary"]
    assert employer.get("/api/workflow/verification/capabilities").status_code == 503
