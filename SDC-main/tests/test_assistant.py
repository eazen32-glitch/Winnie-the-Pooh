"""Guided advice stays tied to catalogue facts, source evidence and user intent."""

from copy import deepcopy

import pytest

from career.assistant import build_reply, role_exposure
from career.catalog import PROFILES, ROLES, SKILLS
from career.exposure import build_exposure_evidence
from career.recommendations import match_profile


@pytest.fixture
def snapshot():
    return {
        "jobs": [{"id": "synthetic-job", "title": "Data Analyst", "company": "Synthetic test employer", "description": "Data analytics", "posted_at": "2026-10-15T12:00:00Z", "url": "https://example.org/test-job", "active": True}],
        "ai_updates": [],
        "signal_status": {"status": "cached", "fetched_at": "2026-10-22T00:00:00Z", "source_name": "Synthetic test feed", "source_url": "https://example.org/feed", "windows": {"recent_start": "2026-09-23", "recent_end": "2026-10-23", "previous_start": "2026-08-24", "previous_end": "2026-09-23"}},
    }


def profile():
    return {**deepcopy(PROFILES[0]), "scenario": "moderate"}


@pytest.mark.parametrize("scenario", ["moderate", "fast"])
@pytest.mark.parametrize("role", ROLES, ids=lambda role: role["id"])
def test_exposure_is_qualitative_and_role_grounded(role, scenario):
    response = role_exposure(role["id"], scenario)
    assert response["level"] in {"low", "moderate", "high"}
    assert response["scenario"] == scenario
    assert response["source_url"] == role["source_url"]
    assert len(response["task_examples"]) >= 2
    assert len(response["human_strengths"]) >= 2
    assert "not the probability" in response["summary"]
    assert "editorial" in response["method"].lower()
    assert "percent" not in response and "probability" not in response
    assert response["research_evidence"] == build_exposure_evidence(role["id"])


@pytest.mark.parametrize("role_id,scenario", [("imaginary-job", "moderate"), ("data-scientist", "certain")])
def test_exposure_rejects_unknown_inputs(role_id, scenario):
    with pytest.raises(ValueError):
        role_exposure(role_id, scenario)


def test_editable_task_index_reports_formula_and_sensitivity_without_probability():
    initial = role_exposure("software-developer", "moderate")
    assumptions = {task["id"]: 100 if index < 3 else 0 for index, task in enumerate(initial["task_assessment"]["tasks"])}
    response = role_exposure("software-developer", "moderate", assumptions)
    assessment = response["task_assessment"]
    assert assessment["percentage"] == 50
    assert assessment["customised"] is True
    assert assessment["sensitivity_band"] == {"lower": 42.5, "upper": 57.5, "assumption_shift_points": 15}
    assert "divided by six" in assessment["formula"]
    assert "not a confidence interval" in assessment["uncertainty"]
    assert "not a job-replacement probability" in assessment["scope"]
    assert initial["task_assessment"]["percentage"] != assessment["percentage"]


@pytest.mark.parametrize("assumptions", [[], {"invented-task": 40}, {"routine-1": True}, {"routine-1": -1}, {"routine-1": 101}, {"routine-1": 10 ** 500}, {"routine-1": float("nan")}, {"routine-1": float("inf")}, {"routine-1": "60"}])
def test_task_index_rejects_invented_or_invalid_assumptions(assumptions):
    with pytest.raises(ValueError):
        role_exposure("software-developer", task_assumptions=assumptions)


def test_partial_task_edit_preserves_other_defaults_and_does_not_mutate_input():
    assumptions = {"routine-1": 33.3}
    before = deepcopy(assumptions)
    edited = role_exposure("software-developer", "fast", assumptions)["task_assessment"]
    defaults = role_exposure("software-developer", "fast")["task_assessment"]
    assert assumptions == before
    assert edited["tasks"][0]["assistance_percent"] == 33.3
    assert edited["tasks"][1:] == defaults["tasks"][1:]


