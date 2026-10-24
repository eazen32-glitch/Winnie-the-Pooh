# Extracted screenshot section

This is the search, Skills/Roles tabs, signal filter, table, direction badges,
SDG badges and evidence links from your supplied SDC-main project. The sidebar,
page heading, other dashboard sections, accounts and recruitment features are
excluded. Your original project and virtual environments have not been modified.

## Preview

Double-click `preview.html`. It works without installing anything and uses the
original project's dated public snapshot. It does not perform live refreshes.
All skill and role rows are included, including rows below the screenshot crop.
Numbers can differ from a later running app snapshot; they are not hardcoded
from the screenshot.

For the Python version, from this extracted folder:

```powershell
python -m pip install -r requirements.txt
python run_demo.py
```

Open http://127.0.0.1:5051/skills-radar/ . To enable the original scheduled public
feed checks every 15 minutes, run `python run_demo.py --live`. Failed checks keep
the dated cache. Cached evidence is loaded immediately, with the first live
check scheduled about five seconds after startup. Browser status polling is
every 20 seconds; it is separate from the source refresh interval.

## Merge into another Flask project

1. Copy the entire `skills_radar` folder beside your other Python application's
   entry point. Install Flask if that application does not already use it.
2. After creating your Flask app, add:

   ```python
   from skills_radar import init_app
   init_app(app, auto_refresh=True)  # False for cached/offline operation
   ```

3. Add these assets in your existing template's head:

   ```html
   <link rel="stylesheet" href="{{ url_for('skills_radar.static', filename='radar.css') }}">
   <script src="{{ url_for('skills_radar.static', filename='radar.js') }}" defer></script>
   ```

4. Put this exactly where the screenshot section should appear:

   ```jinja2
   {% include 'radar-section.html' %}
   ```

The extracted component's CSS selectors start with `.skills-radar`, its DOM
queries stay inside its own section, and the API routes start with
`/skills-radar/`. It does not need the old whole-app `app.js` or `styles.css`.
Your other app's global CSS may still affect it; adjust the component styles
if your app defines more specific global rules.

## Use only the frontend, or reuse the original project's API

Copy the `<section ...>...</section>` from `preview.html` into your page, load
`radar.css` and `radar.js`, and remove the two Flask-only data attributes if you
copied the Jinja template instead. Provide either:

- Your API: add `data-radar-url="/api/radar"` and optionally
  `data-monitor-url="/api/monitor/status"` to the section. These match the
  original SDC project endpoints; use the same server origin.
- Local preview data: load `preview-data.js` before `radar.js`.
- Your own data: after the page loads, call
  `SkillsRadar.mount(document.querySelector('[data-skills-radar]')).setData(data)`.

Data must contain `skills` and `roles` arrays. Each item has `name` (skills) or
`title` (roles), `recent_count`, `previous_count`, `label`, `sdgs`, and `evidence`.
Labels are `stable`, `rising`, `declining`, or `insufficient`. Evidence entries
have `url`, `date`, and `kind` (`job` or `ai_release`). Optional top-level `sdgs`
provides goal titles/URLs; `signal_status.fetched_at` identifies snapshot time.

## Files

- `skills_radar/templates/radar-section.html`: only the requested HTML section.
- `skills_radar/static/radar.css`: relevant original styles, scoped to the section.
- `skills_radar/static/radar.js`: search, tabs, filtering, rendering, API polling.
- `skills_radar/engine.py`: extracted original counting and direction functions.
- `skills_radar/sources.py`: original public-feed ingestion and dated cache.
- `skills_radar/monitor.py`: original refresh worker without discovery routes.
- `skills_radar/catalog.json`: only the catalogue data the radar needs.
- `skills_radar/data/signals_seed.json`: original public fallback snapshot.
- `skills_radar/__init__.py`: small Flask integration adapter.

Runtime caches and the refresh-worker lease database are written beneath your
Flask app's `instance/skills_radar` folder. No source account database, session
secret, `.venv`, or private account data is included.

## Source and data attribution

Extracted from the supplied `templates/index.html`, `static/app.js`,
`static/styles.css`, and radar-related `career` modules. Rendering and API glue
were adapted to make this section independent. Feed attribution, timestamps,
count windows and original direction thresholds are retained.
The extracted source loader explicitly reads UTF-8 so Windows can load the
public snapshot correctly. The bundled fallback uses the latest valid public
cache found in your supplied project; it reproduces the five visible screenshot
rows (477/543, 70/141, 38/35, 12/7, 6/22).

Job evidence: Simplify / Coder Quad new-graduate public listings. AI evidence:
Hugging Face Transformers releases. SDGs: United Nations Sustainable Development
Goals. Counts describe a limited international graduate-job sample, not
Malaysian labour statistics or job forecasts. SDG mappings are curated.

## Verification

Checked the Flask page, stylesheet/script routes, radar/status APIs, all five
screenshot counts and eight role rows. Browser checks confirmed skill search,
combined search/filter empty state, Skills/Roles switching, SDG/evidence links,
and the isolated layout. Live external downloads were not triggered during
verification; live mode uses the extracted original bounded feed loader and
refresh worker.
