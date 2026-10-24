"""Local, synthetic recruitment workflow for the hackathon demonstration.

SQLite persists accounts, submitted resume snapshots and interview decisions.
Demo role entry deliberately opens shared synthetic accounts; newly registered
accounts remain isolated. Nothing here submits to a real employer or sends mail.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hmac
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .catalog import PROFILES, ROLES, SKILLS
from .assistant import role_exposure
from .recommendations import build_skill_pathway
from .sources import safe_url
from .verification import SYNTHETIC_FIXTURE, VerificationError, check_domain, check_registry, normalize_evidence

workflow_bp = Blueprint("workflow", __name__)
UTC = timezone.utc
LOCAL_ZONE = ZoneInfo("Asia/Kuala_Lumpur")
SKILL_MAP = {item["id"]: item for item in SKILLS}
ROLE_MAP = {item["id"]: item for item in ROLES}
ACTIVE_STATUSES = {"submitted", "viewed", "under_review", "shortlisted", "interview_scheduled"}
TERMINAL_STATUSES = {"accepted", "rejected", "withdrawn"}
SALARY_CURRENCIES = {"MYR", "USD", "SGD", "GBP", "EUR", "AUD"}
SALARY_PERIODS = {"hour", "month", "year"}


class WorkflowError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _fail(message, status=400):
    raise WorkflowError(message, status)


@workflow_bp.errorhandler(WorkflowError)
def workflow_error(error):
    return jsonify(error=str(error)), error.status


def _now():
    return datetime.now(UTC)


def _iso(value=None):
    return (value or _now()).astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _today():
    return _now().astimezone(LOCAL_ZONE).date()


def _json():
    if not request.is_json:
        _fail("Send application/json.", 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        _fail("Send a JSON object.")
    return payload


def _text(payload, key, maximum=240, *, required=False, default=""):
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value) > maximum:
        _fail(f"{key.replace('_', ' ').capitalize()} must be text of at most {maximum} characters.")
    value = value.strip()
    if required and not value:
        _fail(f"{key.replace('_', ' ').capitalize()} is required.")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        _fail(f"{key.replace('_', ' ').capitalize()} contains unsupported characters.")
    return value


def _skills(values, *, required=False):
    if not isinstance(values, list) or len(values) > len(SKILL_MAP):
        _fail("Select skills from the supplied catalogue.")
    if any(not isinstance(value, str) or value not in SKILL_MAP for value in values):
        _fail("Select skills from the supplied catalogue.")
    if len(set(values)) != len(values):
        _fail("Select each skill only once.")
    if required and not values:
        _fail("Select at least one skill.")
    return values


def _positive_id(value, field="ID"):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2**63 - 1:
        _fail(f"{field} must be a positive whole number.")
    return value


def _is_choice(value, choices):
    return isinstance(value, str) and value in choices


def _https(value, *, required=False):
    if not value and not required:
        return ""
    if re.search(r"\s", value) or not safe_url(value):
        _fail("Use a valid HTTPS link without embedded credentials.")
    return value


def _skill_view(identifier):
    value = SKILL_MAP[identifier]
    return {key: value[key] for key in ("id", "name", "sdgs")}


def _match(required, known):
    known = set(known)
    matched = [identifier for identifier in required if identifier in known]
    missing = [identifier for identifier in required if identifier not in known]
    return {"percentage": round(100 * len(matched) / len(required), 1) if required else 0,
            "matched_skills": [_skill_view(value) for value in matched],
            "missing_skills": [_skill_view(value) for value in missing]}


def _resume(payload, version):
    hours = payload.get("weekly_hours", 6)
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 40:
        _fail("Weekly learning hours must be a whole number from 1 to 40.")
    return {
        "display_name": _text(payload, "display_name", 100, required=True),
        "headline": _text(payload, "headline", 160, required=True),
        "education": _text(payload, "education", 2000),
        "experience": _text(payload, "experience", 3000),
        "location": _text(payload, "location", 120),
        "skills": _skills(payload.get("skills", []), required=True),
        "interests": _text(payload, "interests", 1000),
        "weekly_hours": hours, "version": version,
    }


def _salary(payload):
    values = []
    for key in ("salary_min", "salary_max"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1_000_000_000 or not math.isfinite(value):
            _fail("A positive, finite minimum and maximum base salary are required.")
        values.append(round(value, 2))
    if min(values) <= 0:
        _fail("Base salary must be at least 0.01 in the selected currency.")
    if values[0] > values[1]:
        _fail("Maximum base salary must be at least the minimum base salary.")
    currency = payload.get("salary_currency")
    period = payload.get("salary_period")
    if not _is_choice(currency, SALARY_CURRENCIES) or not _is_choice(period, SALARY_PERIODS):
        _fail("Choose a supported salary currency and pay period.")
    return (*values, currency, period)


def _sla_days():
    value = current_app.config.get("APPLICATION_SLA_DAYS", 7)
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 90 else 7


def _parse_stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _notify(con, user_id, kind, title, application_id=None):
    con.execute("INSERT INTO workflow_notifications(user_id,kind,title,application_id,created_at) VALUES(?,?,?,?,?)",
                (user_id, kind, title, application_id, _iso()))


def _event(con, application_id, status, actor_id=None, reason=""):
    con.execute("INSERT INTO application_events(application_id,status,actor_id,reason,created_at) VALUES(?,?,?,?,?)",
                (application_id, status, actor_id, reason, _iso()))


def _notify_application(con, row, actor_id, title):
    owner = con.execute("SELECT c.owner_id FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=?", (row["job_id"],)).fetchone()["owner_id"]
    for recipient in {row["applicant_id"], owner} - {actor_id}:
        _notify(con, recipient, "application", title, row["id"])


def _verification_mode():
    mode = current_app.config.get("EMPLOYER_VERIFICATION_MODE", "synthetic")
    if not isinstance(mode, str) or mode not in {"synthetic", "gleif"}:
        _fail("The employer verification provider is not configured correctly.", 503)
    return mode


def _verification_ttl():
    value = current_app.config.get("EMPLOYER_VERIFICATION_TTL_DAYS", 30)
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 90 else 30


def _challenge_minutes():
    value = current_app.config.get("EMPLOYER_DOMAIN_CHALLENGE_MINUTES", 30)
    return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 60 else 30


def _stored_json(row, key):
    try:
        result = json.loads(row[key])
        return result if isinstance(result, dict) else {}
    except (TypeError, ValueError):
        return {}


def _fresh(value):
    try:
        return bool(value) and _parse_stamp(value) > _now()
    except (TypeError, ValueError, OverflowError):
        return False


def _snapshot_matches(snapshot):
    if snapshot.get("status") != "matched" or not _fresh(snapshot.get("expires_at")):
        return False
    try:
        checked = _parse_stamp(snapshot["checked_at"])
        if checked > _now() or checked >= _parse_stamp(snapshot["expires_at"]):
            return False
        digest = snapshot["sha256"]
        encoded = json.dumps({key: value for key, value in snapshot.items() if key != "sha256"}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return isinstance(digest, str) and hmac.compare_digest(digest, hashlib.sha256(encoded.encode()).hexdigest())
    except (TypeError, KeyError, ValueError, OverflowError):
        return False


def _verification_view(row, private=False):
    evidence = _stored_json(row, "verification_evidence_json")
    registry = _stored_json(row, "registry_snapshot_json")
    domain = _stored_json(row, "domain_snapshot_json")
    review = _stored_json(row, "verification_review_json")
    mode = row["verification_mode"] or _verification_mode()
    same_mode = mode == _verification_mode()
    registry_ok = same_mode and _snapshot_matches(registry)
    domain_ok = same_mode and _snapshot_matches(domain)
    status = row["verification_status"]
    if status == "verified" and (not registry_ok or not domain_ok or not _fresh(row["verification_expires_at"])):
        status = "expired" if same_mode else "unverified"
    moderator_ok = status == "verified" and bool(review.get("registration_confirmed") and review.get("domain_control_confirmed") and review.get("recruiter_authorization_confirmed"))
    can_publish = registry_ok and domain_ok and moderator_ok
    checks = {"registry": registry.get("status", "unchecked") if same_mode else "unchecked",
              "domain": domain.get("status", "unchecked") if same_mode else "unchecked",
              "moderator": "approved" if moderator_ok else "rejected" if status in {"rejected", "revoked"} else "pending" if evidence else "unchecked"}
    if checks["registry"] == "matched" and not registry_ok:
        checks["registry"] = "expired"
    if checks["domain"] == "matched" and not domain_ok:
        checks["domain"] = "expired"
    missing = []
    if not registry_ok:
        missing.append("A current legal entity registry match")
    if not domain_ok:
        missing.append("A current company domain control challenge")
    if not moderator_ok:
        missing.append("Independent moderator confirmation of recruiter authorization")
    limits = ["Registry records establish legal entity details, not recruiter identity or authority.",
              "Domain control proves control of a domain, not a person's identity.",
              "Moderator authorization review concerns the fictional recruiter reference in this demonstration; no real person's identity is verified.",
              "All accounts, vacancies and applications in this competition remain synthetic."]
    if mode == "synthetic":
        limits.insert(0, "All checks use a fixed fictional registry and a simulated domain challenge; no real employer is verified.")
    else:
        limits.insert(0, "GLEIF is the public Legal Entity Identifier registry, not Malaysia's SSM registry; organizations without an LEI cannot match this provider.")
    result = {"status": status, "reason": row["verification_reason"] if private else "", "mode": mode, "simulation": mode == "synthetic",
              "submitted_at": row["verification_submitted_at"], "reviewed_at": row["verification_reviewed_at"],
              "expires_at": row["verification_expires_at"] or (min(registry["expires_at"], domain["expires_at"]) if registry_ok and domain_ok else None), "checked_at": registry.get("checked_at"),
              "provider": registry.get("provider", "Synthetic fixture" if mode == "synthetic" else "GLEIF"),
              "checks": checks, "can_publish": can_publish, "missing_steps": missing, "limitations": limits,
              "badge": "synthetic_checks_complete" if can_publish and mode == "synthetic" else "registry_domain_moderator_checked" if can_publish else "checks_incomplete",
              "label": "Synthetic checks complete" if can_publish and mode == "synthetic" else "Public registry + DNS; demo authorization reviewed" if can_publish else "Verification checks incomplete"}
    record = registry.get("record") if isinstance(registry.get("record"), dict) else {}
    result["registry_source"] = {"provider": registry.get("provider", ""), "source_url": registry.get("source", ""),
                                 "checked_at": registry.get("checked_at"), "expires_at": registry.get("expires_at"),
                                 "status": checks["registry"], "simulation": mode == "synthetic", "sha256": registry.get("sha256", ""),
                                 "record": {key: record.get(key, "") for key in ("legal_name", "country", "registration_number", "lei", "entity_status", "registration_status", "registration_authority_id")}}
    if private:
        result.update(evidence=evidence, registry_snapshot=registry, domain_snapshot=domain,
                      domain_challenge=_stored_json(row, "domain_challenge_json"), review=review)
    return result


def _verification_event(con, company_id, actor_id, kind, payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    con.execute("INSERT INTO verification_evidence_events(company_id,actor_id,kind,payload_json,sha256,created_at) VALUES(?,?,?,?,?,?)",
                (company_id, actor_id, kind, encoded, hashlib.sha256(encoded.encode()).hexdigest(), _iso()))


def _publishing_allowed(company):
    if current_app.config.get("REQUIRE_EMPLOYER_VERIFICATION", True) and not company["verification"]["can_publish"]:
        _fail("Complete current registry, company domain and independent moderator checks before publishing a vacancy.", 409)


def _provider_attempt(con, company_id, mode, kind):
    """Reserve a live request in SQLite before leaving the transaction.

    The gate survives process restarts and is shared by concurrent workers.
    Synthetic fixture interactions stay immediate and never contact a provider.
    """
    if mode == "synthetic":
        return None
    prior = con.execute("SELECT * FROM verification_provider_attempts WHERE company_id=? AND kind=?", (company_id, kind)).fetchone()
    if prior and _fresh(prior["next_attempt_at"]):
        _fail("A public verification check was requested recently. Wait 30 seconds before trying this check again.", 429)
    nonce = secrets.token_urlsafe(24)
    con.execute("INSERT INTO verification_provider_attempts(company_id,kind,request_nonce,started_at,next_attempt_at) VALUES(?,?,?,?,?) ON CONFLICT(company_id,kind) DO UPDATE SET request_nonce=excluded.request_nonce,started_at=excluded.started_at,next_attempt_at=excluded.next_attempt_at",
                (company_id, kind, nonce, _iso(), _iso(_now() + timedelta(seconds=30))))
    return nonce


def _current_attempt(con, company_id, kind, nonce):
    if nonce is None:
        return True
    row = con.execute("SELECT request_nonce FROM verification_provider_attempts WHERE company_id=? AND kind=?", (company_id, kind)).fetchone()
    return bool(row and hmac.compare_digest(row["request_nonce"], nonce))


def _verification_unchanged(current, original):
    fields = ("name", "industry", "location", "description", "website", "verification_status", "verification_mode",
              "verification_evidence_json", "registry_snapshot_json", "domain_snapshot_json", "domain_challenge_json",
              "verification_review_json", "verification_submitted_at", "verification_reviewed_at", "verification_expires_at")
    return bool(current) and all(current[key] == original[key] for key in fields)


class WorkflowService:
    def __init__(self, database, sla_days=7):
        self.database = str(database)
        self.sla_days = sla_days if isinstance(sla_days, int) and not isinstance(sla_days, bool) and 1 <= sla_days <= 90 else 7
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.database, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def initialize(self):
        with self.connection() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('jobseeker','hr')),
                    onboarding_complete INTEGER NOT NULL DEFAULT 0,
                    resume_json TEXT, profile_version INTEGER NOT NULL DEFAULT 0,
                    demo_key TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
                    name TEXT NOT NULL, industry TEXT NOT NULL, location TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
                    synthetic INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                    title TEXT NOT NULL, role_id TEXT NOT NULL, description TEXT NOT NULL,
                    location TEXT NOT NULL, work_mode TEXT NOT NULL, employment_type TEXT NOT NULL,
                    required_skills_json TEXT NOT NULL, deadline TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL REFERENCES jobs(id),
                    applicant_id INTEGER NOT NULL REFERENCES users(id), resume_json TEXT NOT NULL,
                    resume_version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'submitted',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    UNIQUE(job_id, applicant_id)
                );
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE REFERENCES applications(id),
                    start TEXT NOT NULL, end TEXT NOT NULL, meeting_url TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'scheduled'
                );
                CREATE INDEX IF NOT EXISTS application_applicant_idx ON applications(applicant_id);
                CREATE INDEX IF NOT EXISTS job_company_idx ON jobs(company_id);
            """)
            self._migrate(con)
            # One transaction protects an interrupted first-time seed. Existing
            # companies, profiles, decisions and deadlines are never reset.
            if not con.in_transaction:
                con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT id FROM users WHERE demo_key='jobseeker'").fetchone():
                self._extended_seed(con)
                return
            seeds = [
                ("alex.demo@example.invalid", "Alex Demo", "jobseeker", "jobseeker", 0),
                ("hr.demo@example.invalid", "Verdant HR Demo", "hr", "hr", None),
                ("hr.other@example.invalid", "BrightPath HR Demo", "hr", "hr-other", None),
                ("sam.demo@example.invalid", "Sam Demo", "jobseeker", "candidate-2", 1),
                ("maya.demo@example.invalid", "Maya Demo", "jobseeker", "candidate-3", 2),
            ]
            ids = {}
            for email, name, role, key, profile_index in seeds:
                resume = None
                if profile_index is not None:
                    base = PROFILES[profile_index]
                    resume = {"display_name": name, "headline": "Synthetic early-career profile",
                              "education": "Demo university programme", "experience": "Synthetic project and volunteering experience.",
                              "location": "Kuala Lumpur", "skills": base["skills"], "interests": base["interests"],
                              "weekly_hours": base["weekly_hours"], "version": 1}
                cursor = con.execute("INSERT INTO users(email,password_hash,display_name,role,onboarding_complete,resume_json,profile_version,demo_key) VALUES(?,?,?,?,1,?,?,?)",
                                     (email, generate_password_hash(secrets.token_urlsafe(32)), name, role,
                                      json.dumps(resume) if resume else None, 1 if resume else 0, key))
                ids[key] = cursor.lastrowid
            companies = []
            for owner, name, industry, description in [
                (ids["hr"], "Verdant Labs (Demo)", "Responsible technology", "A synthetic company developing useful digital and sustainability tools."),
                (ids["hr-other"], "BrightPath Learning (Demo)", "Education and sustainability", "A synthetic employer supporting learning, operational improvement and climate projects."),
            ]:
                cursor = con.execute("INSERT INTO companies(owner_id,name,industry,location,description,website) VALUES(?,?,?,'Kuala Lumpur',?,'')", (owner, name, industry, description))
                companies.append(cursor.lastrowid)
            job_ids = []
            for index, role in enumerate(ROLES):
                company_id = companies[0 if index < 4 else 1]
                cursor = con.execute("INSERT INTO jobs(company_id,title,role_id,description,location,work_mode,employment_type,required_skills_json,deadline,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'open',?)",
                                     (company_id, role["title"], role["id"], "Synthetic demo vacancy. " + role["summary"],
                                      "Kuala Lumpur" if index % 2 else "Penang", ["hybrid", "remote", "onsite"][index % 3],
                                      "full-time", json.dumps([item["id"] for item in role["skills"]]),
                                      (_today() + timedelta(days=30 + index)).isoformat(), _iso()))
                job_ids.append(cursor.lastrowid)
            for key, job_index, status in [("jobseeker", 0, "submitted"), ("candidate-2", 1, "shortlisted"), ("candidate-3", 2, "under_review")]:
                user = con.execute("SELECT resume_json FROM users WHERE id=?", (ids[key],)).fetchone()
                con.execute("INSERT INTO applications(job_id,applicant_id,resume_json,resume_version,status,created_at,updated_at) VALUES(?,?,?,1,?,?,?)",
                            (job_ids[job_index], ids[key], user["resume_json"], status, _iso(), _iso()))
            self._extended_seed(con)

    def _migrate(self, con):
        """Add fields without replacing existing accounts, resumes or decisions."""
        additions = {
            "jobs": {"salary_min": "REAL", "salary_max": "REAL", "salary_currency": "TEXT", "salary_period": "TEXT"},
            "companies": {"verification_status": "TEXT NOT NULL DEFAULT 'unverified'", "verification_reason": "TEXT NOT NULL DEFAULT ''",
                          "registration_number": "TEXT NOT NULL DEFAULT ''", "recruiter_identity": "TEXT NOT NULL DEFAULT ''", "evidence_note": "TEXT NOT NULL DEFAULT ''",
                          "verification_submitted_at": "TEXT", "verification_reviewed_at": "TEXT",
                          "verification_mode": "TEXT NOT NULL DEFAULT ''", "verification_evidence_json": "TEXT NOT NULL DEFAULT '{}'",
                          "registry_snapshot_json": "TEXT NOT NULL DEFAULT '{}'", "domain_snapshot_json": "TEXT NOT NULL DEFAULT '{}'",
                          "domain_challenge_json": "TEXT NOT NULL DEFAULT '{}'", "verification_review_json": "TEXT NOT NULL DEFAULT '{}'",
                          "verification_expires_at": "TEXT"},
            "applications": {"response_due_at": "TEXT", "decision_reason": "TEXT NOT NULL DEFAULT ''", "viewed_at": "TEXT", "escalated_at": "TEXT"},
        }
        for table, fields in additions.items():
            existing = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
            for column, declaration in fields.items():
                if column not in existing:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
        con.executescript("""
            CREATE TABLE IF NOT EXISTS moderator_accounts (
                user_id INTEGER PRIMARY KEY REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS verification_audit (
                id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                actor_id INTEGER REFERENCES users(id), status TEXT NOT NULL, reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS verification_evidence_events (
                id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                actor_id INTEGER REFERENCES users(id), kind TEXT NOT NULL, payload_json TEXT NOT NULL,
                sha256 TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS verification_provider_attempts (
                company_id INTEGER NOT NULL REFERENCES companies(id), kind TEXT NOT NULL,
                request_nonce TEXT NOT NULL, started_at TEXT NOT NULL, next_attempt_at TEXT NOT NULL,
                PRIMARY KEY(company_id,kind)
            );
            CREATE TABLE IF NOT EXISTS compliance_incidents (
                id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL REFERENCES companies(id),
                job_id INTEGER REFERENCES jobs(id), kind TEXT NOT NULL, detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS compliance_legacy_job_idx
                ON compliance_incidents(job_id,kind) WHERE job_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS application_events (
                id INTEGER PRIMARY KEY, application_id INTEGER NOT NULL REFERENCES applications(id),
                status TEXT NOT NULL, actor_id INTEGER REFERENCES users(id), reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS application_event_idx ON application_events(application_id,id);
            CREATE TABLE IF NOT EXISTS workflow_notifications (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), kind TEXT NOT NULL,
                title TEXT NOT NULL, application_id INTEGER REFERENCES applications(id),
                created_at TEXT NOT NULL, read_at TEXT
            );
            CREATE INDEX IF NOT EXISTS workflow_notification_idx ON workflow_notifications(user_id,id);
        """)
        # The older badge meant only that a moderator read self-entered text.
        # Keep the original evidence and audit, but never inherit that badge as
        # registry/domain verification during this additive migration.
        legacy = con.execute("SELECT id FROM companies WHERE verification_status='verified' AND verification_mode=''").fetchall()
        for row in legacy:
            reason = "Earlier text-only approval requires registry, domain and independent authorization checks."
            con.execute("UPDATE companies SET verification_status='unverified',verification_reason=? WHERE id=?", (reason, row["id"]))
            con.execute("INSERT INTO verification_audit(company_id,status,reason,created_at) VALUES(?,'unverified',?,?)", (row["id"], reason, _iso()))

    def _extended_seed(self, con):
        moderator = con.execute("SELECT id FROM users WHERE demo_key='moderator'").fetchone()
        if not moderator:
            cursor = con.execute("INSERT INTO users(email,password_hash,display_name,role,onboarding_complete,demo_key) VALUES(?,?,?,'hr',1,'moderator')",
                                 ("moderator.demo@example.invalid", generate_password_hash(secrets.token_urlsafe(32)), "Moderator Demo"))
            moderator_id = cursor.lastrowid
            con.execute("INSERT INTO moderator_accounts(user_id) VALUES(?)", (moderator_id,))
        # Only original seeded vacancies receive clearly illustrative salaries.
        # Existing employer-entered jobs are never assigned fabricated pay.
        rows = con.execute("SELECT j.*,u.demo_key FROM jobs j JOIN companies c ON c.id=j.company_id JOIN users u ON u.id=c.owner_id WHERE j.salary_min IS NULL").fetchall()
        for row in rows:
            if row["demo_key"] in {"hr", "hr-other"} and row["description"].startswith("Synthetic demo vacancy. "):
                minimum = 3200 + (row["id"] % 5) * 300
                con.execute("UPDATE jobs SET salary_min=?,salary_max=?,salary_currency='MYR',salary_period='month' WHERE id=?", (minimum, minimum + 1800, row["id"]))
            else:
                con.execute("UPDATE jobs SET status='closed' WHERE id=?", (row["id"],))
                con.execute("INSERT OR IGNORE INTO compliance_incidents(company_id,job_id,kind,detail,created_at) VALUES(?,?,'missing_salary','Legacy vacancy closed until a base salary range is supplied.',?)", (row["company_id"], row["id"], _iso()))
        for row in con.execute("SELECT * FROM applications").fetchall():
            if not row["response_due_at"]:
                due = _parse_stamp(row["created_at"]) + timedelta(days=self.sla_days)
                con.execute("UPDATE applications SET response_due_at=? WHERE id=?", (_iso(due), row["id"]))
            if not con.execute("SELECT id FROM application_events WHERE application_id=? LIMIT 1", (row["id"],)).fetchone():
                con.execute("INSERT INTO application_events(application_id,status,reason,created_at) VALUES(?,?,?,?)",
                            (row["id"], row["status"], "Imported current state; earlier events were not recorded.", row["updated_at"]))

    def is_moderator(self, user):
        if not user:
            return False
        with self.connection() as con:
            permitted = con.execute("SELECT user_id FROM moderator_accounts WHERE user_id=?", (user["id"],)).fetchone()
            identity = con.execute("SELECT demo_key FROM users WHERE id=?", (user["id"],)).fetchone()
        # Email addresses are unverified in this local prototype; matching an
        # address supplied during signup must never grant moderator privileges.
        allowed = current_app.config.get("MODERATOR_USER_IDS", [])
        if not isinstance(allowed, (list, tuple, set)):
            allowed = []
        explicitly_allowed = user["id"] in {value for value in allowed if isinstance(value, int) and not isinstance(value, bool)}
        if _verification_mode() == "gleif" and identity and identity["demo_key"] == "moderator":
            return explicitly_allowed
        return bool(permitted) or explicitly_allowed

    def current_user(self):
        identifier = session.get("user_id")
        if not identifier:
            return None
        with self.connection() as con:
            row = con.execute("SELECT id,email,display_name,role,onboarding_complete FROM users WHERE id=?", (identifier,)).fetchone()
        user = self.user_dto(row) if row else None
        if user:
            user["is_moderator"] = self.is_moderator(user)
        return user

    @staticmethod
    def user_dto(row):
        return {"id": row["id"], "email": row["email"], "display_name": row["display_name"],
                "role": row["role"], "onboarding_complete": bool(row["onboarding_complete"])}

    def company(self, con, user_id):
        row = con.execute("SELECT * FROM companies WHERE owner_id=?", (user_id,)).fetchone()
        return self.company_view(con, row, private=True) if row else None

    def company_view(self, con, row, private=False):
        result = {key: row[key] for key in ("id", "name", "industry", "location", "description", "website")}
        result["verification"] = _verification_view(row, private=private)
        violations = con.execute("SELECT COUNT(*) FROM compliance_incidents WHERE company_id=?", (row["id"],)).fetchone()[0]
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        overdue = con.execute(f"SELECT COUNT(*) FROM applications a JOIN jobs j ON j.id=a.job_id WHERE j.company_id=? AND a.status IN ({placeholders}) AND a.response_due_at<?",
                              (row["id"], *ACTIVE_STATUSES, _iso())).fetchone()[0]
        result["accountability"] = {"score": max(0, 100 - violations * 10 - overdue * 5), "violations": violations,
                                    "overdue_applications": overdue, "method": "100 minus 10 per salary incident and 5 per currently overdue application; prototype policy."}
        if private:
            result["owner_id"] = row["owner_id"]
            result.update({key: row[key] for key in ("registration_number", "recruiter_identity", "evidence_note")})
        return result

    def profile(self, user):
        with self.connection() as con:
            row = con.execute("SELECT resume_json FROM users WHERE id=?", (user["id"],)).fetchone()
            company = self.company(con, user["id"]) if user["role"] == "hr" else None
        return {"user": user, "resume": json.loads(row["resume_json"]) if row["resume_json"] else None, "company": company}

    def job_view(self, con, row, resume=None, application=None):
        company = con.execute("SELECT * FROM companies WHERE id=?", (row["company_id"],)).fetchone()
        requirements = json.loads(row["required_skills_json"])
        known = (resume or {}).get("skills", [])
        weekly_hours = (resume or {}).get("weekly_hours", 6)
        pathway = build_skill_pathway(requirements, known, weekly_hours)
        pathway["weekly_hours"] = weekly_hours
        return {"id": row["id"], "title": row["title"], "role_id": row["role_id"], "description": row["description"],
                "location": row["location"], "work_mode": row["work_mode"], "employment_type": row["employment_type"],
                "required_skills": [_skill_view(value) for value in requirements], "deadline": row["deadline"],
                "status": row["status"], "company": self.company_view(con, company), "synthetic": True,
                "salary_min": row["salary_min"], "salary_max": row["salary_max"], "salary_currency": row["salary_currency"], "salary_period": row["salary_period"],
                "salary": {"minimum": row["salary_min"], "maximum": row["salary_max"], "currency": row["salary_currency"], "period": row["salary_period"], "illustrative": True},
                "exposure": role_exposure(row["role_id"]),
                "match": _match(requirements, known), "pathway": pathway,
                "application_id": application["id"] if application else None,
                "application_status": application["status"] if application else None}

    def application_view(self, con, row):
        resume = json.loads(row["resume_json"])
        job = con.execute("SELECT * FROM jobs WHERE id=?", (row["job_id"],)).fetchone()
        interview = con.execute("SELECT id,start,end,meeting_url,notes,status FROM interviews WHERE application_id=?", (row["id"],)).fetchone()
        job_dto = self.job_view(con, job, resume, row)
        due = row["response_due_at"] or _iso(_parse_stamp(row["created_at"]) + timedelta(days=self.sla_days))
        remaining = (_parse_stamp(due) - _now()).total_seconds() / 3600
        active = row["status"] in ACTIVE_STATUSES
        history = [dict(event) for event in con.execute("SELECT id,status,reason,created_at FROM application_events WHERE application_id=? ORDER BY id", (row["id"],))]
        return {"id": row["id"], "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"],
                "decision_reason": row["decision_reason"], "viewed_at": row["viewed_at"], "history": history,
                "sla": {"due_at": due, "overdue": active and remaining < 0, "remaining_hours": round(remaining, 1),
                        "escalated": bool(row["escalated_at"]), "active": active, "policy_days": self.sla_days},
                "job": job_dto, "applicant": {"id": row["applicant_id"], "display_name": resume["display_name"], "resume": resume},
                "match": job_dto["match"], "interview": dict(interview) if interview else None}