@pytest.mark.parametrize("role", ROLES, ids=lambda role: role["id"])
def test_published_measure_is_unchanged_by_authored_scenarios_and_task_edits(role):
    baseline = role_exposure(role["id"], "moderate")
    fast = role_exposure(role["id"], "fast")
    custom = role_exposure(role["id"], "fast", {task["id"]: 100 for task in fast["task_assessment"]["tasks"]})
    assert baseline["research_evidence"] == fast["research_evidence"] == custom["research_evidence"]
    assert custom["task_assessment"]["percentage"] == 100
    assert baseline["task_assessment"]["percentage"] != custom["task_assessment"]["percentage"]


@pytest.mark.parametrize("role_id", ["business-intelligence-analyst", "project-management-specialist"])
def test_unmapped_research_is_unavailable_while_authored_calculator_still_works(role_id):
    response = role_exposure(role_id)
    research = response["research_evidence"]
    assert research["status"] == "unavailable"
    assert research["metric"] is None
    assert research["unavailable_reason"]
    assert response["task_assessment"]["percentage"] > 0


@pytest.mark.parametrize("question,view,expected", [
    ("How do salary ranges work?", "jobs", "base salary"),
    ("Is this company verified?", "jobs", "not a real company-registry"),
    ("How do I send messages?", "messages", "private, role-scoped"),
    ("What if an application is overdue?", "applications", "response deadline"),
])
def test_new_workflow_guidance_is_actionable_and_honest(snapshot, question, view, expected):
    response = build_reply(question, profile(), snapshot, actor_role="jobseeker")
    assert expected in response["answer"]
    assert any(action["view"] == view for action in response["actions"])


def test_gap_reply_uses_selected_role_and_its_real_gaps(snapshot):
    person = profile()
    selected = "business-intelligence-analyst"
    result = build_reply("What skills am I lacking?", person, snapshot, role_id=selected)
    match = next(match for match in match_profile(person, snapshot)["matches"] if match["id"] == selected)
    assert match["title"] in result["answer"]
    assert all(skill["name"] in result["answer"] for skill in match["missing_skills"])
    assert result["sources"]
    assert "2026-10-22" in result["answer"]
    assert any(action.get("role_id") == selected for action in result["actions"])


def test_catalogue_role_named_in_question_is_resolved(snapshot):
    result = build_reply("What skills do I lack for Data Scientist?", profile(), snapshot)
    assert "For Data Scientist" in result["answer"]
    assert any(action.get("role_id") == "data-scientist" for action in result["actions"])


def test_named_role_overrides_current_pathway_selection(snapshot):
    result = build_reply("What skills do I lack for Data Scientist?", profile(), snapshot, role_id="project-management-specialist")
    assert "For Data Scientist" in result["answer"]


def test_named_role_without_specific_question_gets_role_context(snapshot):
    result = build_reply("Tell me about Sustainability Specialist", profile(), snapshot)
    assert result["answer"].startswith("Sustainability Specialist:")
    assert any(action.get("role_id") == "sustainability-specialist" for action in result["actions"])


def test_suggestions_are_catalogue_roles_and_not_hiring_promises(snapshot):
    result = build_reply("Suggest jobs", profile(), snapshot)
    expected = match_profile(profile(), snapshot)["matches"][:3]
    assert all(match["title"] in result["answer"] for match in expected)
    assert "not hiring probabilities" in result["answer"]
    assert "no language model" in result["method"]


def test_learning_reply_has_real_resources_and_introduction_budget(snapshot):
    result = build_reply("Plan my learning", profile(), snapshot, role_id="data-scientist")
    known_urls = {resource["url"] for skill in SKILLS for resource in skill["resources"]}
    assert any(source["url"] in known_urls for source in result["sources"])
    assert "6 hours/week" in result["answer"]
    assert "introductory study hours" in result["answer"]
    assert "not a promise" in result["answer"]
    assert result["actions"][0]["view"] == "pathway"


