"""Flask entry point. Run: python app.py (development only, no debug console)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import tempfile

from flask import Flask, jsonify, render_template, request, session
from werkzeug.exceptions import HTTPException

from career.catalog import PROFILES, ROLES, SDGS, SKILLS
from career.recommendations import build_radar, match_profile
from career.sources import SourceStore
from career.validation import validate_profile

ROOT = Path(__file__).resolve().parent


def persistent_session_secret(directory):
    """Keep signed sessions valid after restart without checking a key into Git."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "session-secret"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        value = path.read_text(encoding="utf-8").strip()
        if len(value) < 64:
            raise RuntimeError("The local session key is invalid. Restore instance/session-secret before starting.")
        return value
    value = secrets.token_hex(32)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(value)
    return value


def configured_moderator_ids():
    raw = os.environ.get("NEXTSTEP_MODERATOR_USER_IDS", "").strip()
    if not raw:
        return []
    identifiers = []
    for part in raw.split(","):
        value = part.strip()
        if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 2**63 - 1:
            raise ValueError("NEXTSTEP_MODERATOR_USER_IDS must contain comma-separated positive user IDs.")
        identifiers.append(int(value))
    return list(dict.fromkeys(identifiers))


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=16 * 1024, JSON_SORT_KEYS=False,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("NEXTSTEP_SECURE_COOKIES") == "1",
        EMPLOYER_VERIFICATION_MODE=os.environ.get("NEXTSTEP_VERIFICATION_MODE", "synthetic"),
        EMPLOYER_VERIFICATION_TTL_DAYS=int(os.environ.get("NEXTSTEP_VERIFICATION_TTL_DAYS", "30")),
        EMPLOYER_DOMAIN_CHALLENGE_MINUTES=int(os.environ.get("NEXTSTEP_DOMAIN_CHALLENGE_MINUTES", "30")),
        REQUIRE_EMPLOYER_VERIFICATION=os.environ.get("NEXTSTEP_REQUIRE_VERIFIED_EMPLOYERS", "1") != "0",
        MODERATOR_USER_IDS=configured_moderator_ids(),
    )
    if test_config:
        app.config.update(test_config)
    if app.testing:
        app.config.setdefault("SECRET_KEY", "")
        if not app.config.get("SECRET_KEY"):
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        if not app.config.get("WORKFLOW_DATABASE"):
            temporary = tempfile.TemporaryDirectory(prefix="nextstep-test-")
            app.extensions["workflow_tempdir"] = temporary
            app.config["WORKFLOW_DATABASE"] = str(Path(temporary.name) / "workflow.sqlite3")
    else:
        app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or persistent_session_secret(ROOT / "instance")
        app.config.setdefault("WORKFLOW_DATABASE", str(ROOT / "instance/workflow.sqlite3"))
    store = app.config.get("SOURCE_STORE") or SourceStore(ROOT / "instance/signals.json", ROOT / "data/signals_seed.json")
    app.extensions["sources"] = store
    from career.workflow import init_workflow, workflow_bp
    init_workflow(app)
    app.register_blueprint(workflow_bp)
    from career.communication import init_communication, communication_bp
    init_communication(app)
    app.register_blueprint(communication_bp)
    from career.monitor import init_monitor, start_monitor
    init_monitor(app)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return error

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", app="NextStep", evidence_available=bool(store.snapshot()["jobs"]))

    @app.get("/api/catalog")
    def catalog():
        return jsonify(skills=SKILLS, roles=ROLES, sdgs=SDGS, profiles=PROFILES)

    def scenario_value(raw):
        if raw not in ("moderate", "fast"):
            raise ValueError("Choose the moderate or fast scenario.")
        return raw

    @app.get("/api/radar")
    def radar():
        try:
            scenario = scenario_value(request.args.get("scenario", "moderate"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(build_radar(store.snapshot(), scenario))

    @app.post("/api/signals/refresh")
    def refresh():
        payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(payload, dict):
            return jsonify(error="Send a JSON object."), 400
        try:
            scenario = scenario_value(payload.get("scenario", request.args.get("scenario", "moderate")))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        snapshot, attempted = store.refresh()
        result = build_radar(snapshot, scenario)
        result["refresh_attempted"] = attempted
        return jsonify(result), 200 if snapshot["jobs"] else 503

    @app.post("/api/match")
    def match():
        if not request.is_json:
            return jsonify(error="Send application/json."), 415
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Send a JSON object."), 400
        try:
            profile = validate_profile(payload)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(match_profile(profile, store.snapshot()))

    @app.get("/api/exposure")
    def exposure():
        from career.assistant import role_exposure
        role_id = request.args.get("role_id", "")
        try:
            if role_id not in {role["id"] for role in ROLES}:
                raise ValueError("Choose a role from the supplied catalog.")
            scenario = scenario_value(request.args.get("scenario", "moderate"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(role_exposure(role_id, scenario))

    @app.get("/api/exposure/evidence")
    def exposure_evidence():
        from career.exposure import build_exposure_evidence
        role_id = request.args.get("role_id", "")
        if role_id not in {role["id"] for role in ROLES}:
            return jsonify(error="Choose a role from the supplied catalog."), 400
        return jsonify(build_exposure_evidence(role_id))

    @app.get("/api/exposure/methodology")
    def exposure_methodology():
        from career.exposure import exposure_methodology as methodology
        return jsonify(methodology())

    @app.get("/api/exposure/report/<role_id>")
    def exposure_report(role_id):
        from career.exposure import build_exposure_evidence, exposure_methodology
        role = next((item for item in ROLES if item["id"] == role_id), None)
        if role is None:
            return jsonify(error="Choose a role from the supplied catalog."), 400
        response = jsonify({
            "report_type": "public_occupational_research_evidence",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "role": {key: role[key] for key in ("id", "title", "sdgs", "source_url")},
            "research_evidence": build_exposure_evidence(role_id),
            "methodology": exposure_methodology(),
            "personal_job_loss_probability": None,
            "scope": "Public occupational research only. No personal profile is included, and no individual job-loss probability is inferred.",
        })
        response.headers["Content-Disposition"] = f'attachment; filename="nextstep-{role_id}-exposure-evidence.json"'
        return response

    @app.post("/api/assistant")
    def assistant():
        from career.llm import enhanced_reply
        payload = request.get_json(silent=True)
        try:
            if not request.is_json or not isinstance(payload, dict):
                raise ValueError("Send a JSON object.")
            message = payload.get("message", "")
            if not isinstance(message, str) or not 1 <= len(message.strip()) <= 1000:
                raise ValueError("Ask a question using 1 to 1,000 characters.")
            supplied_profile = payload.get("profile", {})
            if not isinstance(supplied_profile, dict):
                raise ValueError("The skills profile must be a JSON object.")
            profile = validate_profile({**supplied_profile, "scenario": payload.get("scenario", supplied_profile.get("scenario", "moderate"))})
            role_id = payload.get("role_id")
            if role_id is not None and (not isinstance(role_id, str) or role_id not in {role["id"] for role in ROLES}):
                raise ValueError("Choose a role from the supplied catalog.")
            for field in ("use_model", "external_consent"):
                if field in payload and not isinstance(payload[field], bool):
                    raise ValueError(f"{field.replace('_', ' ').capitalize()} must be true or false.")
            if payload.get("use_model") and not payload.get("external_consent"):
                raise ValueError("Consent is required before sending this question to the external language model.")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        user = app.extensions["workflow"].current_user()
        actor_role = user["role"] if user else "guest"
        if payload.get("use_model"):
            supplied = request.headers.get("X-CSRF-Token", "")
            expected = session.get("csrf_token", "")
            if not supplied or not expected or not secrets.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
                return jsonify(error="Reload your session before using the optional online assistant."), 403
        return jsonify(enhanced_reply(
            message.strip(), profile, store.snapshot(), actor_role=actor_role,
            role_id=role_id, use_model=payload.get("use_model", False),
            consent=payload.get("external_consent", False),
        ))

    @app.post("/api/exposure/what-if")
    def exposure_what_if():
        from career.assistant import role_exposure
        payload = request.get_json(silent=True)
        try:
            if not request.is_json or not isinstance(payload, dict):
                raise ValueError("Send a JSON object.")
            role_id = payload.get("role_id")
            if not isinstance(role_id, str) or role_id not in {role["id"] for role in ROLES}:
                raise ValueError("Choose a role from the supplied catalog.")
            scenario = scenario_value(payload.get("scenario", "moderate"))
            result = role_exposure(role_id, scenario, payload.get("task_assumptions"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(result)

    @app.get("/api/assistant/capabilities")
    def assistant_capabilities():
        from career.llm import assistant_capabilities as capabilities
        return jsonify(capabilities())

    start_monitor(app)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NextStep development prototype")
    parser.add_argument("--refresh", action="store_true", help="Refresh public evidence and exit")
    parser.add_argument("--no-monitor", action="store_true", help="Disable background public-source refresh")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    args = parser.parse_args()
    app = create_app({"AUTO_REFRESH_ENABLED": False} if args.no_monitor or args.refresh else None)
    if args.refresh:
        data, _ = app.extensions["sources"].refresh(force=True)
        print(json.dumps(data["signal_status"], indent=2))
        raise SystemExit(0 if data["signal_status"]["status"] == "live" else 1)
    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    finally:
        from career.monitor import stop_monitor
        stop_monitor(app)
