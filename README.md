# Folio — Python + HTML profile page

A responsive personal profile built with Flask, server-rendered HTML, CSS, a little JavaScript, and SQLite. Includes an editable profile, availability status, skills, contact links, and two clearly labeled sample project detail views. All visual assets are local; no external services, fonts, or API keys are needed.

## Run locally

Requires Python 3.10 or later. In a terminal in this folder:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. On macOS/Linux use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

Click **Edit profile** to update the demo name, role, location, biography, email, skills, links, and availability. SQLite saves changes in `instance/profile.sqlite3`, created automatically on first run. Close the app with Ctrl+C. Delete that database while the app is stopped to restore the demo profile.

## Customize

- `app.py`: initial demo details in `DEFAULT_PROFILE`, illustrative projects in `PROJECTS`, routes, validation, and database access.
- `templates/index.html`: page layout and edit form.
- `static/style.css`: colors, responsive layout, and project artwork.
- `static/app.js`: accessible modal dialogs and section navigation.

The default profile and both project concepts are illustrative. Contact uses `hello@example.com` until you replace it. Profile initials update automatically with your name. Project content is edited in `PROJECTS`; the profile editor handles personal details only. Changes to defaults affect newly created databases; use the form to update an existing profile.

## Checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover rendering, saving and persistence across app instances, validation, CSRF rejection, HTML escaping, and local assets. Test databases use temporary directories and do not change your profile.

## Deployment scope

This is a local, single-user starter. The edit form has CSRF protection and input validation, but there is no login system. Anyone who can access the server can edit the profile. It binds to `127.0.0.1` with Flask debug mode disabled. Add authentication and authorization, a production WSGI server, HTTPS, and secure cookies before exposing an editable deployment to the internet. Set `PROFILE_SECRET_KEY` to a persistent random value for deployment; by default a new secret is generated on each server start, invalidating previous sessions. Optional environment variable `PORT` changes the local port.