def test_exposure_reply_does_not_invent_replacement_percentage(snapshot):
    result = build_reply("What is my AI replacement percentage?", profile(), snapshot, role_id="software-developer")
    assert "cannot give a validated job-replacement percentage" in result["answer"]
    assert "Human strengths" in result["answer"]
    assert not any(character == "%" for character in result["answer"])
    assert any("onetonline.org" in source["url"] for source in result["sources"])
    research = result["research_evidence"]
    assert research["source"]["url"] in {source["url"] for source in result["sources"]}
    assert "53/100" in result["answer"]
    assert "broader occupation proxy" in result["answer"]
    assert "2025" in result["answer"]
    assert research["scope"]["time_horizon"] in result["answer"]
    assert "does not change the published study measure" in result["answer"]
    assert "Next reskilling steps" in result["answer"]
    known_resources = {resource["url"] for skill in SKILLS for resource in skill["resources"]}
    assert any(source["url"] in known_resources for source in result["sources"])


@pytest.mark.parametrize("alias,role_id", [("software engineer", "software-developer"), ("software engineers", "software-developer"), ("data analyst", "business-intelligence-analyst"), ("project manager", "project-management-specialist")])
def test_exposure_question_resolves_known_alias_and_does_not_reuse_selected_role(snapshot, alias, role_id):
    result = build_reply(f"What is the AI replacement percentage for a {alias}?", profile(), snapshot, role_id="data-scientist")
    assert result["research_evidence"]["role_id"] == role_id
    assert result["actions"][0]["role_id"] == role_id


def test_unavailable_occupation_mapping_is_not_reported_as_zero_or_neighbour_score(snapshot):
    result = build_reply("What is AI replacement exposure for a project manager?", profile(), snapshot)
    assert result["research_evidence"]["metric"] is None
    assert "Published exposure measure: unavailable" in result["answer"]
    assert "No percentage is inferred" in result["answer"]
    assert "/100" not in result["answer"]


def test_personal_job_loss_question_explains_why_study_index_is_not_personal_forecast(snapshot):
    result = build_reply("Will I lose my job to AI?", profile(), snapshot, role_id="software-developer")
    assert result["research_evidence"]["role_id"] == "software-developer"
    assert "personal job-loss probability" in result["answer"]
    assert "53/100" in result["answer"]


def test_unknown_requested_occupation_does_not_silently_use_selected_role(snapshot):
    result = build_reply("What is the AI replacement percentage for a nurse?", profile(), snapshot, role_id="software-developer")
    assert "nurse is unavailable in this curated catalogue" in result["answer"]
    assert "Software Developer" not in result["answer"]
    assert "research_evidence" not in result
    assert not any(action.get("role_id") for action in result["actions"])


def test_historical_computerisation_request_keeps_software_suboccupations_separate(snapshot):
    result = build_reply("What is the historical computerisation probability for a software engineer?", profile(), snapshot)
    assert "Historical 2013 computerisation model" in result["answer"]
    assert "Software Developers, Applications" in result["answer"]
    assert "Software Developers, Systems Software" in result["answer"]
    assert "4.2%" in result["answer"] and "13%" in result["answer"]
    assert "not current GenAI replacement percentages" in result["answer"]
    assert "not averaged" in result["answer"]
    historical_sources = result["research_evidence"]["historical_estimates"]
    assert any(source["url"] == historical_sources[0]["source"]["mirror_url"] and source["date"] == "2013" for source in result["sources"])


def test_historical_data_gaps_do_not_borrow_neighbour_occupation_probability(snapshot):
    result = build_reply("Explain historical computerisation risk for a Data Scientist", profile(), snapshot)
    assert "Historical computerisation estimate: unavailable" in result["answer"]
    assert result["research_evidence"]["historical_estimates"] == []
    assert "%" not in result["answer"]


def test_sdg_reply_explains_contribution_and_cites_goal(snapshot):
    result = build_reply("Explain SDGs", profile(), snapshot, role_id="sustainability-specialist")
    assert "resource use" in result["answer"]
    assert "not measure impact" in result["answer"]
    assert any("sdgs.un.org/goals/goal" in source["url"] for source in result["sources"])


