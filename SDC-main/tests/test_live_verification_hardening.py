"""Operational live-mode boundaries, exercised with mock public records only."""

from copy import deepcopy
from datetime import timedelta

import pytest

from app import configured_moderator_ids
from career import verification, workflow
from test_verification import challenge, employer, moderator, review, submit
from test_verification_connector import gleif_record, real_claims, synthetic_claims
from test_workflow import app, build_app, change, client, demo


@pytest.mark.parametrize("value", ["admin@example.invalid", "0", "-1", "1,,2", "true", str(2**100)])
def test_moderator_configuration_cannot_promote_an_email_or_invalid_identifier(monkeypatch, value):
    monkeypatch.setenv("NEXTSTEP_MODERATOR_USER_IDS", value)
    with pytest.raises(ValueError):
        configured_moderator_ids()


def test_moderator_configuration_accepts_only_explicit_operator_ids(monkeypatch):
    monkeypatch.setenv("NEXTSTEP_MODERATOR_USER_IDS", "3, 7, 3")
    assert configured_moderator_ids() == [3, 7]
    monkeypatch.delenv("NEXTSTEP_MODERATOR_USER_IDS")
    assert configured_moderator_ids() == []


def test_live_mode_disables_shared_demo_entry_and_existing_demo_privileges(app, moderator):
    moderator_id = moderator.get("/api/auth/session").json["user"]["id"]
    assert moderator.get("/api/workflow/moderation").status_code == 200
    app.config["EMPLOYER_VERIFICATION_MODE"] = "gleif"
    capabilities = moderator.get("/api/workflow/verification/capabilities").json
    assert capabilities["moderator_demo_available"] is False
    assert capabilities["live_check_cooldown_seconds"] == 30
    assert moderator.get("/api/workflow/moderation").status_code == 403
    new_client = app.test_client()
    assert change(new_client, "/api/auth/demo", {"role": "moderator"}).status_code == 403
    app.config["MODERATOR_USER_IDS"] = [moderator_id]
    assert moderator.get("/api/workflow/moderation").status_code == 200
    # An operator allowlist does not reopen the anonymous demo entry point.
    assert change(new_client, "/api/auth/demo", {"role": "moderator"}).status_code == 403


def test_live_registry_cooldown_is_persistent_and_expires(app, employer, real_claims, gleif_record, monkeypatch):
    calls = []

    def fetch(*args):
        calls.append(args)
        return deepcopy(gleif_record)

    monkeypatch.setattr(verification, "_fetch_json", fetch)
    app.config["EMPLOYER_VERIFICATION_MODE"] = "gleif"
    endpoint = "/api/workflow/company/verification"
    assert change(employer, endpoint, real_claims, method="PUT").status_code == 200
    assert change(employer, endpoint, real_claims, method="PUT").status_code == 429
    assert change(employer, endpoint + "/recheck").status_code == 429
    restarted = build_app(app.config["WORKFLOW_DATABASE"])
    restarted.config["EMPLOYER_VERIFICATION_MODE"] = "gleif"
    owner_again = restarted.test_client()
    demo(owner_again, "hr")
    assert change(owner_again, endpoint, real_claims, method="PUT").status_code == 429
    assert len(calls) == 1
    later = workflow._now() + timedelta(seconds=31)
    monkeypatch.setattr(workflow, "_now", lambda: later)
    assert change(owner_again, endpoint, real_claims, method="PUT").status_code == 200
    assert len(calls) == 2


def test_a_provider_response_cannot_overwrite_a_newer_review(app, employer, real_claims, gleif_record, monkeypatch):
    company_id = employer.get("/api/workflow/profile").json["company"]["id"]
    app.config["EMPLOYER_VERIFICATION_MODE"] = "gleif"

    def changed_while_request_was_pending(*args):
        with app.extensions["workflow"].connection() as connection:
            connection.execute("UPDATE companies SET verification_status='revoked',verification_reason=? WHERE id=?", ("Synthetic authorization revoked while the provider was pending.", company_id))
        return deepcopy(gleif_record)

    monkeypatch.setattr(verification, "_fetch_json", changed_while_request_was_pending)
    result = change(employer, "/api/workflow/company/verification", real_claims, method="PUT")
    assert result.status_code == 409
    owner = employer.get("/api/workflow/profile").json["company"]["verification"]
    assert owner["status"] == "revoked"
    assert owner["can_publish"] is False
    assert owner["registry_snapshot"] == {}


def test_private_review_reasons_are_not_embedded_in_public_job_cards(app, employer, moderator):
    pending = submit(employer)
    assert challenge(employer, pending).status_code == 200
    marker = "SYNTHETIC_PRIVATE_REVIEW_DETAIL_FOR_OWNER_ONLY"
    assert review(moderator, pending["id"], reason=marker).status_code == 200
    private = employer.get("/api/workflow/profile").json["company"]["verification"]
    assert private["reason"] == marker
    public = app.test_client().get("/api/workflow/jobs")
    assert public.status_code == 200
    assert marker not in public.get_data(as_text=True)
    company = next(item["company"] for item in public.json["jobs"] if item["company"]["id"] == pending["id"])
    assert company["verification"]["reason"] == ""
    assert company["verification"]["registry_source"]["record"]["legal_name"] == "Verdant Labs (Demo)"
