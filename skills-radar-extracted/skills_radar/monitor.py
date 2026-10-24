"""Source-refresh worker extracted from career/monitor.py; no account dependencies."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sqlite3
import threading
import time
import uuid
from .sources import iso_time

UTC = timezone.utc
SCOPE = 'Observed international technical graduate posting sample; not representative Malaysian labour statistics or a validated forecast.'

def evidence_revision(snapshot):
    """Ignore fetch-time churn, but notice changed observations and AI evidence."""
    evidence = {key: snapshot.get(key, []) for key in ("jobs", "ai_updates")}
    encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]



def _stamp(value):
    return iso_time(datetime.fromtimestamp(value, UTC)) if value is not None else None



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