def init_workflow(app):
    database = app.config.get("WORKFLOW_DATABASE") or Path(app.root_path) / "instance" / "workflow.sqlite3"
    app.extensions["workflow"] = WorkflowService(database, app.config.get("APPLICATION_SLA_DAYS", 7))


def _service():
    return current_app.extensions["workflow"]


def _user(role=None):
    user = _service().current_user()
    if not user:
        _fail("Sign in to use this feature.", 401)
    if role and user["role"] != role:
        _fail("This action is not available for your account type.", 403)
    return user


def _session_dto():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    user = _service().current_user()
    return {"user": user, "role": user["role"] if user else "guest", "csrf_token": session["csrf_token"]}


def _sign_in(identifier):
    session.clear()
    session["user_id"] = identifier
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify(_session_dto())


@workflow_bp.before_request
def csrf_check():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        token = session.get("csrf_token", "")
        supplied = request.headers.get("X-CSRF-Token", "")
        if not token or not supplied or not hmac.compare_digest(token.encode("utf-8"), supplied.encode("utf-8")):
            _fail("Your session token is missing or expired. Reload and try again.", 403)


@workflow_bp.get("/api/auth/session")
def auth_session():
    return jsonify(_session_dto())


@workflow_bp.post("/api/auth/register")
def register():
    payload = _json()
    email = _text(payload, "email", 254, required=True).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        _fail("Enter a valid email address; use a synthetic address for the demo.")
    role = payload.get("role")
    if not _is_choice(role, {"jobseeker", "hr"}):
        _fail("Choose jobseeker or HR.")
    name = _text(payload, "display_name", 100, required=True)
    password = payload.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        _fail("Password must contain 8 to 128 characters.")
    try:
        with _service().connection() as con:
            cursor = con.execute("INSERT INTO users(email,password_hash,display_name,role) VALUES(?,?,?,?)",
                                 (email, generate_password_hash(password), name, role))
            identifier = cursor.lastrowid
    except sqlite3.IntegrityError:
        _fail("An account already uses this address.", 409)
    return _sign_in(identifier), 201