def test_hr_guidance_is_actionable_without_hiring_decision(snapshot):
    result = build_reply("Reject applicants", profile(), snapshot, actor_role="hr")
    assert "make your own" in result["answer"]
    assert result["actions"][0]["view"] == "applicants"
    assert "Synthetic test employer" not in result["answer"]


def test_hr_interview_guidance_does_not_pretend_to_send_invites(snapshot):
    result = build_reply("Schedule interviews", profile(), snapshot, actor_role="hr")
    assert "does not create a video room or send an email" in result["answer"]
    assert {action["view"] for action in result["actions"]} == {"applicants", "calendar"}


def test_guest_application_guidance_requires_signin(snapshot):
    result = build_reply("Where are my applications?", profile(), snapshot)
    assert "Sign in" in result["answer"]
    assert all(action["view"] != "applications" for action in result["actions"])


def test_unsupported_question_has_scoped_fallback(snapshot):
    result = build_reply("Tell me tomorrow's weather", profile(), snapshot)
    assert "guided catalogue assistant" in result["answer"]
    assert not result["sources"]


def test_empty_profile_can_explore_without_invented_skills(snapshot):
    result = build_reply("Find my skill gaps", {}, snapshot)
    assert "no selected skills" in result["answer"]
    assert result["sources"]


def test_reply_does_not_mutate_profile_or_source_data(snapshot):
    person = profile()
    before = deepcopy((person, snapshot))
    build_reply("Suggest roles", person, snapshot)
    assert (person, snapshot) == before


@pytest.mark.parametrize("message", ["", "   ", "x" * 1001, None, []])
def test_reply_rejects_invalid_question(message, snapshot):
    with pytest.raises(ValueError):
        build_reply(message, profile(), snapshot)


def test_reply_rejects_invented_role(snapshot):
    with pytest.raises(ValueError):
        build_reply("Suggest jobs", profile(), snapshot, role_id="invented")


@pytest.fixture(scope="module")
def api_app(tmp_path_factory):
    """Exercise the real endpoint boundary with no remote source requests."""
    from app import create_app

    class EmptySource:
        def snapshot(self):
            return {"jobs": [], "ai_updates": [], "signal_status": {"status": "offline"}}

    return create_app({
        "TESTING": True,
        "SECRET_KEY": "synthetic-assistant-test-key",
        "WORKFLOW_DATABASE": str(tmp_path_factory.mktemp("assistant-api") / "workflow.sqlite3"),
        "SOURCE_STORE": EmptySource(),
    })


@pytest.fixture
def api_client(api_app):
    return api_app.test_client()


@pytest.mark.parametrize("payload", [
    {}, {"message": ""}, {"message": "   "}, {"message": 42},
    {"message": "x" * 1001}, {"message": "Suggest roles", "profile": []},
    {"message": "Suggest roles", "role_id": []},
    {"message": "Suggest roles", "role_id": "invented"},
    {"message": "Suggest roles", "scenario": "certain"},
    {"message": "Suggest roles", "profile": {"skills": ["invented"]}},
])
def test_assistant_api_rejects_bad_input(api_client, payload):
    response = api_client.post("/api/assistant", json=payload)
    assert response.status_code == 400
    assert response.json["error"]


def test_assistant_api_rejects_malformed_or_non_object_payload(api_client):
    for body in ["null", "[]", "{bad"]:
        response = api_client.post("/api/assistant", data=body, content_type="application/json")
        assert response.status_code == 400


