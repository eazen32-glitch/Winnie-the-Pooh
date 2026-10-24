"""Scheduled public-feed monitoring and source-observed occupation signals.

The daemon never receives user profiles. A small SQLite lease coordinates web
processes; failed fetches retain dated evidence. These observations are not
employment forecasts or a discovery of occupations that do not yet exist.
"""

from __future__ import annotations

import atexit
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from flask import Blueprint, current_app, jsonify

from .sources import JOB_ATTRIBUTION, JOB_URL, date_windows, iso_time, plain_text, safe_url

monitor_bp = Blueprint("trend_monitor", __name__)
UTC = timezone.utc
SCOPE = "Observed international technical graduate posting sample; not representative Malaysian labour statistics or a validated forecast."


def evidence_revision(snapshot):
    """Ignore fetch-time churn, but notice changed observations and AI evidence."""
    evidence = {key: snapshot.get(key, []) for key in ("jobs", "ai_updates")}
    encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]


def _stamp(value):
    return iso_time(datetime.fromtimestamp(value, UTC)) if value is not None else None


def _configured_bool(value, errors):
    if isinstance(value, bool):
        return value
    if str(value).lower() in {"1", "true", "yes", "on"}:
        return True
    if str(value).lower() in {"0", "false", "no", "off"}:
        return False
    errors.append("NEXTSTEP_AUTO_REFRESH must be 1 or 0; automatic refresh is disabled.")
    return False


class TrendMonitor:
    def __init__(self, store, database, *, enabled=True, interval=900, initial_delay=5, testing=False, configuration_errors=None):
        self.store = store
        self.database = Path(database)
        self.enabled = bool(enabled) and not testing
        self.testing = testing
        self.interval = interval
        self.initial_delay = initial_delay
        self.configuration_errors = list(configuration_errors or [])
        self.owner = uuid.uuid4().hex
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.RLock()
        self._next_due = None
        self._last_checked = None
        self._last_success = None
        self._last_error = None

    def start(self):
        with self._lock:
            if not self.enabled or (self._thread and self._thread.is_alive()):
                return False
            self._stop.clear()
            self._next_due = time.time() + self.initial_delay
            self._thread = threading.Thread(target=self._run, name="nextstep-public-signals", daemon=True)
            self._thread.start()
            return True

    def stop(self, timeout=1):
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    @contextmanager
    def _connection(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.database), timeout=2)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS refresh_lease (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT, lease_until REAL NOT NULL DEFAULT 0, next_due REAL NOT NULL DEFAULT 0)")
            connection.execute("INSERT OR IGNORE INTO refresh_lease(id) VALUES(1)")
            connection.commit()
            with connection:
                yield connection
        finally:
            connection.close()

    def _claim(self, now):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT lease_until,next_due FROM refresh_lease WHERE id=1").fetchone()
            if row[0] > now or row[1] > now:
                self._next_due = max(now + 5, row[0], row[1])
                return False
            # Downloads are bounded to 25 seconds; a two-minute lease survives
            # normal processing and automatically recovers a crashed process.
            connection.execute("UPDATE refresh_lease SET owner=?,lease_until=?,next_due=? WHERE id=1", (self.owner, now + 120, now + self.interval))
            self._next_due = now + self.interval
            return True

    def _release(self):
        with self._connection() as connection:
            connection.execute("UPDATE refresh_lease SET lease_until=0 WHERE id=1 AND owner=?", (self.owner,))

    def tick(self, now=None):
        """One bounded refresh attempt; explicit method permits deterministic tests."""
        if not self.enabled:
            return False
        now = time.time() if now is None else now
        claimed = False
        try:
            claimed = self._claim(now)
            if not claimed:
                return False
            self._last_checked = now
            snapshot, attempted = self.store.refresh()
            status = snapshot.get("signal_status", {})
            if attempted and status.get("status") == "live":
                self._last_success = time.time()
                self._last_error = None
            elif attempted:
                self._last_error = "Public sources could not all be refreshed; the last dated evidence remains available."
            else:
                self._last_error = None  # Manual refresh may have just used the cooldown.
            return attempted
        except Exception:
            # Do not expose database paths, proxy details, credentials or bodies.
            self._last_error = "Automatic refresh was unavailable; use the dated cache or try a manual refresh."
            self._next_due = now + self.interval
            return False
        finally:
            if claimed:
                try:
                    self._release()
                except Exception:
                    pass  # The lease expires without manual intervention.

    def _run(self):
        while not self._stop.is_set():
            delay = max(0, (self._next_due or time.time()) - time.time())
            if self._stop.wait(delay):
                break
            self.tick()

    def status(self):
        snapshot = self.store.snapshot()
        status = snapshot.get("signal_status", {})
        with self._lock:
            return {
                "enabled": self.enabled,
                "running": bool(self._thread and self._thread.is_alive()),
                "mode": "testing" if self.testing else "automatic" if self.enabled else "manual",
                "interval_seconds": self.interval,
                "next_refresh_at": _stamp(self._next_due),
                "last_checked_at": _stamp(self._last_checked),
                "last_success_at": _stamp(self._last_success),
                "last_error": self._last_error,
                "revision": evidence_revision(snapshot),
                "fetched_at": snapshot.get("fetched_at"),
                "ai_fetched_at": snapshot.get("ai_fetched_at"),
                "source_status": status.get("status", "offline"),
                "refreshing": status.get("refreshing", False),
                "configuration_errors": self.configuration_errors,
                "scope": SCOPE,
            }


