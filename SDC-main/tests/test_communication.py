"""Synthetic private messaging: ownership, CSRF, unread state and retry safety."""

import pytest
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from career.communication import communication_bp, init_communication
from career.workflow import init_workflow, workflow_bp


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="synthetic-messaging-test", WORKFLOW_DATABASE=str(tmp_path / "messages.sqlite3"))
    init_workflow(app)
    app.register_blueprint(workflow_bp)
    init_communication(app)
    app.register_blueprint(communication_bp)

    @app.errorhandler(HTTPException)
    def error(exception):
        return jsonify(error=exception.description), exception.code

    return app


def change(client, path, payload=None):
    csrf = client.get("/api/auth/session").get_json()["csrf_token"]
    return client.post(path, json=payload or {}, headers={"X-CSRF-Token": csrf})


def login(client, role):
    response = change(client, "/api/auth/demo", {"role": role})
    assert response.status_code == 200


def new_candidate(app):
    client = app.test_client()
    response = change(client, "/api/auth/register", {"role": "jobseeker", "display_name": "Another Synthetic Candidate", "email": "another@example.invalid", "password": "SyntheticPassphrase123!"})
    assert response.status_code == 201
    return client


@pytest.fixture
def people(app):
    candidate, hr = app.test_client(), app.test_client()
    login(candidate, "jobseeker")
    login(hr, "hr")
    job = hr.get("/api/workflow/jobs?mine=1").get_json()["jobs"][0]
    created = change(candidate, "/api/messages/threads", {"job_id": job["id"]})
    assert created.status_code == 201, created.get_json()
    return candidate, hr, job, created.get_json()["thread"]["id"]


def send(client, identifier, body="A synthetic question", **extra):
    return change(client, f"/api/messages/threads/{identifier}/messages", {"body": body, **extra})


def test_candidate_can_contact_hr_before_applying_and_hr_can_reply(people):
    candidate, hr, job, identifier = people
    assert send(candidate, identifier, "Which skills should I practise?").status_code == 201
    inbox = hr.get("/api/messages/threads").get_json()
    assert inbox["unread_count"] == 1
    assert inbox["threads"][0]["job_id"] == job["id"]
    assert send(hr, identifier, "Start with SQL and communication.").status_code == 201
    data = candidate.get(f"/api/messages/threads/{identifier}/messages").get_json()
    assert [item["mine"] for item in data["messages"]] == [True, False]
    assert data["messages"][1]["body"] == "Start with SQL and communication."
    assert "email" not in data["thread"]["candidate"]


def test_duplicate_thread_is_same_conversation(people):
    candidate, hr, job, identifier = people
    response = change(candidate, "/api/messages/threads", {"job_id": job["id"]})
    assert response.status_code == 200
    assert response.get_json()["thread"]["id"] == identifier
    assert len(hr.get("/api/messages/threads").get_json()["threads"]) == 1


def test_hr_can_start_thread_only_from_owned_application(app):
    hr = app.test_client()
    login(hr, "hr")
    application = hr.get("/api/workflow/applications").get_json()["applications"][0]
    response = change(hr, "/api/messages/threads", {"application_id": application["id"]})
    assert response.status_code == 201
    foreign = new_candidate(app)
    identifier = response.get_json()["thread"]["id"]
    assert foreign.get(f"/api/messages/threads/{identifier}/messages").status_code == 404
    assert change(hr, "/api/messages/threads", {"application_id": 999999}).status_code == 404


def test_candidate_can_open_chat_from_own_application(app):
    candidate = app.test_client()
    login(candidate, "jobseeker")
    application = candidate.get("/api/workflow/applications").get_json()["applications"][0]
    response = change(candidate, "/api/messages/threads", {"application_id": application["id"]})
    assert response.status_code == 201
    assert response.get_json()["thread"]["job_id"] == application["job"]["id"]
    other = new_candidate(app)
    assert change(other, "/api/messages/threads", {"application_id": application["id"]}).status_code == 404


def test_closed_job_blocks_new_enquiry_but_preserves_existing_thread(people, app):
    candidate, hr, job, identifier = people
    with app.extensions["workflow"].connection() as con:
        con.execute("UPDATE jobs SET status='closed' WHERE id=?", (job["id"],))
    assert change(candidate, "/api/messages/threads", {"job_id": job["id"]}).status_code == 200
    assert send(candidate, identifier).status_code == 201
    other = new_candidate(app)
    assert change(other, "/api/messages/threads", {"job_id": job["id"]}).status_code == 409