def test_assistant_api_uses_authenticated_role_not_client_claim(api_client):
    guest = api_client.post("/api/assistant", json={"message": "Review applicants", "role": "hr"})
    assert guest.status_code == 200
    assert not any(action["view"] == "applicants" for action in guest.json["actions"])

    session = api_client.get("/api/auth/session").json
    signed_in = api_client.post("/api/auth/demo", json={"role": "hr"}, headers={"X-CSRF-Token": session["csrf_token"]})
    assert signed_in.status_code == 200
    response = api_client.post("/api/assistant", json={"message": "Review applicants", "role": "guest"})
    assert response.status_code == 200
    assert any(action["view"] == "applicants" for action in response.json["actions"])
    assert "make your own" in response.json["answer"]


def test_exposure_api_returns_qualitative_sourced_context(api_client):
    response = api_client.get("/api/exposure?role_id=software-developer&scenario=fast")
    assert response.status_code == 200
    assert response.json["scenario"] == "fast"
    assert response.json["level"] in {"low", "moderate", "high"}
    assert "onetonline.org" in response.json["source_url"]
    assert "%" not in response.json["summary"]
    assert response.json["human_strengths"]


@pytest.mark.parametrize("query", ["", "role_id=imaginary", "role_id=software-developer&scenario=certain"])
def test_exposure_api_rejects_unknown_role_or_scenario(api_client, query):
    response = api_client.get("/api/exposure?" + query)
    assert response.status_code == 400


def test_task_what_if_api_explains_exact_recalculation(api_client):
    defaults = api_client.get("/api/exposure?role_id=data-scientist").json
    assumptions = {task["id"]: 40 for task in defaults["task_assessment"]["tasks"]}
    response = api_client.post("/api/exposure/what-if", json={"role_id": "data-scientist", "scenario": "fast", "task_assumptions": assumptions})
    assert response.status_code == 200
    assert response.json["task_assessment"]["percentage"] == 40
    assert response.json["task_assessment"]["sensitivity_band"]["lower"] == 25
    assert response.json["task_assessment"]["sensitivity_band"]["upper"] == 55
    assert response.json["research_evidence"] == defaults["research_evidence"]


def test_assistant_api_exposure_uses_published_evidence_and_cites_source(api_client):
    result = api_client.post("/api/assistant", json={"message": "What is the AI replacement percentage for a software engineer?", "role_id": "data-scientist"})
    assert result.status_code == 200
    research = result.json["research_evidence"]
    assert research["role_id"] == "software-developer"
    assert research["metric"]["value"] == 0.53
    assert research["metric"]["is_probability"] is False
    assert research["source"]["url"] in {source["url"] for source in result.json["sources"]}
    assert "validated job-replacement percentage" in result.json["answer"]


@pytest.mark.parametrize("payload", [[], {"role_id": "imaginary"}, {"role_id": []}, {"role_id": "data-scientist", "scenario": "certain"}, {"role_id": "data-scientist", "task_assumptions": {"routine-1": True}}])
def test_task_what_if_api_rejects_unknown_or_invalid_input(api_client, payload):
    assert api_client.post("/api/exposure/what-if", json=payload).status_code == 400


def test_optional_online_assistant_requires_consent_and_session_token(api_client, monkeypatch):
    for name in ("NEXTSTEP_ENABLE_LLM", "NEXTSTEP_OPENAI_API_KEY", "NEXTSTEP_OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    capabilities = api_client.get("/api/assistant/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json["model_available"] is False
    payload = {"message": "Suggest roles", "use_model": True}
    assert api_client.post("/api/assistant", json=payload).status_code == 400
    payload["external_consent"] = True
    assert api_client.post("/api/assistant", json=payload).status_code == 403
    token = api_client.get("/api/auth/session").json["csrf_token"]
    reply = api_client.post("/api/assistant", json=payload, headers={"X-CSRF-Token": token})
    assert reply.status_code == 200
    assert reply.json["model_info"]["status"] == "not_configured"
    assert reply.json["model_info"]["used"] is False


@pytest.mark.parametrize("field,value", [("use_model", "yes"), ("external_consent", 1)])
def test_optional_assistant_api_rejects_non_boolean_preferences(api_client, field, value):
    response = api_client.post("/api/assistant", json={"message": "Suggest roles", field: value})
    assert response.status_code == 400