def init_monitor(app):
    errors = []
    enabled = _configured_bool(app.config.get("AUTO_REFRESH_ENABLED", os.environ.get("NEXTSTEP_AUTO_REFRESH", "1")), errors)
    raw_interval = app.config.get("AUTO_REFRESH_INTERVAL", os.environ.get("NEXTSTEP_REFRESH_SECONDS", "900"))
    try:
        if isinstance(raw_interval, (bool, float)):
            raise ValueError
        interval = int(raw_interval)
        if not 300 <= interval <= 86400:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        interval = 900
        errors.append("Refresh interval must be 300–86400 seconds; using 900 seconds.")
    store = app.extensions["sources"]
    cache_path = Path(getattr(store, "cache_path", Path(app.instance_path) / "signals.json"))
    database = app.config.get("MONITOR_DATABASE", cache_path.parent / "trend-monitor.sqlite3")
    monitor = TrendMonitor(store, database, enabled=enabled, interval=interval, testing=app.testing, configuration_errors=errors)
    app.extensions["trend_monitor"] = monitor
    app.register_blueprint(monitor_bp)
    return monitor


def start_monitor(app):
    monitor = app.extensions.get("trend_monitor") or init_monitor(app)
    started = monitor.start()
    if started:
        atexit.register(monitor.stop)
    return started


def stop_monitor(app):
    monitor = app.extensions.get("trend_monitor")
    if monitor:
        monitor.stop()


def observed_occupations(snapshot, limit=40):
    """Group source titles without inventing occupations or employment statistics."""
    try:
        reference = datetime.fromisoformat(snapshot["fetched_at"].replace("Z", "+00:00"))
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
    except (KeyError, TypeError, ValueError):
        reference = datetime.now(UTC)
    windows = date_windows(reference)
    dates = {key: datetime.fromisoformat(value).replace(tzinfo=UTC) for key, value in windows.items()}
    grouped = defaultdict(lambda: {"title": "", "recent_count": 0, "previous_count": 0, "examples": []})
    seen = set()
    for job in snapshot.get("jobs", []):
        title, link = plain_text(job.get("title")), safe_url(job.get("url"))
        key = str(job.get("id") or link)
        if not title or not link or key in seen:
            continue
        try:
            posted = datetime.fromisoformat(job["posted_at"].replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=UTC)
        except (KeyError, ValueError, TypeError):
            continue
        if dates["recent_start"] <= posted < dates["recent_end"]:
            bucket = "recent_count"
        elif dates["previous_start"] <= posted < dates["previous_end"]:
            bucket = "previous_count"
        else:
            continue
        seen.add(key)
        item = grouped[title.casefold()]
        item["title"] = item["title"] or title
        item[bucket] += 1
        if len(item["examples"]) < 3:
            item["examples"].append({"title": title, "url": link, "posted_at": job["posted_at"], "company": plain_text(job.get("company"), 140)})
    items = []
    for item in grouped.values():
        recent, previous = item["recent_count"], item["previous_count"]
        trend = "insufficient_evidence"
        if recent >= 3 and previous == 0:
            trend = "newly_observed"
        elif max(recent, previous) >= 3:
            trend = "rising" if recent > previous * 1.25 else "declining" if recent < previous * 0.8 else "stable"
        item.update(change_count=recent - previous, trend=trend, uncertain=True)
        items.append(item)
    items.sort(key=lambda item: (-abs(item["change_count"]), -item["recent_count"], item["title"].casefold()))
    return {
        "as_of": snapshot.get("fetched_at"), "source_name": JOB_ATTRIBUTION,
        "source_url": JOB_URL, "windows": windows, "scope": SCOPE,
        "method": "Exact source titles grouped case-insensitively in two equal 30-day windows. At least three observations in one window are needed for a directional label. Newly observed means absent from this sample's previous window, not a newly created occupation.",
        "items": items[:max(1, min(int(limit), 100))],
    }


@monitor_bp.get("/api/monitor/status")
def monitor_status():
    return jsonify(current_app.extensions["trend_monitor"].status())


@monitor_bp.get("/api/monitor/discoveries")
def monitor_discoveries():
    return jsonify(observed_occupations(current_app.extensions["sources"].snapshot()))