@workflow_bp.post("/api/auth/login")
def login():
    payload = _json()
    email = _text(payload, "email", 254, required=True).lower()
    password = payload.get("password", "")
    if not isinstance(password, str) or len(password) > 128:
        _fail("Email or password is incorrect.", 401)
    with _service().connection() as con:
        row = con.execute("SELECT id,password_hash FROM users WHERE email=?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        _fail("Email or password is incorrect.", 401)
    return _sign_in(row["id"])


@workflow_bp.post("/api/auth/demo")
def demo_login():
    payload = _json()
    role = payload.get("role")
    if not _is_choice(role, {"jobseeker", "hr", "moderator"}):
        _fail("Choose jobseeker, HR or moderator demo entry.")
    if role == "moderator" and (_verification_mode() == "gleif" or not current_app.config.get("ENABLE_MODERATOR_DEMO", True)):
        _fail("Moderator demo entry is disabled.", 403)
    with _service().connection() as con:
        row = con.execute("SELECT id FROM users WHERE demo_key=?", (role,)).fetchone()
    return _sign_in(row["id"])


@workflow_bp.post("/api/auth/logout")
def logout():
    _json()
    session.clear()
    return jsonify(_session_dto())


@workflow_bp.get("/api/workflow/profile")
def get_profile():
    return jsonify(_service().profile(_user()))


@workflow_bp.put("/api/workflow/profile")
def save_profile():
    user, payload = _user(), _json()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        if user["role"] == "jobseeker":
            version = con.execute("SELECT profile_version FROM users WHERE id=?", (user["id"],)).fetchone()[0] + 1
            resume = _resume(payload, version)
            con.execute("UPDATE users SET display_name=?,resume_json=?,profile_version=?,onboarding_complete=1 WHERE id=?",
                        (resume["display_name"], json.dumps(resume), version, user["id"]))
        else:
            company = {"name": _text(payload, "name", 140, required=True), "industry": _text(payload, "industry", 140, required=True),
                       "location": _text(payload, "location", 120, required=True), "description": _text(payload, "description", 2500),
                       "website": _https(_text(payload, "website", 500))}
            previous = con.execute("SELECT * FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
            changed = previous and any(previous[key] != value for key, value in company.items())
            con.execute("INSERT INTO companies(owner_id,name,industry,location,description,website) VALUES(?,?,?,?,?,?) ON CONFLICT(owner_id) DO UPDATE SET name=excluded.name,industry=excluded.industry,location=excluded.location,description=excluded.description,website=excluded.website",
                        (user["id"], company["name"], company["industry"], company["location"], company["description"], company["website"]))
            if changed and previous["verification_status"] not in {"unverified"}:
                reason = "Company profile changed; submit updated verification evidence."
                con.execute("UPDATE companies SET verification_status='unverified',verification_reason=?,verification_reviewed_at=NULL,registry_snapshot_json='{}',domain_snapshot_json='{}',domain_challenge_json='{}',verification_review_json='{}',verification_expires_at=NULL WHERE id=?", (reason, previous["id"]))
                con.execute("INSERT INTO verification_audit(company_id,actor_id,status,reason,created_at) VALUES(?,?,'unverified',?,?)", (previous["id"], user["id"], reason, _iso()))
                _verification_event(con, previous["id"], user["id"], "profile_changed", {"changed_fields": [key for key, value in company.items() if previous[key] != value], "reason": reason})
            con.execute("UPDATE users SET onboarding_complete=1 WHERE id=?", (user["id"],))
    return jsonify(_service().profile(_service().current_user()))


def _moderator():
    user = _user()
    if not _service().is_moderator(user):
        _fail("Moderator access is required.", 403)
    return user


@workflow_bp.put("/api/workflow/company/verification")
def submit_verification():
    user, payload = _user("hr"), _json()
    mode = _verification_mode()
    try:
        evidence = normalize_evidence(payload, mode=mode)
    except VerificationError as error:
        _fail(str(error))
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        original = con.execute("SELECT * FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
        if not original:
            _fail("Complete your company profile first.", 409)
        nonce = _provider_attempt(con, original["id"], mode, "registry")
    snapshot = check_registry(evidence, mode=mode, now=_now(), ttl_days=_verification_ttl())
    challenge = {"name": "_nextstep-verification." + evidence["domain"], "token": secrets.token_urlsafe(32),
                 "expires_at": _iso(_now() + timedelta(minutes=_challenge_minutes())), "simulation": mode == "synthetic",
                 "instructions": "Enter this token to run the explicit simulated DNS challenge. No email is sent." if mode == "synthetic" else "Publish this exact token in a TXT record at the challenge name, then check DNS. No email is sent."}
    reason = "Registry lookup unavailable; approval is blocked until a fresh successful registry check." if snapshot["status"] == "unavailable" else ""
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        company = con.execute("SELECT * FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
        if not _verification_unchanged(company, original) or not _current_attempt(con, original["id"], "registry", nonce):
            _fail("Company evidence, profile or review changed during verification. Submit the current evidence again.", 409)
        con.execute("UPDATE companies SET registration_number=?,recruiter_identity=?,evidence_note=?,verification_mode=?,verification_evidence_json=?,registry_snapshot_json=?,domain_snapshot_json='{}',domain_challenge_json=?,verification_review_json='{}',verification_expires_at=NULL,verification_status='pending',verification_reason=?,verification_submitted_at=?,verification_reviewed_at=NULL WHERE id=?",
                    (evidence["registration_number"], evidence["recruiter_email"], evidence["evidence_note"], mode, json.dumps(evidence), json.dumps(snapshot), json.dumps(challenge), reason, _iso(), company["id"]))
        _verification_event(con, company["id"], user["id"], "submission", {"mode": mode, "evidence": evidence, "registry": snapshot})
        con.execute("INSERT INTO verification_audit(company_id,actor_id,status,reason,created_at) VALUES(?,?,'pending',?,?)", (company["id"], user["id"], "Structured evidence submitted; registry, domain and independent authorization review are required.", _iso()))
        for moderator in con.execute("SELECT user_id FROM moderator_accounts WHERE user_id<>?", (user["id"],)):
            _notify(con, moderator["user_id"], "verification", f"Verification requested: {company['name']}")
        result = _service().company(con, user["id"])
    return jsonify(company=result)


@workflow_bp.get("/api/workflow/verification/capabilities")
def verification_capabilities():
    mode = _verification_mode()
    return jsonify(mode=mode, simulation=mode == "synthetic", fixture={**SYNTHETIC_FIXTURE, "evidence_note": "Fictional recruiter authorization for the hackathon demonstration; use public or synthetic references only."},
                   moderator_demo_available=mode == "synthetic" and bool(current_app.config.get("ENABLE_MODERATOR_DEMO", True)),
                   live_check_cooldown_seconds=30 if mode == "gleif" else 0,
                   publishing_requires_verification=bool(current_app.config.get("REQUIRE_EMPLOYER_VERIFICATION", True)),
                   limitations=["Synthetic mode uses a fixed fictional registry record and an explicit simulated DNS challenge.",
                                "GLEIF mode checks public LEI records, not Malaysia's SSM registry, and requires control of the claimed DNS domain.",
                                "Registry and DNS results do not prove recruiter identity. An independent moderator must document authorization evidence for a fictional recruiter reference.",
                                "No personal documents, real recruiting or email delivery are supported."])


@workflow_bp.post("/api/workflow/company/verification/challenge")
def verify_company_domain():
    user, payload = _user("hr"), _json()
    mode = _verification_mode()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
        if not row or row["verification_status"] != "pending" or row["verification_mode"] != mode:
            _fail("Submit company evidence in the configured verification mode first.", 409)
        evidence, challenge = _stored_json(row, "verification_evidence_json"), _stored_json(row, "domain_challenge_json")
        if not challenge or not _fresh(challenge.get("expires_at")):
            _fail("The domain challenge expired. Submit the evidence again for a new token.", 409)
        if mode == "synthetic":
            token = _text(payload, "token", 160, required=True)
            if not hmac.compare_digest(token.encode(), challenge["token"].encode()):
                _fail("The synthetic challenge token does not match.", 400)
        nonce = _provider_attempt(con, row["id"], mode, "domain")
    snapshot = check_domain(evidence["domain"], challenge["token"], mode=mode, now=_now(), ttl_days=_verification_ttl())
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        current = con.execute("SELECT * FROM companies WHERE id=?", (row["id"],)).fetchone()
        if not _verification_unchanged(current, row) or not _current_attempt(con, row["id"], "domain", nonce) or not _fresh(challenge.get("expires_at")):
            _fail("Verification evidence changed or the challenge expired. Try the current challenge.", 409)
        con.execute("UPDATE companies SET domain_snapshot_json=? WHERE id=?", (json.dumps(snapshot), row["id"]))
        _verification_event(con, row["id"], user["id"], "domain_check", snapshot)
        result = _service().company(con, user["id"])
    return jsonify(company=result)


@workflow_bp.post("/api/workflow/company/verification/recheck")
def recheck_company_registry():
    user = _user("hr")
    _json()
    mode = _verification_mode()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
        if not row or not _stored_json(row, "verification_evidence_json") or row["verification_mode"] != mode:
            _fail("Submit company evidence in the configured verification mode first.", 409)
        evidence = _stored_json(row, "verification_evidence_json")
        nonce = _provider_attempt(con, row["id"], mode, "registry")
    snapshot = check_registry(evidence, mode=mode, now=_now(), ttl_days=_verification_ttl())
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        current = con.execute("SELECT * FROM companies WHERE id=?", (row["id"],)).fetchone()
        if not _verification_unchanged(current, row) or not _current_attempt(con, row["id"], "registry", nonce):
            _fail("Company evidence changed during lookup. Try again.", 409)
        reason = "Registry evidence rechecked; independent approval is required again."
        con.execute("UPDATE companies SET registry_snapshot_json=?,verification_status='pending',verification_reason=?,verification_reviewed_at=NULL,verification_review_json='{}',verification_expires_at=NULL WHERE id=?", (json.dumps(snapshot), reason, row["id"]))
        _verification_event(con, row["id"], user["id"], "registry_recheck", snapshot)
        con.execute("INSERT INTO verification_audit(company_id,actor_id,status,reason,created_at) VALUES(?,?,'pending',?,?)", (row["id"], user["id"], reason, _iso()))
        result = _service().company(con, user["id"])
    return jsonify(company=result)


@workflow_bp.get("/api/workflow/moderation")
def moderation_queue():
    _moderator()
    with _service().connection() as con:
        companies = [_service().company_view(con, row, private=True) for row in con.execute("SELECT * FROM companies ORDER BY CASE verification_status WHEN 'pending' THEN 0 ELSE 1 END,id DESC")]
        audit = [dict(row) for row in con.execute("SELECT id,company_id,status,reason,created_at FROM verification_audit ORDER BY id DESC LIMIT 100")]
        incidents = [dict(row) for row in con.execute("SELECT id,company_id,job_id,kind,detail,created_at FROM compliance_incidents ORDER BY id DESC LIMIT 100")]
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        overdue = [dict(row) for row in con.execute(f"SELECT a.id AS application_id,a.status,a.response_due_at AS due_at,a.escalated_at,j.id AS job_id,j.title AS job_title,c.id AS company_id,c.name AS company_name FROM applications a JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id WHERE a.status IN ({placeholders}) AND a.response_due_at<? ORDER BY a.response_due_at,a.id LIMIT 200", (*ACTIVE_STATUSES, _iso()))]
        evidence_events = [{key: row[key] for key in ("id", "company_id", "actor_id", "kind", "sha256", "created_at")} for row in con.execute("SELECT * FROM verification_evidence_events ORDER BY id DESC LIMIT 100")]
    return jsonify(companies=companies, audit=audit, evidence_events=evidence_events, incidents=incidents, overdue_applications=overdue, simulation=_verification_mode() == "synthetic")


@workflow_bp.patch("/api/workflow/moderation/companies/<int:identifier>")
def moderate_company(identifier):
    user, payload = _moderator(), _json()
    _positive_id(identifier, "Company ID")
    status = payload.get("status")
    if not _is_choice(status, {"verified", "rejected", "revoked"}):
        _fail("Choose verified, rejected or revoked.")
    reason = _text(payload, "reason", 1000, required=True)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM companies WHERE id=?", (identifier,)).fetchone()
        if not row:
            _fail("Company not found.", 404)
        if row["owner_id"] == user["id"]:
            _fail("A moderator cannot review their own company.", 403)
        if status == "revoked" and row["verification_status"] != "verified":
            _fail("Only a previously verified company can have its approval revoked.", 409)
        if status != "revoked" and row["verification_status"] != "pending":
            _fail("Only a pending submission can be reviewed.", 409)
        review = {"moderator_id": user["id"], "decision": status, "reason": reason, "reviewed_at": _iso()}
        expires = None
        if status == "verified":
            checks = ("registration_confirmed", "domain_control_confirmed", "recruiter_authorization_confirmed")
            if any(payload.get(key) is not True for key in checks):
                _fail("Explicitly confirm the registration match, domain control and recruiter authorization separately.")
            registry, domain = _stored_json(row, "registry_snapshot_json"), _stored_json(row, "domain_snapshot_json")
            if row["verification_mode"] != _verification_mode() or not _snapshot_matches(registry) or not _snapshot_matches(domain):
                _fail("Current successful registry and domain checks are required; unavailable, mismatched or expired evidence cannot be approved.", 409)
            evidence = _stored_json(row, "verification_evidence_json")
            for other in con.execute("SELECT * FROM companies WHERE id<>? AND verification_mode=? AND verification_status='verified'", (identifier, row["verification_mode"])):
                other_claim = _stored_json(other, "verification_evidence_json")
                duplicate = other_claim.get("lei") == evidence["lei"] or (other_claim.get("country") == evidence["country"] and other_claim.get("registration_number") == evidence["registration_number"])
                if duplicate and _verification_view(other)["can_publish"]:
                    _fail("This legal entity already has a current approval under another company account. An independent moderator must revoke that approval before a transfer can be reviewed.", 409)
            reference = _https(_text(payload, "authorization_reference", 500, required=True), required=True)
            hostname = urlsplit(reference).hostname or ""
            if hostname != evidence["domain"] and not hostname.endswith("." + evidence["domain"]):
                _fail("Use a public authorization reference on the verified company domain.")
            note = _text(payload, "authorization_note", 1500, required=True)
            if len(note) < 20:
                _fail("Document the independent public authorization evidence reviewed (at least 20 characters).")
            review.update({key: True for key in checks})
            review.update(authorization_reference=reference, authorization_note=note)
            expires = min(registry["expires_at"], domain["expires_at"], _iso(_now() + timedelta(days=_verification_ttl())))
        con.execute("UPDATE companies SET verification_status=?,verification_reason=?,verification_reviewed_at=?,verification_review_json=?,verification_expires_at=? WHERE id=?", (status, reason, _iso(), json.dumps(review), expires, identifier))
        _verification_event(con, identifier, user["id"], "moderator_review", review)
        con.execute("INSERT INTO verification_audit(company_id,actor_id,status,reason,created_at) VALUES(?,?,?,?,?)", (identifier, user["id"], status, reason, _iso()))
        _notify(con, row["owner_id"], "verification", f"Company verification {status}: {reason}")
        result = _service().company_view(con, con.execute("SELECT * FROM companies WHERE id=?", (identifier,)).fetchone(), private=True)
    return jsonify(company=result, simulation=_verification_mode() == "synthetic")


@workflow_bp.get("/api/workflow/jobs")
def jobs():
    service, user = _service(), _service().current_user()
    profile = service.profile(user)["resume"] if user and user["role"] == "jobseeker" else None
    if not user or user["role"] != "jobseeker":
        raw = request.args.get("skills", "")
        if len(raw) > 1000:
            _fail("Skill filter is too long.")
        try:
            weekly_hours = int(request.args.get("weekly_hours", "6"))
        except (ValueError, TypeError):
            _fail("Weekly learning hours must be a whole number from 1 to 40.")
        if not 1 <= weekly_hours <= 40:
            _fail("Weekly learning hours must be a whole number from 1 to 40.")
        profile = {"skills": _skills(raw.split(",") if raw else []), "weekly_hours": weekly_hours}
    search = request.args.get("search", "").strip().casefold()
    location = request.args.get("location", "").strip().casefold()
    mode = request.args.get("work_mode", "")
    if mode and mode not in {"remote", "hybrid", "onsite"}:
        _fail("Choose remote, hybrid or onsite.")
    if len(search) > 200 or len(location) > 120:
        _fail("Search filter is too long.")
    mine = request.args.get("mine") == "1"
    sorting = request.args.get("sort", "newest" if mine else "match")
    if sorting not in {"match", "newest"}:
        _fail("Choose match or newest ordering.")
    if mine:
        _user("hr")
    with service.connection() as con:
        if mine:
            rows = con.execute("SELECT j.* FROM jobs j JOIN companies c ON c.id=j.company_id WHERE c.owner_id=? ORDER BY j.id DESC", (user["id"],)).fetchall()
        else:
            rows = con.execute("SELECT * FROM jobs WHERE salary_min>0 AND salary_max>=salary_min ORDER BY id DESC").fetchall()
        items = []
        for row in rows:
            application = con.execute("SELECT id,status FROM applications WHERE job_id=? AND applicant_id=?", (row["id"], user["id"])).fetchone() if user and user["role"] == "jobseeker" else None
            item = service.job_view(con, row, profile, application)
            text = " ".join([item["title"], item["description"], item["company"]["name"], *[skill["name"] for skill in item["required_skills"]]]).casefold()
            if search and search not in text or location and location not in item["location"].casefold() or mode and item["work_mode"] != mode:
                continue
            items.append(item)
    if sorting == "match":
        items.sort(key=lambda item: (-item["match"]["percentage"], -item["id"]))
    return jsonify(jobs=items, profile=profile, sort=sorting)


def _owned_job(con, identifier, user):
    _positive_id(identifier, "Job ID")
    row = con.execute("SELECT j.* FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=? AND c.owner_id=?", (identifier, user["id"])).fetchone()
    if not row:
        _fail("Job not found in your company.", 404)
    return row


def _salary_for_owner(payload, user):
    try:
        return _salary(payload)
    except WorkflowError:
        # Save a transparent policy incident independently of the rejected job
        # transaction, so rejecting invalid pay cannot silently erase a penalty.
        with _service().connection() as con:
            company = con.execute("SELECT id FROM companies WHERE owner_id=?", (user["id"],)).fetchone()
            if company:
                con.execute("INSERT INTO compliance_incidents(company_id,kind,detail,created_at) VALUES(?,'invalid_salary','A vacancy submission was rejected because its base salary range was missing or invalid.',?)", (company["id"], _iso()))
                _notify(con, user["id"], "compliance", "Vacancy rejected: supply a valid base salary range. Accountability score reduced by 10.")
        raise


@workflow_bp.post("/api/workflow/jobs")
def create_job():
    user, payload = _user("hr"), _json()
    if not user["onboarding_complete"]:
        _fail("Complete your company profile before posting a job.", 409)
    title = _text(payload, "title", 160, required=True)
    description = _text(payload, "description", 3000, required=True)
    location = _text(payload, "location", 120, required=True)
    role_id = payload.get("role_id")
    if not _is_choice(role_id, ROLE_MAP):
        _fail("Select a role from the catalogue.")
    required = _skills(payload.get("required_skills", []), required=True)
    mode = payload.get("work_mode")
    employment = payload.get("employment_type")
    if not _is_choice(mode, {"remote", "hybrid", "onsite"}) or not _is_choice(employment, {"full-time", "part-time", "internship"}):
        _fail("Select a valid work arrangement and employment type.")
    try:
        deadline = date.fromisoformat(payload.get("deadline", ""))
    except (TypeError, ValueError):
        _fail("Enter a valid application deadline.")
    if deadline <= _today() or deadline == date.max:
        _fail("Application deadline must be after today.")
    salary = _salary_for_owner(payload, user)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        company = _service().company(con, user["id"])
        if not company:
            _fail("Complete your company profile first.", 409)
        _publishing_allowed(company)
        cursor = con.execute("INSERT INTO jobs(company_id,title,role_id,description,location,work_mode,employment_type,required_skills_json,deadline,created_at,salary_min,salary_max,salary_currency,salary_period) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (company["id"], title, role_id, description, location, mode, employment, json.dumps(required), deadline.isoformat(), _iso(), *salary))
        row = con.execute("SELECT * FROM jobs WHERE id=?", (cursor.lastrowid,)).fetchone()
        result = _service().job_view(con, row)
    return jsonify(job=result), 201


@workflow_bp.patch("/api/workflow/jobs/<int:identifier>")
def change_job(identifier):
    user, payload = _user("hr"), _json()
    with _service().connection() as con:
        previous = _owned_job(con, identifier, user)
    status = payload.get("status", previous["status"])
    if not _is_choice(status, {"open", "closed"}):
        _fail("Choose open or closed.")
    salary_payload = {key: payload.get(key, previous[key]) for key in ("salary_min", "salary_max", "salary_currency", "salary_period")}
    salary = _salary_for_owner(salary_payload, user)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = _owned_job(con, identifier, user)
        if status == "open" and date.fromisoformat(row["deadline"]) < _today():
            _fail("An expired job cannot be reopened.", 409)
        if status == "open":
            _publishing_allowed(_service().company(con, user["id"]))
        con.execute("UPDATE jobs SET status=?,salary_min=?,salary_max=?,salary_currency=?,salary_period=? WHERE id=?", (status, *salary, identifier))
        result = _service().job_view(con, con.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone())
    return jsonify(job=result)


def _application_rows(con, user):
    if user["role"] == "jobseeker":
        return con.execute("SELECT * FROM applications WHERE applicant_id=? ORDER BY updated_at DESC,id DESC", (user["id"],)).fetchall()
    return con.execute("SELECT a.* FROM applications a JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id WHERE c.owner_id=? ORDER BY a.updated_at DESC,a.id DESC", (user["id"],)).fetchall()


def _owned_application(con, identifier, user):
    _positive_id(identifier, "Application ID")
    condition = "a.applicant_id=?" if user["role"] == "jobseeker" else "c.owner_id=?"
    row = con.execute("SELECT a.* FROM applications a JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id WHERE a.id=? AND " + condition,
                      (identifier, user["id"])).fetchone()
    if not row:
        _fail("Application not found in your account.", 404)
    return row


@workflow_bp.get("/api/workflow/applications")
def applications():
    user = _user()
    with _service().connection() as con:
        rows = _application_rows(con, user)
        items = [_service().application_view(con, row) for row in rows]
    return jsonify(applications=items, pending_count=sum(item["status"] in ACTIVE_STATUSES for item in items))


@workflow_bp.post("/api/workflow/applications/<int:identifier>/viewed")
def mark_viewed(identifier):
    user = _user("hr")
    _json()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = _owned_application(con, identifier, user)
        if not row["viewed_at"]:
            status = "viewed" if row["status"] == "submitted" else row["status"]
            con.execute("UPDATE applications SET viewed_at=?,status=?,updated_at=? WHERE id=?", (_iso(), status, _iso() if status != row["status"] else row["updated_at"], identifier))
            _event(con, identifier, "viewed", user["id"], "Recruiter opened the submitted profile.")
            _notify(con, row["applicant_id"], "application", "Your application has been viewed by the recruiter.", identifier)
        result = _service().application_view(con, con.execute("SELECT * FROM applications WHERE id=?", (identifier,)).fetchone())
    return jsonify(application=result)


def _escalate_overdue(con, user=None):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    scope, arguments = "", []
    if user:
        scope = " AND " + ("a.applicant_id=?" if user["role"] == "jobseeker" else "c.owner_id=?")
        arguments = [user["id"]]
    rows = con.execute(f"SELECT a.*,c.owner_id FROM applications a JOIN jobs j ON j.id=a.job_id JOIN companies c ON c.id=j.company_id WHERE a.status IN ({placeholders}) AND a.response_due_at<? AND a.escalated_at IS NULL" + scope,
                       (*ACTIVE_STATUSES, _iso(), *arguments)).fetchall()
    for row in rows:
        changed = con.execute("UPDATE applications SET escalated_at=? WHERE id=? AND escalated_at IS NULL", (_iso(), row["id"])).rowcount
        if not changed:
            continue
        for recipient in {row["applicant_id"], row["owner_id"]}:
            _notify(con, recipient, "sla", "The application response deadline has passed. This delay is recorded and has been escalated for review.", row["id"])
        for moderator in con.execute("SELECT user_id FROM moderator_accounts"):
            _notify(con, moderator["user_id"], "sla", "An employer response deadline has been missed; review employer accountability.", row["id"])


@workflow_bp.get("/api/workflow/updates")
def workflow_updates():
    user = _user()
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        _escalate_overdue(con, user)
        notifications = [dict(row) for row in con.execute("SELECT id,kind,title,application_id,created_at,read_at FROM workflow_notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],))]
        for notification in notifications:
            notification["view"] = "messages" if notification["kind"] == "message" else "moderation" if user.get("is_moderator") and notification["kind"] in {"verification", "sla"} else "applicants" if user["role"] == "hr" else "applications"
        unread = con.execute("SELECT COUNT(*) FROM workflow_notifications WHERE user_id=? AND read_at IS NULL", (user["id"],)).fetchone()[0]
        rows = _application_rows(con, user)
        state = [(row["id"], row["status"], row["updated_at"], row["viewed_at"], row["escalated_at"], row["decision_reason"]) for row in rows]
        events = [con.execute("SELECT COALESCE(MAX(id),0) FROM application_events WHERE application_id=?", (row["id"],)).fetchone()[0] for row in rows]
        company = _service().company(con, user["id"]) if user["role"] == "hr" else None
        revision = hashlib.sha256(json.dumps([state, events, notifications, company], sort_keys=True).encode()).hexdigest()[:20]
    return jsonify(revision=revision, unread_count=unread, notifications=notifications)


@workflow_bp.patch("/api/workflow/notifications/read")
def read_notifications():
    user, payload = _user(), _json()
    if payload.get("all") is True:
        with _service().connection() as con:
            con.execute("UPDATE workflow_notifications SET read_at=COALESCE(read_at,?) WHERE user_id=?", (_iso(), user["id"]))
        return jsonify(updated=True)
    identifiers = payload.get("ids")
    if not isinstance(identifiers, list) or len(identifiers) > 100 or any(isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2**63 - 1 for value in identifiers):
        _fail("Select at most 100 valid notification IDs.")
    with _service().connection() as con:
        for identifier in set(identifiers):
            con.execute("UPDATE workflow_notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND user_id=?", (_iso(), identifier, user["id"]))
    return jsonify(updated=True)


@workflow_bp.post("/api/workflow/applications")
def apply():
    user, payload = _user("jobseeker"), _json()
    identifier = _positive_id(payload.get("job_id"), "Job ID")
    if not user["onboarding_complete"]:
        _fail("Complete your resume profile before applying.", 409)
    try:
        with _service().connection() as con:
            con.execute("BEGIN IMMEDIATE")
            job = con.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
            if not job:
                _fail("Job not found.", 404)
            if job["status"] != "open" or date.fromisoformat(job["deadline"]) < _today():
                _fail("This job is closed or its application deadline has passed.", 409)
            row = con.execute("SELECT resume_json,profile_version FROM users WHERE id=?", (user["id"],)).fetchone()
            if not row["resume_json"]:
                _fail("Complete your resume profile before applying.", 409)
            cursor = con.execute("INSERT INTO applications(job_id,applicant_id,resume_json,resume_version,created_at,updated_at,response_due_at) VALUES(?,?,?,?,?,?,?)",
                                 (identifier, user["id"], row["resume_json"], row["profile_version"], _iso(), _iso(), _iso(_now() + timedelta(days=_service().sla_days))))
            saved = con.execute("SELECT * FROM applications WHERE id=?", (cursor.lastrowid,)).fetchone()
            _event(con, saved["id"], "submitted", user["id"], "Application sent with a saved resume snapshot.")
            _notify_application(con, saved, user["id"], "A new candidate application is ready for review.")
            result = _service().application_view(con, saved)
    except sqlite3.IntegrityError:
        _fail("You have already applied to this job.", 409)
    return jsonify(application=result), 201


@workflow_bp.patch("/api/workflow/applications/<int:identifier>")
def decide_application(identifier):
    user, payload = _user(), _json()
    status = payload.get("status")
    allowed = {"withdrawn"} if user["role"] == "jobseeker" else {"under_review", "shortlisted", "accepted", "rejected"}
    if not _is_choice(status, allowed):
        _fail("This application status change is not available for your account.", 403)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = _owned_application(con, identifier, user)
        reason = _text(payload, "reason", 1500, required=status in {"accepted", "rejected"})
        if row["status"] in TERMINAL_STATUSES and row["status"] != status:
            _fail("This application has already reached a final status.", 409)
        if row["status"] in TERMINAL_STATUSES and row["status"] == status:
            if status in {"accepted", "rejected"} and row["decision_reason"] != reason:
                _fail("A final decision and its reason cannot be rewritten.", 409)
            return jsonify(application=_service().application_view(con, row))
        # A scheduled invitation must be cancelled explicitly or resolved by a
        # final decision, rather than silently leaving a misleading calendar item.
        if row["status"] == "interview_scheduled" and status in {"under_review", "shortlisted"}:
            _fail("Cancel the scheduled interview before changing its review status.", 409)
        con.execute("UPDATE applications SET status=?,updated_at=?,decision_reason=? WHERE id=?", (status, _iso(), reason if status in {"accepted", "rejected"} else row["decision_reason"], identifier))
        _event(con, identifier, status, user["id"], reason)
        _notify_application(con, row, user["id"], f"Application {status.replace('_', ' ')}" + (f": {reason}" if reason else "."))
        if status in TERMINAL_STATUSES:
            con.execute("UPDATE interviews SET status='cancelled' WHERE application_id=? AND status IN ('scheduled','confirmed')", (identifier,))
        result = _service().application_view(con, con.execute("SELECT * FROM applications WHERE id=?", (identifier,)).fetchone())
    return jsonify(application=result)


@workflow_bp.post("/api/workflow/applications/<int:identifier>/interview")
def schedule_interview(identifier):
    user, payload = _user("hr"), _json()
    start_text = _text(payload, "start", 100, required=True)
    try:
        start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        if start.tzinfo is None or start.utcoffset() is None:
            _fail("Interview time must include a timezone offset.")
        start = start.astimezone(UTC)
    except (ValueError, OverflowError):
        _fail("Enter a valid interview date and timezone.")
    if start <= _now():
        _fail("Interview time must be in the future.")
    duration = payload.get("duration_minutes", 30)
    if isinstance(duration, bool) or not isinstance(duration, int) or not 30 <= duration <= 180:
        _fail("Interview duration must be a whole number from 30 to 180 minutes.")
    generate_link = payload.get("generate_link", False)
    if not isinstance(generate_link, bool):
        _fail("Choose whether to generate a meeting link.")
    raw_link = _text(payload, "meeting_url", 1000)
    if generate_link and not raw_link:
        raw_link = "https://meet.jit.si/NextStep-Synthetic-" + secrets.token_urlsafe(24)
    meeting_url = _https(raw_link, required=True)
    notes = _text(payload, "notes", 1000)
    try:
        end = start + timedelta(minutes=duration)
    except OverflowError:
        _fail("Interview date is outside the supported calendar range.")
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        application = _owned_application(con, identifier, user)
        if application["status"] in TERMINAL_STATUSES:
            _fail("A finalised application cannot receive an interview.", 409)
        conflict = con.execute("""SELECT i.id FROM interviews i
            JOIN applications a ON a.id=i.application_id JOIN jobs j ON j.id=a.job_id
            JOIN companies c ON c.id=j.company_id
            WHERE i.application_id<>? AND i.status IN ('scheduled','confirmed')
            AND i.start < ? AND i.end > ? AND (a.applicant_id=? OR c.owner_id=?) LIMIT 1""",
            (identifier, _iso(end), _iso(start), application["applicant_id"], user["id"])).fetchone()
        if conflict:
            _fail("This time overlaps an existing candidate or company interview.", 409)
        con.execute("INSERT INTO interviews(application_id,start,end,meeting_url,notes,status) VALUES(?,?,?,?,?,'scheduled') ON CONFLICT(application_id) DO UPDATE SET start=excluded.start,end=excluded.end,meeting_url=excluded.meeting_url,notes=excluded.notes,status='scheduled'",
                    (identifier, _iso(start), _iso(end), meeting_url, notes))
        con.execute("UPDATE applications SET status='interview_scheduled',updated_at=? WHERE id=?", (_iso(), identifier))
        _event(con, identifier, "interview_scheduled", user["id"], "Online interview invitation scheduled in the app.")
        _notify_application(con, application, user["id"], "You have an online interview invitation. Open your calendar to confirm and join.")
        result = _service().application_view(con, con.execute("SELECT * FROM applications WHERE id=?", (identifier,)).fetchone())
    return jsonify(application=result)


@workflow_bp.patch("/api/workflow/interviews/<int:identifier>")
def interview_response(identifier):
    user, payload = _user(), _json()
    _positive_id(identifier, "Interview ID")
    status = payload.get("status")
    allowed = {"confirmed", "cancelled"} if user["role"] == "jobseeker" else {"cancelled"}
    if not _is_choice(status, allowed):
        _fail("Choose a permitted interview response.", 403)
    with _service().connection() as con:
        con.execute("BEGIN IMMEDIATE")
        interview = con.execute("SELECT * FROM interviews WHERE id=?", (identifier,)).fetchone()
        if not interview:
            _fail("Interview not found.", 404)
        application = _owned_application(con, interview["application_id"], user)
        if interview["status"] == "cancelled" or application["status"] in TERMINAL_STATUSES:
            _fail("This interview is no longer active.", 409)
        if status == "confirmed" and datetime.fromisoformat(interview["start"].replace("Z", "+00:00")) <= _now():
            _fail("A past interview cannot be confirmed.", 409)
        con.execute("UPDATE interviews SET status=? WHERE id=?", (status, identifier))
        if status == "cancelled":
            con.execute("UPDATE applications SET status='under_review',updated_at=? WHERE id=?", (_iso(), application["id"]))
        _event(con, application["id"], "under_review" if status == "cancelled" else application["status"], user["id"], f"Interview {status}.")
        _notify_application(con, application, user["id"], f"Interview {status}.")
        result = _service().application_view(con, con.execute("SELECT * FROM applications WHERE id=?", (application["id"],)).fetchone())
    return jsonify(application=result)


def _calendar_events(user):
    service, events = _service(), []
    with service.connection() as con:
        rows = _application_rows(con, user)
        for row in rows:
            item = service.application_view(con, row)
            interview = item["interview"]
            if interview:
                events.append({"id": f"interview-{interview['id']}", "type": "interview",
                               "title": f"Interview · {item['job']['title']}" + (f" · {item['applicant']['display_name']}" if user["role"] == "hr" else ""),
                               "start": interview["start"], "end": interview["end"], "meeting_url": interview["meeting_url"],
                               "application_id": row["id"], "job_id": item["job"]["id"], "status": interview["status"], "timezone": "Asia/Kuala_Lumpur"})
        if user["role"] == "hr":
            deadlines = con.execute("SELECT j.* FROM jobs j JOIN companies c ON c.id=j.company_id WHERE c.owner_id=? AND j.status='open'", (user["id"],)).fetchall()
            deadline_apps = {}
        else:
            active = [row for row in rows if row["status"] in ACTIVE_STATUSES]
            deadline_apps = {row["job_id"]: row["id"] for row in active}
            deadlines = [con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone() for job_id in deadline_apps]
        for job in deadlines:
            # Date-only deadlines are all-day events. ISO dates remain unshifted
            # in the UI and export; interview times are normalised to UTC.
            end = date.fromisoformat(job["deadline"]) + timedelta(days=1)
            events.append({"id": f"deadline-{job['id']}", "type": "deadline", "title": f"Application deadline · {job['title']}",
                           "start": job["deadline"], "end": end.isoformat(), "meeting_url": "",
                           "application_id": deadline_apps.get(job["id"]), "job_id": job["id"], "status": "scheduled", "timezone": "Asia/Kuala_Lumpur"})
    return sorted(events, key=lambda value: (value["start"], value["id"]))


@workflow_bp.get("/api/workflow/calendar")
def calendar():
    return jsonify(events=_calendar_events(_user()))


def _ics_text(value):
    return str(value).replace("\\", "\\\\").replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold_ics(line):
    # iCalendar folds at 75 octets, not characters; don't split UTF-8 bytes.
    pieces, current, size = [], "", 0
    for char in line:
        length = len(char.encode("utf-8"))
        if size + length > 74:
            pieces.append(current)
            current, size = " ", 1
        current += char
        size += length
    pieces.append(current)
    return "\r\n".join(pieces)


@workflow_bp.get("/api/workflow/calendar.ics")
def calendar_download():
    events = _calendar_events(_user())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NextStep//Synthetic Career Demo//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    for event in events:
        lines.extend(["BEGIN:VEVENT", f"UID:{event['id']}@nextstep.invalid", f"DTSTAMP:{stamp}", f"SUMMARY:{_ics_text(event['title'])}"])
        if event["type"] == "deadline":
            lines.extend(["DTSTART;VALUE=DATE:" + event["start"].replace("-", ""), "DTEND;VALUE=DATE:" + event["end"].replace("-", "")])
        else:
            for label, key in (("DTSTART", "start"), ("DTEND", "end")):
                value = datetime.fromisoformat(event[key].replace("Z", "+00:00")).astimezone(UTC)
                lines.append(f"{label}:{value.strftime('%Y%m%dT%H%M%SZ')}")
            lines.append("URL:" + _ics_text(event["meeting_url"]))
            lines.append("STATUS:" + ("CANCELLED" if event["status"] == "cancelled" else "CONFIRMED" if event["status"] == "confirmed" else "TENTATIVE"))
        lines.extend(["DESCRIPTION:Synthetic NextStep demonstration. No email invitation has been sent.", "END:VEVENT"])
    lines.append("END:VCALENDAR")
    content = "\r\n".join(_fold_ics(line) for line in lines) + "\r\n"
    return Response(content, mimetype="text/calendar", headers={"Content-Disposition": 'attachment; filename="nextstep-calendar.ics"'})
