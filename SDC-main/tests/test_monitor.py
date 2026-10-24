"""Automatic signal refresh tests use isolated caches and no network."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import threading

from flask import Flask
import pytest

from career import monitor, sources

UTC = timezone.utc


class FakeStore:
    def __init__(self, tmp_path):
        self.cache_path = tmp_path / "signals.json"
        self.calls = 0
        self.refreshed = threading.Event()
        self.failure = False

    def snapshot(self):
        return {"jobs": [], "ai_updates": [], "signal_status": {"status": "live"}}

    def refresh(self):
        self.calls += 1
        self.refreshed.set()
        if self.failure:
            raise RuntimeError("private credential or proxy must not be exposed")
        return self.snapshot(), True


def configured_app(tmp_path, **config):
    app = Flask(__name__)
    app.config.update(config)
    app.extensions["sources"] = FakeStore(tmp_path)
    monitor.init_monitor(app)
    return app


def test_default_automatic_monitor_is_nonblocking_and_idempotent(tmp_path):
    store = FakeStore(tmp_path)
    worker = monitor.TrendMonitor(store, tmp_path / "monitor.sqlite3", initial_delay=0)
    try:
        assert worker.start() is True
        assert store.refreshed.wait(1)
        assert worker.start() is False
        assert worker.status()["mode"] == "automatic"
        assert worker.status()["running"] is True
    finally:
        worker.stop()
    assert not worker.status()["running"]


def test_testing_never_starts_automatic_network_even_when_enabled(tmp_path):
    app = configured_app(tmp_path, TESTING=True, AUTO_REFRESH_ENABLED=True)
    assert monitor.start_monitor(app) is False
    assert app.extensions["sources"].calls == 0
    data = app.test_client().get("/api/monitor/status").get_json()
    assert data["mode"] == "testing"
    assert data["enabled"] is False
    assert not (tmp_path / "trend-monitor.sqlite3").exists()


def test_default_mode_is_automatic_but_init_does_not_start_worker(tmp_path, monkeypatch):
    monkeypatch.delenv("NEXTSTEP_AUTO_REFRESH", raising=False)
    app = configured_app(tmp_path)
    status = app.extensions["trend_monitor"].status()
    assert status["enabled"] is True
    assert status["running"] is False
    assert status["interval_seconds"] == 900
    assert app.extensions["sources"].calls == 0


def test_env_optout_and_interval(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXTSTEP_AUTO_REFRESH", "0")
    monkeypatch.setenv("NEXTSTEP_REFRESH_SECONDS", "600")
    app = configured_app(tmp_path)
    assert not monitor.start_monitor(app)
    assert app.extensions["trend_monitor"].status()["interval_seconds"] == 600
    assert app.extensions["trend_monitor"].status()["mode"] == "manual"


@pytest.mark.parametrize("interval", ["nan", "299", "86401", -1, True, 300.5])
def test_bad_intervals_fall_back_safely(tmp_path, interval):
    app = configured_app(tmp_path, AUTO_REFRESH_INTERVAL=interval)
    status = app.extensions["trend_monitor"].status()
    assert status["interval_seconds"] == 900
    assert status["configuration_errors"]


def test_invalid_boolean_disables_instead_of_silently_enabling(tmp_path):
    app = configured_app(tmp_path, AUTO_REFRESH_ENABLED="sometimes")
    status = app.extensions["trend_monitor"].status()
    assert status["enabled"] is False
    assert status["configuration_errors"]


def test_coordinated_workers_do_not_repeat_scheduled_refresh(tmp_path):
    first_store, second_store = FakeStore(tmp_path), FakeStore(tmp_path)
    database = tmp_path / "shared.sqlite3"
    first = monitor.TrendMonitor(first_store, database)
    second = monitor.TrendMonitor(second_store, database)
    assert first.tick(now=1000) is True
    assert second.tick(now=1001) is False
    assert first_store.calls == 1 and second_store.calls == 0
    assert second.tick(now=1901) is True
    assert second_store.calls == 1


def test_failed_worker_attempt_sanitizes_error_and_preserves_cooldown(tmp_path):
    store = FakeStore(tmp_path)
    store.failure = True
    worker = monitor.TrendMonitor(store, tmp_path / "monitor.sqlite3")
    assert worker.tick(now=1000) is False
    status = worker.status()
    assert "credential" not in status["last_error"]
    assert "proxy" not in status["last_error"]
    assert status["next_refresh_at"]
    assert worker.tick(now=1001) is False
    assert store.calls == 1


def test_evidence_revision_ignores_refresh_timestamps_but_detects_changed_data():
    one = {"fetched_at": "2026-10-22", "jobs": [{"title": "Analyst"}], "ai_updates": []}
    two = deepcopy(one)
    two["fetched_at"] = "2026-10-23"
    assert monitor.evidence_revision(one) == monitor.evidence_revision(two)
    two["jobs"][0]["title"] = "New observed title"
    assert monitor.evidence_revision(one) != monitor.evidence_revision(two)


def sample_snapshot():
    reference = datetime(2026, 10, 23, 12, tzinfo=UTC)
    jobs = []
    for title, recent, previous in [("Growing role", 4, 1), ("Declining role", 0, 4), ("New to sample", 3, 0), ("Sparse role", 2, 0)]:
        for count, age in [(recent, 3), (previous, 40)]:
            for index in range(count):
                identifier = f"{title}-{age}-{index}"
                jobs.append({"id": identifier, "title": title, "posted_at": sources.iso_time(reference - timedelta(days=age)), "url": f"https://jobs.example.org/{len(jobs)}", "company": "Public sample"})
    return {"fetched_at": sources.iso_time(reference), "jobs": jobs, "ai_updates": []}


def test_discoveries_are_exact_observed_titles_with_sources_and_sparse_threshold():
    snapshot = sample_snapshot()
    snapshot["jobs"].append(deepcopy(snapshot["jobs"][0]))
    snapshot["jobs"].append({"id": "bad", "title": "Unsafe", "url": "javascript:alert(1)", "posted_at": snapshot["fetched_at"]})
    result = monitor.observed_occupations(snapshot)
    items = {item["title"]: item for item in result["items"]}
    assert set(items) == {"Growing role", "Declining role", "New to sample", "Sparse role"}
    assert items["Growing role"]["trend"] == "rising"
    assert items["Growing role"]["recent_count"] == 4
    assert items["Declining role"]["trend"] == "declining"
    assert items["New to sample"]["trend"] == "newly_observed"
    assert items["Sparse role"]["trend"] == "insufficient_evidence"
    assert all(item["uncertain"] and item["examples"][0]["url"].startswith("https:") for item in items.values())
    assert "not a newly created occupation" in result["method"]


def test_discovery_endpoint_handles_empty_offline_snapshot(tmp_path):
    app = configured_app(tmp_path, TESTING=True)
    response = app.test_client().get("/api/monitor/discoveries")
    assert response.status_code == 200
    assert response.get_json()["items"] == []


def test_snapshot_remains_available_during_network_refresh(tmp_path, monkeypatch):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(sample_snapshot()), encoding="utf-8")
    store = sources.SourceStore(tmp_path / "cache.json", seed)
    entered, release = threading.Event(), threading.Event()

    def blocked_download(url, maximum):
        entered.set()
        assert release.wait(2)
        raise OSError("synthetic network failure")

    monkeypatch.setattr(sources, "download", blocked_download)
    thread = threading.Thread(target=store.refresh)
    thread.start()
    try:
        assert entered.wait(1)
        # This call would block behind the old network-held RLock.
        snapshot = store.snapshot()
        assert snapshot["jobs"]
        assert snapshot["signal_status"]["refreshing"] is True
        assert store.refresh(force=True)[1] is False
    finally:
        release.set()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert store.snapshot()["signal_status"]["refreshing"] is False


def test_other_process_cache_update_becomes_visible_without_restart(tmp_path):
    seed, cache = tmp_path / "seed.json", tmp_path / "cache.json"
    snapshot = sample_snapshot()
    seed.write_text(json.dumps(snapshot), encoding="utf-8")
    store = sources.SourceStore(cache, seed)
    changed = deepcopy(snapshot)
    changed["jobs"][0]["title"] = "Updated public title"
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps(changed), encoding="utf-8")
    replacement.replace(cache)
    assert store.snapshot()["jobs"][0]["title"] == "Updated public title"
    assert store.snapshot()["signal_status"]["status"] == "cached"
    assert "another worker" in store.snapshot()["signal_status"]["message"]