@pytest.mark.parametrize("method,path,payload", [
    ("GET", "/api/messages/threads", None),
    ("GET", "/api/messages/threads/1/messages", None),
    ("POST", "/api/messages/threads", {"job_id": 1}),
    ("POST", "/api/messages/threads/1/messages", {"body": "hello"}),
    ("POST", "/api/messages/threads/1/read", {"through_id": 0}),
])
def test_guests_cannot_access_messaging(app, method, path, payload):
    client = app.test_client()
    response = client.get(path) if method == "GET" else change(client, path, payload)
    assert response.status_code == 401


def test_another_candidate_cannot_read_send_or_acknowledge(people, app):
    candidate, hr, _, identifier = people
    send(hr, identifier)
    outsider = new_candidate(app)
    assert outsider.get("/api/messages/threads").get_json()["threads"] == []
    assert outsider.get(f"/api/messages/threads/{identifier}/messages").status_code == 404
    assert send(outsider, identifier).status_code == 404
    assert change(outsider, f"/api/messages/threads/{identifier}/read", {"through_id": 1}).status_code == 404


def test_unrelated_hr_cannot_access_thread(people, app):
    _, _, _, identifier = people
    outsider = app.test_client()
    response = change(outsider, "/api/auth/register", {"role": "hr", "display_name": "Unrelated Synthetic HR", "email": "outsider.hr@example.invalid", "password": "SyntheticPassphrase123!"})
    assert response.status_code == 201
    assert outsider.get("/api/messages/threads").get_json()["threads"] == []
    assert outsider.get(f"/api/messages/threads/{identifier}/messages").status_code == 404
    assert send(outsider, identifier).status_code == 404


def test_reads_are_explicit_and_do_not_swallow_new_messages(people):
    candidate, hr, _, identifier = people
    first = send(hr, identifier, "First question").get_json()["message"]
    second = send(hr, identifier, "Second question").get_json()["message"]
    path = f"/api/messages/threads/{identifier}"
    assert candidate.get(path + "/messages").get_json()["thread"]["unread_count"] == 2
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 2
    assert change(candidate, path + "/read", {"through_id": first["id"]}).get_json()["thread"]["unread_count"] == 1
    assert change(candidate, path + "/read", {"through_id": second["id"]}).get_json()["thread"]["unread_count"] == 0
    # Repeating an exact acknowledgement is idempotent.
    assert change(candidate, path + "/read", {"through_id": first["id"]}).get_json()["thread"]["unread_count"] == 0


def test_exact_read_ids_do_not_mark_older_unseen_messages_read(people):
    candidate, hr, _, identifier = people
    sent = [send(hr, identifier, f"Incoming message {index}").get_json()["message"]["id"] for index in range(3)]
    path = f"/api/messages/threads/{identifier}/read"

    # The compatibility field names one message rather than an unseen range.
    latest = change(candidate, path, {"through_id": sent[-1]})
    assert latest.status_code == 200
    assert latest.get_json()["thread"]["unread_count"] == 2
    # Going backwards through the conversation must still record these reads.
    older = change(candidate, path, {"message_ids": [sent[1]] * 100})
    assert older.status_code == 200
    assert older.get_json()["thread"]["unread_count"] == 1
    assert change(candidate, path, {"message_ids": [sent[0]]}).get_json()["thread"]["unread_count"] == 0
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 0


def test_reading_latest_page_leaves_older_incoming_messages_unread(people):
    candidate, hr, _, identifier = people
    sent = [send(hr, identifier, f"Burst message {index}").get_json()["message"]["id"] for index in range(65)]
    path = f"/api/messages/threads/{identifier}"
    latest = candidate.get(path + "/messages").get_json()
    assert [item["id"] for item in latest["messages"]] == sent[-50:]
    assert latest["has_more"] is True
    assert latest["thread"]["unread_count"] == 65

    response = change(candidate, path + "/read", {"message_ids": [item["id"] for item in latest["messages"]]})
    assert response.status_code == 200
    assert response.get_json()["thread"]["unread_count"] == 15
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 15
    older = candidate.get(path + f"/messages?before={latest['next_before']}").get_json()
    assert [item["id"] for item in older["messages"]] == sent[:15]
    assert change(candidate, path + "/read", {"message_ids": sent[:15]}).get_json()["thread"]["unread_count"] == 0


