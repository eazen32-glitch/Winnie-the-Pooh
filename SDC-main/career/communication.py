"""Private, synthetic candidate/recruiter conversations for the demo.

This module never sends email or contacts an external employer. A conversation
belongs to one candidate and the HR account that owns the associated company.
Reading a page does not mark messages read; the client acknowledges only the
messages it actually displayed.
"""

from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from .workflow import (
    WorkflowError, _fail, _iso, _json, _notify, _positive_id, _service, _text, _user,
    csrf_check,
)

communication_bp = Blueprint("communication", __name__, url_prefix="/api/messages")
communication_bp.before_request(csrf_check)


@communication_bp.errorhandler(WorkflowError)
def communication_error(error):
    return jsonify(error=str(error)), error.status


def init_communication(app):
    with app.extensions["workflow"].connection() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS message_threads (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                candidate_id INTEGER NOT NULL REFERENCES users(id),
                candidate_seen_id INTEGER NOT NULL DEFAULT 0,
                hr_seen_id INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(job_id, candidate_id)
            );
            CREATE TABLE IF NOT EXISTS thread_messages (
                id INTEGER PRIMARY KEY,
                thread_id INTEGER NOT NULL REFERENCES message_threads(id),
                sender_id INTEGER NOT NULL REFERENCES users(id),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                client_nonce TEXT,
                UNIQUE(thread_id, sender_id, client_nonce)
            );
            CREATE INDEX IF NOT EXISTS thread_candidate_idx ON message_threads(candidate_id);
            CREATE INDEX IF NOT EXISTS thread_message_idx ON thread_messages(thread_id, id);
            CREATE TABLE IF NOT EXISTS message_reads (
                message_id INTEGER NOT NULL REFERENCES thread_messages(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                read_at TEXT NOT NULL,
                PRIMARY KEY(message_id, user_id)
            );
            CREATE INDEX IF NOT EXISTS message_read_user_idx ON message_reads(user_id, message_id);
        """)
        # Preserve receipts from the original cursor-based schema. New reads
        # record individual displayed messages and never advance these cursors.
        con.execute("""
            INSERT OR IGNORE INTO message_reads(message_id,user_id,read_at)
            SELECT m.id,t.candidate_id,? FROM thread_messages m
            JOIN message_threads t ON t.id=m.thread_id
            WHERE m.id<=t.candidate_seen_id AND m.sender_id<>t.candidate_id
        """, (_iso(),))
        con.execute("""
            INSERT OR IGNORE INTO message_reads(message_id,user_id,read_at)
            SELECT m.id,c.owner_id,? FROM thread_messages m
            JOIN message_threads t ON t.id=m.thread_id
            JOIN jobs j ON j.id=t.job_id JOIN companies c ON c.id=j.company_id
            WHERE m.id<=t.hr_seen_id AND m.sender_id<>c.owner_id
        """, (_iso(),))


def _owned_thread(con, identifier, user):
    identifier = _positive_id(identifier, "Conversation ID")
    row = con.execute("""
        SELECT t.*, j.title AS job_title, c.id AS company_id,
               c.name AS company_name, c.owner_id AS hr_id,
               u.display_name AS candidate_name
        FROM message_threads t
        JOIN jobs j ON j.id=t.job_id
        JOIN companies c ON c.id=j.company_id
        JOIN users u ON u.id=t.candidate_id
        WHERE t.id=? AND (t.candidate_id=? OR c.owner_id=?)
    """, (identifier, user["id"], user["id"])).fetchone()
    if row is None:
        _fail("Conversation not found in your account.", 404)
    return row


def _thread_view(con, row, user):
    candidate = user["id"] == row["candidate_id"]
    last = con.execute("SELECT id,body,created_at,sender_id FROM thread_messages WHERE thread_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    unread = con.execute("""
        SELECT COUNT(*) FROM thread_messages m WHERE m.thread_id=? AND m.sender_id<>?
        AND NOT EXISTS(SELECT 1 FROM message_reads r WHERE r.message_id=m.id AND r.user_id=?)
    """, (row["id"], user["id"], user["id"])).fetchone()[0]
    return {
        "id": row["id"], "job_id": row["job_id"], "job_title": row["job_title"],
        "company": {"id": row["company_id"], "name": row["company_name"]},
        "candidate": {"id": row["candidate_id"], "display_name": row["candidate_name"]},
        "counterpart": row["company_name"] if candidate else row["candidate_name"],
        "unread_count": unread, "created_at": row["created_at"], "updated_at": row["updated_at"],
        "last_message": {"id": last["id"], "preview": last["body"][:140], "created_at": last["created_at"], "mine": last["sender_id"] == user["id"]} if last else None,
        "synthetic": True,
    }


def _query_integer(key, default, minimum, maximum):
    raw = request.args.get(key, str(default))
    if not re.fullmatch(r"[0-9]{1,19}", raw):
        _fail(f"{key.capitalize()} must be a whole number.")
    value = int(raw)
    if not minimum <= value <= maximum:
        _fail(f"{key.capitalize()} must be from {minimum} to {maximum}.")
    return value


@communication_bp.get("/threads")
def threads():
    user = _user()
    limit = _query_integer("limit", 100, 1, 100)
    before = _query_integer("before", 2**62, 1, 2**62)
    with _service().connection() as con:
        # IDs provide stable pagination even while new messages update a thread.
        rows = con.execute("""
            SELECT t.id FROM message_threads t JOIN jobs j ON j.id=t.job_id
            JOIN companies c ON c.id=j.company_id
            WHERE (t.candidate_id=? OR c.owner_id=?) AND t.id<?
            ORDER BY t.id DESC LIMIT ?
        """, (user["id"], user["id"], before, limit + 1)).fetchall()
        items = [_thread_view(con, _owned_thread(con, row["id"], user), user) for row in rows[:limit]]
        unread = con.execute("""
            SELECT COUNT(*) FROM thread_messages m
            JOIN message_threads t ON t.id=m.thread_id JOIN jobs j ON j.id=t.job_id
            JOIN companies c ON c.id=j.company_id
            WHERE m.sender_id<>? AND (t.candidate_id=? OR c.owner_id=?)
            AND NOT EXISTS(SELECT 1 FROM message_reads r WHERE r.message_id=m.id AND r.user_id=?)
        """, (user["id"], user["id"], user["id"], user["id"])).fetchone()[0]
    return jsonify(threads=items, unread_count=unread, has_more=len(rows) > limit,
                   next_before=items[-1]["id"] if len(rows) > limit else None)


@communication_bp.post("/threads")
def create_thread():
    user, payload = _user(), _json()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        if user["role"] == "jobseeker":
            if "job_id" not in payload and "application_id" in payload:
                application_id = _positive_id(payload.get("application_id"), "Application ID")
                owned = con.execute("SELECT job_id FROM applications WHERE id=? AND applicant_id=?", (application_id, user["id"])).fetchone()
                if owned is None:
                    _fail("Application not found in your account.", 404)
                job_id = owned["job_id"]
            else:
                job_id = _positive_id(payload.get("job_id"), "Job ID")
            job = con.execute("SELECT id,status,deadline FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                _fail("Job not found.", 404)
            candidate_id = user["id"]
        elif user["role"] == "hr":
            application_id = _positive_id(payload.get("application_id"), "Application ID")
            application = con.execute("""
                SELECT a.job_id,a.applicant_id FROM applications a JOIN jobs j ON j.id=a.job_id
                JOIN companies c ON c.id=j.company_id WHERE a.id=? AND c.owner_id=?
            """, (application_id, user["id"])).fetchone()
            if application is None:
                _fail("Application not found in your company.", 404)
            job_id, candidate_id = application["job_id"], application["applicant_id"]
        else:
            _fail("This account cannot start conversations.", 403)
        existing = con.execute("SELECT id FROM message_threads WHERE job_id=? AND candidate_id=?", (job_id, candidate_id)).fetchone()
        if existing:
            identifier, created = existing["id"], False
        else:
            if user["role"] == "jobseeker" and job["status"] != "open":
                _fail("New enquiries are unavailable for this closed job.", 409)
            now = _iso()
            identifier = con.execute("INSERT INTO message_threads(job_id,candidate_id,created_at,updated_at) VALUES(?,?,?,?)", (job_id, candidate_id, now, now)).lastrowid
            created = True
        item = _thread_view(con, _owned_thread(con, identifier, user), user)
    return jsonify(thread=item), 201 if created else 200


@communication_bp.get("/threads/<int:identifier>/messages")
def messages(identifier):
    user = _user()
    limit = _query_integer("limit", 50, 1, 100)
    before = _query_integer("before", 2**62, 1, 2**62)
    with _service().connection() as con:
        thread = _owned_thread(con, identifier, user)
        rows = con.execute("""
            SELECT m.*,u.display_name AS sender_name FROM thread_messages m
            JOIN users u ON u.id=m.sender_id WHERE m.thread_id=? AND m.id<?
            ORDER BY m.id DESC LIMIT ?
        """, (identifier, before, limit + 1)).fetchall()
        items = [{"id": row["id"], "body": row["body"], "sender_name": row["sender_name"],
                  "mine": row["sender_id"] == user["id"], "created_at": row["created_at"]} for row in reversed(rows[:limit])]
        dto = _thread_view(con, thread, user)
    return jsonify(thread=dto, messages=items, has_more=len(rows) > limit,
                   next_before=items[0]["id"] if len(rows) > limit else None)


@communication_bp.post("/threads/<int:identifier>/messages")
def send_message(identifier):
    user, payload = _user(), _json()
    body = _text(payload, "body", 2000, required=True)
    nonce = payload.get("client_nonce")
    if nonce is not None and (not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", nonce)):
        _fail("Message request identifier is invalid.")
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        thread = _owned_thread(con, identifier, user)
        existing = con.execute("SELECT * FROM thread_messages WHERE thread_id=? AND sender_id=? AND client_nonce=?", (identifier, user["id"], nonce)).fetchone() if nonce else None
        if existing:
            if existing["body"] != body:
                _fail("A message request identifier was already used for different text.", 409)
            message_id, created, timestamp = existing["id"], False, existing["created_at"]
        else:
            timestamp = _iso()
            message_id = con.execute("INSERT INTO thread_messages(thread_id,sender_id,body,created_at,client_nonce) VALUES(?,?,?,?,?)", (identifier, user["id"], body, timestamp, nonce)).lastrowid
            con.execute("UPDATE message_threads SET updated_at=? WHERE id=?", (timestamp, identifier))
            recipient = thread["hr_id"] if user["id"] == thread["candidate_id"] else thread["candidate_id"]
            application = con.execute("SELECT id FROM applications WHERE job_id=? AND applicant_id=?", (thread["job_id"], thread["candidate_id"])).fetchone()
            _notify(con, recipient, "message", "New message about " + thread["job_title"], application["id"] if application else None)
            created = True
        # Sending must not implicitly acknowledge earlier incoming messages.
        item = {"id": message_id, "body": body, "sender_name": user["display_name"], "mine": True, "created_at": timestamp}
    return jsonify(message=item), 201 if created else 200


@communication_bp.post("/threads/<int:identifier>/read")
def acknowledge(identifier):
    user, payload = _user(), _json()
    if "message_ids" in payload:
        identifiers = payload["message_ids"]
        if "through_id" in payload or not isinstance(identifiers, list) or len(identifiers) > 100:
            _fail("Choose at most 100 displayed message IDs.")
        identifiers = {_positive_id(value, "Message ID") for value in identifiers}
    else:
        # Compatibility for older clients: acknowledge this exact message, not
        # every earlier message, because pages may not have been displayed.
        through = payload.get("through_id")
        if isinstance(through, bool) or not isinstance(through, int) or not 0 <= through <= 2**63 - 1:
            _fail("Choose a displayed message ID.")
        identifiers = {through} if through else set()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        thread = _owned_thread(con, identifier, user)
        if identifiers:
            placeholders = ",".join("?" for _ in identifiers)
            found = con.execute(f"SELECT id FROM thread_messages WHERE thread_id=? AND id IN ({placeholders})", (identifier, *identifiers)).fetchall()
            if len(found) != len(identifiers):
                _fail("Message not found in this conversation.", 404)
            con.executemany("INSERT OR IGNORE INTO message_reads(message_id,user_id,read_at) VALUES(?,?,?)",
                            [(message_id, user["id"], _iso()) for message_id in identifiers])
        item = _thread_view(con, _owned_thread(con, identifier, user), user)
    return jsonify(thread=item)
