import json
from contextlib import closing
import os
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import urlsplit

from flask import Flask, flash, redirect, render_template, request, session, url_for
from datetime import datetime


SECTIONS = ("experience", "education", "awards")


def current_year():
    return datetime.now().year


def profile_history(values, section):
    """Read new list values, or the earlier single-entry field format."""
    stored = values.get(section, [])
    if isinstance(stored, list) and (stored or section != "awards"):
        return [row for row in stored if isinstance(row, dict)]
    if section == "awards":
        return [
            {"year": str(values.get(f"award_{number}_year", "")),
             "description": values.get(f"award_{number}", "")}
            for number in range(1, 4)
            if values.get(f"award_{number}") or values.get(f"award_{number}_year")
        ]
    if isinstance(stored, str) and (stored or values.get(f"{section}_year")):
        return [{"year": str(values.get(f"{section}_year", "")), "description": stored}]
    return []


def register_profile_tables(app):
    """Call once from create_app(), after creating the Flask app."""
    @app.context_processor
    def table_context():
        return {"profile_year": current_year(), "profile_history": profile_history}


def read_profile_tables(form, year=None):
    """Read repeated HTML field names. Return (values, validation_errors)."""
    year = year or current_year()
    values = {"phone": form.get("phone", "").strip()}
    errors = {}
    phone = values["phone"]
    if phone and (
        len(phone) > 32
        or not re.fullmatch(r"\+?[0-9().\s-]+", phone)
        or not 7 <= len(re.sub(r"[^0-9]", "", phone)) <= 15
    ):
        errors["phone"] = "Enter a phone number with 7–15 digits, optionally starting with +."

    for section in SECTIONS:
        years = form.getlist(f"{section}_year")
        descriptions = form.getlist(f"{section}_description")
        rows = []
        if len(years) != len(descriptions):
            errors[section] = "Each row needs both a year field and a details field."
        for index in range(max(len(years), len(descriptions))):
            selected_year = years[index].strip() if index < len(years) else ""
            description = descriptions[index].strip() if index < len(descriptions) else ""
            if not selected_year and not description:
                continue
            rows.append({"year": selected_year, "description": description})
            upper_year = year + 6 if section == "education" else year
            if not re.fullmatch(r"[0-9]{4}", selected_year) or not 1900 <= int(selected_year) <= upper_year:
                errors[section] = "Choose a valid year for every filled row."
            elif not description or len(description) > 1000:
                errors[section] = "Enter details of 1–1,000 characters for every filled row."
        if section == "awards" and max(len(years), len(descriptions)) > 3:
            errors[section] = "Awards can have a maximum of 3 rows."
        values[section] = rows
    return values, errors


DEFAULT_PROFILE = {
    "name": "Alex Morgan",
    "role": "Product designer & creative thinker",
    "location": "Kuala Lumpur, Malaysia",
    "bio": "I turn complex problems into simple, thoughtful digital experiences. Currently exploring the space where good design meets everyday life.",
    "email": "hello@example.com",
    "phone": "",
    "status": "studying",
    "experience": [],
    "education": [],
    "awards": [],
    "linkedin": "",
    "skills": "Product design, UI / UX, Design systems, Prototyping, HTML & CSS",
    "available": True,
}

PROJECTS = [
    {"slug": "forma", "number": "01", "title": "Forma", "category": "Brand identity · Web design", "year": "2026", "description": "A quieter home for better living.", "detail": "An illustrative concept for a furniture studio. The exploration brings together a warm neutral palette, oversized typography, and an easy-to-browse collection. Replace this example with your own project and its process.", "tags": ["Visual design", "E-commerce"], "class": "forma"},
    {"slug": "bloom", "number": "02", "title": "Bloom", "category": "Product design · Mobile app", "year": "2026", "description": "Small habits. A little more balance.", "detail": "An illustrative wellbeing app concept focused on small, achievable routines. Soft colors and a simple daily check-in make the experience feel approachable. Replace this example with your own project and its process.", "tags": ["UI / UX", "Mobile"], "class": "bloom"},
]


def create_app(database=None, testing=False):
    app = Flask(__name__)
    register_profile_tables(app)
    app.config.update(
        SECRET_KEY=os.environ.get("PROFILE_SECRET_KEY") or secrets.token_hex(32),
        TESTING=testing,
        MAX_CONTENT_LENGTH=32 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE=str(database or Path(app.instance_path) / "profile.sqlite3"),
    )
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(app.config["DATABASE"])) as db:
        db.execute("CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL)")
        db.execute("INSERT OR IGNORE INTO profile (id, data) VALUES (1, ?)", (json.dumps(DEFAULT_PROFILE),))
        db.commit()

    @app.get("/")
    def mainpage():
        """Render the main landing page."""
        return render_template("mainpage.html")
    
    def read_profile():
        with closing(sqlite3.connect(app.config["DATABASE"])) as db:
            return json.loads(db.execute("SELECT data FROM profile WHERE id = 1").fetchone()[0])

    @app.get("/")
    def index():
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        profile = read_profile()
        initials = "".join(part[0] for part in profile["name"].split()[:2]).upper()
        return render_template("index.html", profile=profile, initials=initials, projects=PROJECTS, errors={}, form=profile, edit_open=False)

    @app.post("/profile")
    def update_profile():
        token = session.get("csrf_token", "")
        if not token or not secrets.compare_digest(token.encode(), request.form.get("csrf_token", "").encode()):
            return "This form has expired. Reload the profile page and try again.", 400
        limits = {
            "name": 70, "role": 100, "location": 100, "bio": 600,
            "email": 254, "linkedin": 300, "skills": 250, "phone": 32,
        }
        data = {key: request.form.get(key, "").strip() for key in limits}
        data["available"] = request.form.get("available") == "on"
        errors = {}
        table_values, table_errors = read_profile_tables(request.form)
        data.update(table_values)
        errors.update(table_errors)
        for key, limit in limits.items():
            if len(data[key]) > limit:
                errors[key] = f"Please use {limit} characters or fewer."
        for key in ("name", "role", "location", "bio"):
            if not data[key]:
                errors[key] = "Please fill in this field."
        data["status"] = request.form.get("status", "")

        allowed_statuses = {
            "studying",
            "fresh_graduate",
            "under_3_years",
            "3_to_10_years",
            "over_10_years",
        }

        if data["status"] not in allowed_statuses:
            errors["status"] = "Please choose a valid status."

        if data["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data["email"]):
            errors["email"] = "Please enter a valid email address."
        for key in ("linkedin",):
            if data[key]:
                try:
                    parsed = urlsplit(data[key])
                    valid = parsed.scheme in ("http", "https") and bool(parsed.hostname) and not parsed.username and not parsed.password and not any(c.isspace() for c in data[key])
                except ValueError:
                    valid = False
                if not valid:
                    errors[key] = "Please enter a complete http:// or https:// link."
        if len([s for s in data["skills"].split(",") if s.strip()]) > 12:
            errors["skills"] = "Please add up to 12 skills, separated by commas."
        if errors:
            profile = read_profile()
            initials = "".join(part[0] for part in profile["name"].split()[:2]).upper()
            return render_template("index.html", profile=profile, initials=initials, projects=PROJECTS, errors=errors, form=data, edit_open=True), 422
        with closing(sqlite3.connect(app.config["DATABASE"])) as db:
            db.execute("UPDATE profile SET data = ? WHERE id = 1", (json.dumps(data),))
            db.commit()
        flash("Your profile is all up to date.")
        return redirect(url_for("index"), code=303)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
        return response

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
