"""Register only the extracted screenshot section in any Flask application."""
import atexit
from pathlib import Path
from flask import Blueprint, current_app, jsonify, render_template
from .engine import build_radar, CATALOG
from .sources import SourceStore
from .monitor import TrendMonitor

bp = Blueprint('skills_radar', __name__, static_folder='static', template_folder='templates')

@bp.get('/')
def demo():
    return render_template('radar-demo.html')

@bp.get('/api/radar')
def radar():
    state = current_app.extensions['skills_radar']
    result = build_radar(state['store'].snapshot())
    result['sdgs'] = CATALOG['sdgs']
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    return response

@bp.get('/api/monitor/status')
def monitor_status():
    response = jsonify(current_app.extensions['skills_radar']['monitor'].status())
    response.headers['Cache-Control'] = 'no-store'
    return response

def init_app(app, *, url_prefix='/skills-radar', auto_refresh=False, interval=900):
    """Call once per Flask app, before serving requests.

    Enable auto_refresh=True for the original scheduled source checks.
    Default False keeps imports and a local preview free of network requests.
    """
    if 'skills_radar' in app.extensions:
        raise RuntimeError('Skills radar is already registered.')
    if isinstance(interval, bool) or not isinstance(interval, int) or not 300 <= interval <= 86400:
        raise ValueError('interval must be an integer between 300 and 86400 seconds.')
    storage = Path(app.instance_path) / 'skills_radar'
    seed = Path(__file__).parent / 'data' / 'signals_seed.json'
    store = SourceStore(storage / 'signals.json', seed)
    monitor = TrendMonitor(store, storage / 'monitor.sqlite3', enabled=auto_refresh, interval=interval, testing=app.testing)
    app.extensions['skills_radar'] = {'store':store, 'monitor':monitor}
    app.register_blueprint(bp, url_prefix=url_prefix)
    if monitor.start():
        atexit.register(monitor.stop)
    return monitor