def test_reading_own_message_does_not_acknowledge_unseen_incoming_messages(people):
    candidate, hr, _, identifier = people
    send(hr, identifier, "An unseen incoming message")
    own = send(candidate, identifier, "An outgoing reply").get_json()["message"]["id"]
    response = change(candidate, f"/api/messages/threads/{identifier}/read", {"message_ids": [own]})
    assert response.status_code == 200
    assert response.get_json()["thread"]["unread_count"] == 1
    assert hr.get("/api/messages/threads").get_json()["unread_count"] == 1


@pytest.mark.parametrize("payload", [{"message_ids": []}, {"through_id": 0}])
def test_empty_read_acknowledgements_leave_unread_messages_unchanged(people, payload):
    candidate, hr, _, identifier = people
    send(hr, identifier)
    response = change(candidate, f"/api/messages/threads/{identifier}/read", payload)
    assert response.status_code == 200
    assert response.get_json()["thread"]["unread_count"] == 1


@pytest.mark.parametrize("payload", [
    {}, {"message_ids": None}, {"message_ids": "1"}, {"message_ids": [True]},
    {"message_ids": [0]}, {"message_ids": [-1]}, {"message_ids": ["1"]},
    {"message_ids": [None]}, {"message_ids": [2**63]}, {"message_ids": [1] * 101},
    {"through_id": True}, {"through_id": -1}, {"through_id": "1"},
    {"message_ids": [], "through_id": 0},
])
def test_invalid_exact_read_payloads_are_rejected(people, payload):
    candidate, _, _, identifier = people
    assert change(candidate, f"/api/messages/threads/{identifier}/read", payload).status_code == 400


def test_mixed_thread_read_ids_are_rejected_atomically(people, app):
    candidate, hr, job, identifier = people
    own = send(hr, identifier, "This must stay unread").get_json()["message"]["id"]
    other = new_candidate(app)
    foreign_thread = change(other, "/api/messages/threads", {"job_id": job["id"]}).get_json()["thread"]["id"]
    foreign = send(other, foreign_thread).get_json()["message"]["id"]
    path = f"/api/messages/threads/{identifier}/read"

    assert change(candidate, path, {"message_ids": [own, foreign]}).status_code == 404
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 1
    assert change(other, path, {"message_ids": [own]}).status_code == 404
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 1


def test_sending_does_not_implicitly_mark_incoming_messages_read(people):
    candidate, hr, _, identifier = people
    send(hr, identifier)
    send(candidate, identifier)
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 1


def test_message_retry_nonce_prevents_duplicates(people):
    candidate, hr, _, identifier = people
    first = send(candidate, identifier, client_nonce="synthetic_retry_1")
    retry = send(candidate, identifier, client_nonce="synthetic_retry_1")
    assert first.status_code == 201 and retry.status_code == 200
    assert first.get_json()["message"]["id"] == retry.get_json()["message"]["id"]
    assert send(candidate, identifier, "Different text", client_nonce="synthetic_retry_1").status_code == 409
    assert len(candidate.get(f"/api/messages/threads/{identifier}/messages").get_json()["messages"]) == 1
    notices = hr.get("/api/workflow/updates").get_json()["notifications"]
    assert len([item for item in notices if item["kind"] == "message"]) == 1


def test_notifications_only_reach_other_participant(people, app):
    candidate, hr, _, identifier = people
    send(candidate, identifier)
    sender_notices = candidate.get("/api/workflow/updates").get_json()["notifications"]
    recipient_notices = hr.get("/api/workflow/updates").get_json()["notifications"]
    assert not any(item["kind"] == "message" for item in sender_notices)
    assert len([item for item in recipient_notices if item["kind"] == "message"]) == 1
    outsider = new_candidate(app)
    assert outsider.get("/api/workflow/updates").get_json()["notifications"] == []


@pytest.mark.parametrize("body", ["", "   ", "a" * 2001, None, 5, "invalid\x00text"])
def test_invalid_message_body_rejected(people, body):
    candidate, _, _, identifier = people
    assert send(candidate, identifier, body).status_code == 400


@pytest.mark.parametrize("nonce", ["bad", 12, "<script>bad</script>", "a" * 81])
def test_invalid_retry_identifiers_rejected(people, nonce):
    candidate, _, _, identifier = people
    assert send(candidate, identifier, client_nonce=nonce).status_code == 400


def test_html_is_retained_as_inert_text(people):
    candidate, hr, _, identifier = people
    body = '<img src=x onerror="alert(1)">\nIs this role remote?'
    assert send(candidate, identifier, body).status_code == 201
    assert hr.get(f"/api/messages/threads/{identifier}/messages").get_json()["messages"][0]["body"] == body


def test_csrf_required_for_every_message_mutation(people):
    candidate, _, job, identifier = people
    assert candidate.post("/api/messages/threads", json={"job_id": job["id"]}).status_code == 403
    assert candidate.post(f"/api/messages/threads/{identifier}/messages", json={"body": "Hello"}).status_code == 403
    assert candidate.post(f"/api/messages/threads/{identifier}/read", json={"through_id": 0}).status_code == 403


def test_bounded_pagination_and_invalid_limits(people):
    candidate, hr, _, identifier = people
    sent = [send(hr, identifier, f"Synthetic message {index}").get_json()["message"]["id"] for index in range(6)]
    path = f"/api/messages/threads/{identifier}/messages"
    latest = candidate.get(path + "?limit=2").get_json()
    assert [item["id"] for item in latest["messages"]] == sent[-2:]
    assert latest["has_more"]
    older = candidate.get(path + f"?limit=2&before={latest['next_before']}").get_json()
    assert [item["id"] for item in older["messages"]] == sent[2:4]
    for query in ["limit=0", "limit=101", "limit=abc", "before=-1", "limit=1.5"]:
        assert candidate.get(path + "?" + query).status_code == 400


@pytest.mark.parametrize("identifier", [True, 0, -1, "1", None])
def test_invalid_job_identifiers_rejected(app, identifier):
    client = app.test_client()
    login(client, "jobseeker")
    assert change(client, "/api/messages/threads", {"job_id": identifier}).status_code == 400


def test_read_cannot_acknowledge_another_threads_message(people, app):
    candidate, hr, job, identifier = people
    other = new_candidate(app)
    other_id = change(other, "/api/messages/threads", {"job_id": job["id"]}).get_json()["thread"]["id"]
    foreign_message = send(other, other_id).get_json()["message"]
    assert change(candidate, f"/api/messages/threads/{identifier}/read", {"through_id": foreign_message["id"]}).status_code == 404


def test_oversized_identifiers_return_validation_error(people):
    candidate, _, _, identifier = people
    assert change(candidate, f"/api/messages/threads/{identifier}/read", {"through_id": 2**63}).status_code == 400
    assert candidate.get(f"/api/messages/threads/{2**63}/messages").status_code == 400
    assert send(candidate, 2**63).status_code == 400


def test_init_preserves_existing_threads_and_messages(app, people):
    candidate, _, _, identifier = people
    send(candidate, identifier)
    init_communication(app)
    assert len(candidate.get(f"/api/messages/threads/{identifier}/messages").get_json()["messages"]) == 1


def test_legacy_read_watermarks_migrate_without_resetting_or_swallowing_new_messages(app, people):
    candidate, hr, _, identifier = people
    first_incoming = send(hr, identifier, "Already read by candidate").get_json()["message"]["id"]
    first_outgoing = send(candidate, identifier, "Already read by HR").get_json()["message"]["id"]
    second_incoming = send(hr, identifier, "Also read by candidate").get_json()["message"]["id"]
    second_outgoing = send(candidate, identifier, "Still unread by HR").get_json()["message"]["id"]
    with app.extensions["workflow"].connection() as con:
        con.execute("UPDATE message_threads SET candidate_seen_id=?,hr_seen_id=? WHERE id=?", (second_incoming, first_outgoing, identifier))

    init_communication(app)
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 0
    assert hr.get("/api/messages/threads").get_json()["unread_count"] == 1
    response = change(hr, f"/api/messages/threads/{identifier}/read", {"message_ids": [second_outgoing]})
    assert response.status_code == 200
    assert response.get_json()["thread"]["unread_count"] == 0
    # Reinitialization preserves exact reads and never promotes a new message
    # merely because an older legacy watermark was imported earlier.
    send(hr, identifier, "New incoming message remains unread")
    init_communication(app)
    assert candidate.get("/api/messages/threads").get_json()["unread_count"] == 1
    assert hr.get("/api/messages/threads").get_json()["unread_count"] == 0
