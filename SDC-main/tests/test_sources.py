"""Evidence ingestion tests: no test makes an outbound network request."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from queue import Queue
from urllib.error import URLError
import xml.etree.ElementTree as ET

import pytest

from career import sources


UTC = timezone.utc


@pytest.fixture
def clock(monkeypatch):
    """A controllable current time, independent of machine-local timezone."""
    current = [datetime.now(UTC).replace(microsecond=0)]
    monkeypatch.setattr(sources, "now_utc", lambda: current[0])
    return current


def job_record(current, **changes):
    row = {
        "id": "public-job-1",
        "title": "Graduate Data Analyst",
        "company_name": "Example Public Employer",
        "category": "AI/ML/Data",
        "date_posted": int((current - timedelta(days=2)).timestamp()),
        "active": True,
        "url": "https://jobs.example.org/graduate-data-analyst",
    }
    row.update(changes)
    return row


def atom_body(current, extra_entries=""):
    date = sources.iso_time(current - timedelta(days=3))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Transformers &amp;lt;b&amp;gt;release&amp;lt;/b&amp;gt;</title>
        <published>{date}</published>
        <updated>{sources.iso_time(current)}</updated>
        <link rel="self" href="https://github.com/example/self" />
        <link rel="alternate" href="https://github.com/huggingface/transformers/releases/tag/v-test" />
        <content type="html">&lt;p&gt;Multimodal model support &amp;amp; bug fixes.&lt;/p&gt;</content>
      </entry>
      {extra_entries}
    </feed>""".encode()


@pytest.fixture
def seed_data(clock):
    """A minimal dated public-source snapshot, not synthetic demand statistics."""
    old = clock[0] - timedelta(days=4)
    return {
        "fetched_at": sources.iso_time(old),
        "ai_fetched_at": sources.iso_time(old),
        "jobs": [{
            "id": "seed-public-job",
            "title": "Graduate Data Analyst",
            "company": "Example Public Employer",
            "description": "AI/ML/Data",
            "posted_at": sources.iso_time(old - timedelta(days=1)),
            "url": "https://jobs.example.org/seed-data-analyst",
            "active": False,
        }],
        "ai_updates": [{
            "title": "Dated model release",
            "summary": "A source-linked public release.",
            "published_at": sources.iso_time(old - timedelta(days=2)),
            "url": "https://github.com/huggingface/transformers/releases/tag/seed",
        }],
    }


@pytest.fixture
def store(tmp_path, seed_data):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(seed_data), encoding="utf-8")
    return sources.SourceStore(tmp_path / "cache" / "signals.json", seed)


def install_downloads(monkeypatch, clock, *, fail=()):
    """URL-keyed responses remain correct when SourceStore runs two threads."""
    calls = Queue()
    responses = {
        sources.JOB_URL: json.dumps([job_record(clock[0], id="refreshed-job")]).encode(),
        sources.AI_URL: atom_body(clock[0]),
    }

    def fake_download(url, max_bytes):
        calls.put((url, max_bytes))
        if url in fail:
            raise URLError("private-proxy.example/credential-should-never-leak")
        assert url in responses, "Unexpected source URL"
        assert max_bytes >= len(responses[url])
        return responses[url]

    monkeypatch.setattr(sources, "download", fake_download)
    return calls


@pytest.mark.parametrize("url", [
    "http://example.org/job", "javascript:alert(1)", "data:text/html,hello",
    "https://user:password@example.org/job", "https://user@example.org/job",
    "https:///missing-host", "https://[invalid/job", None, 4,
])
def test_clickable_urls_reject_unsafe_or_malformed_values(url):
    assert sources.safe_url(url) == ""


def test_normalize_jobs_preserves_history_sanitizes_bounds_and_deduplicates(clock):
    current = clock[0]
    recent = job_record(
        current, title="<b>Graduate</b>  Data &amp; AI\nAnalyst " + "x" * 300,
        company_name="<em>Public</em> &amp; Employer " + "c" * 180,
        category="<p>AI/ML/Data</p> " + "d" * 160,
    )
    history = job_record(
        current, id="historical", title="Previous Data Analyst", active=False,
        date_posted=int((current - timedelta(days=35)).timestamp()),
        url="https://jobs.example.org/historical",
    )
    no_id = job_record(current, id=None, url="https://jobs.example.org/without-id")
    duplicate = dict(recent, title="Duplicate should not replace first record")
    jobs = sources.parse_jobs(json.dumps([history, recent, duplicate, no_id, no_id]).encode(), current)

    assert len(jobs) == 3
    assert jobs[-1]["id"] == "historical"
    assert jobs[-1]["active"] is False, "Inactive postings still provide dated historical evidence"
    normalized = next(job for job in jobs if job["id"] == recent["id"])
    assert normalized["title"].startswith("Graduate Data & AI Analyst")
    assert "<" not in normalized["title"]
    assert len(normalized["title"]) <= 240
    assert len(normalized["company"]) <= 140
    assert len(normalized["description"]) <= 100
    assert normalized["posted_at"] == sources.iso_time(current - timedelta(days=2))
    assert any(job["id"] == no_id["url"] for job in jobs)
    assert all(set(job) == {"id", "title", "company", "description", "posted_at", "url", "active"} for job in jobs)


@pytest.mark.parametrize("changes", [
    {"date_posted": "not-a-timestamp"},
    {"date_posted": None},
    {"date_posted": "inf"},
    {"title": "<b></b>"},
    {"url": "javascript:alert(1)"},
    {"url": "https://credential:secret@jobs.example.org/job"},
])
def test_invalid_job_records_do_not_replace_valid_evidence(clock, changes):
    valid = job_record(clock[0])
    invalid = job_record(clock[0], id="invalid", **changes)
    jobs = sources.parse_jobs(json.dumps([None, 7, valid, invalid]).encode(), clock[0])
    assert [job["id"] for job in jobs] == [valid["id"]]


def test_jobs_discard_old_and_far_future_publication_dates(clock):
    current = clock[0]
    rows = [
        job_record(current),
        job_record(current, id="too-old", date_posted=int((current - timedelta(days=62)).timestamp())),
        # The source parser allows a one-day publication-time tolerance.
        job_record(current, id="future", date_posted=int((current + timedelta(days=2)).timestamp())),
    ]
    assert [row["id"] for row in sources.parse_jobs(json.dumps(rows).encode(), current)] == ["public-job-1"]


@pytest.mark.parametrize("body", [b"{}", b"[]", b"[null, false]", b"not json"])
def test_unusable_job_payloads_raise_instead_of_fabricating_data(clock, body):
    with pytest.raises(ValueError):
        sources.parse_jobs(body, clock[0])


def test_parse_atom_keeps_safe_links_and_source_publication_dates(clock):
    date = sources.iso_time(clock[0] - timedelta(days=1))
    extra = f"""
      <entry><title>Unsafe release</title><updated>{date}</updated><link href="javascript:alert(1)"/></entry>
      <entry><title>Undated release</title><link href="https://github.com/example/undated"/></entry>
      <entry><title>Updated-only release</title><updated>{date}</updated><link href="https://github.com/example/updated"/></entry>
    """
    updates = sources.parse_ai_updates(atom_body(clock[0], extra))
    assert len(updates) == 2
    first = updates[0]
    assert first["url"] == "https://github.com/huggingface/transformers/releases/tag/v-test"
    assert first["published_at"] == sources.iso_time(clock[0] - timedelta(days=3))
    assert first["summary"] == "Multimodal model support & bug fixes."
    assert updates[1]["published_at"] == date
    assert all(row["url"].startswith("https://") for row in updates)
    assert all(set(row) == {"title", "summary", "published_at", "url"} for row in updates)


@pytest.mark.parametrize("body", [b"<not xml", b'<feed xmlns="http://www.w3.org/2005/Atom"/>'])
def test_unusable_ai_feed_raises_instead_of_inventing_releases(body):
    with pytest.raises((ValueError, ET.ParseError)):
        sources.parse_ai_updates(body)


@pytest.mark.parametrize("corruption", [
    "not-json", "missing-jobs", "invalid-date", "root-list", "invalid-job-row", "invalid-ai-row",
])
def test_corrupt_cache_falls_back_to_dated_seed(tmp_path, seed_data, corruption):
    seed = tmp_path / "source-snapshot.json"
    seed.write_text(json.dumps(seed_data), encoding="utf-8")
    cache = tmp_path / "cache.json"
    bad = deepcopy(seed_data)
    if corruption == "not-json":
        cache.write_text("{truncated", encoding="utf-8")
    else:
        if corruption == "missing-jobs":
            bad.pop("jobs")
        elif corruption == "invalid-date":
            bad["fetched_at"] = "not a date"
        elif corruption == "root-list":
            bad = []
        elif corruption == "invalid-job-row":
            bad["jobs"] = ["corrupt row"]
        elif corruption == "invalid-ai-row":
            bad["ai_updates"] = [{"title": "missing date and link"}]
        cache.write_text(json.dumps(bad), encoding="utf-8")

    snapshot = sources.SourceStore(cache, seed).snapshot()
    assert snapshot["jobs"] == seed_data["jobs"]
    assert snapshot["ai_updates"] == seed_data["ai_updates"]
    assert snapshot["signal_status"]["status"] == "cached"
    assert snapshot["signal_status"]["fetched_at"] == seed_data["fetched_at"]


def test_cached_snapshot_remains_dated_and_does_not_expose_mutable_store_data(store, seed_data, clock):
    snapshot = store.snapshot()
    assert snapshot["fetched_at"] == seed_data["fetched_at"]
    assert snapshot["signal_status"]["jobs_count"] == 1
    assert snapshot["signal_status"]["active_jobs_count"] == 0
    assert snapshot["signal_status"]["windows"] == sources.date_windows(clock[0] - timedelta(days=4))
    snapshot["jobs"].clear()
    snapshot["ai_updates"][0]["title"] = "Modified outside the store"
    assert store.snapshot()["jobs"] == seed_data["jobs"]
    assert store.snapshot()["ai_updates"] == seed_data["ai_updates"]


def test_successful_refresh_fetches_independent_sources_and_persists_cache(store, monkeypatch, clock):
    calls = install_downloads(monkeypatch, clock)
    snapshot, attempted = store.refresh()

    assert attempted is True
    assert calls.qsize() == 2
    assert {calls.get_nowait()[0], calls.get_nowait()[0]} == {sources.JOB_URL, sources.AI_URL}
    assert snapshot["signal_status"]["status"] == "live"
    assert snapshot["fetched_at"] == sources.iso_time(clock[0])
    assert snapshot["ai_fetched_at"] == sources.iso_time(clock[0])
    assert snapshot["jobs"][0]["id"] == "refreshed-job"
    assert snapshot["ai_updates"][0]["url"].startswith("https://github.com/")
    written = json.loads(store.cache_path.read_text(encoding="utf-8"))
    assert written["jobs"] == snapshot["jobs"]
    assert written["ai_updates"] == snapshot["ai_updates"]
    assert not store.cache_path.with_suffix(".tmp").exists()


def test_failed_refresh_preserves_last_dated_evidence_and_sanitizes_errors(store, seed_data, monkeypatch, clock):
    install_downloads(monkeypatch, clock, fail=(sources.JOB_URL, sources.AI_URL))
    snapshot, attempted = store.refresh()

    assert attempted is True
    assert snapshot["jobs"] == seed_data["jobs"]
    assert snapshot["ai_updates"] == seed_data["ai_updates"]
    assert snapshot["fetched_at"] == seed_data["fetched_at"]
    assert snapshot["ai_fetched_at"] == seed_data["ai_fetched_at"]
    assert snapshot["signal_status"]["status"] == "cached"
    assert "Could not refresh" in snapshot["signal_status"]["message"]
    assert "private-proxy" not in snapshot["signal_status"]["message"]
    assert "credential-should-never-leak" not in json.dumps(snapshot)


@pytest.mark.parametrize("failed_url", [sources.JOB_URL, sources.AI_URL])
def test_partial_refresh_preserves_each_sources_own_timestamp(store, seed_data, monkeypatch, clock, failed_url):
    install_downloads(monkeypatch, clock, fail=(failed_url,))
    snapshot, attempted = store.refresh()

    assert attempted is True
    assert snapshot["signal_status"]["status"] == "cached"
    if failed_url == sources.JOB_URL:
        assert snapshot["jobs"] == seed_data["jobs"]
        assert snapshot["fetched_at"] == seed_data["fetched_at"]
        assert snapshot["ai_fetched_at"] == sources.iso_time(clock[0])
    else:
        assert snapshot["jobs"][0]["id"] == "refreshed-job"
        assert snapshot["fetched_at"] == sources.iso_time(clock[0])
        assert snapshot["ai_updates"] == seed_data["ai_updates"]
        assert snapshot["ai_fetched_at"] == seed_data["ai_fetched_at"]


def test_offline_without_snapshot_never_manufactures_evidence(tmp_path, monkeypatch, clock):
    empty = sources.SourceStore(tmp_path / "missing-cache.json", tmp_path / "missing-seed.json")
    install_downloads(monkeypatch, clock, fail=(sources.JOB_URL, sources.AI_URL))
    snapshot, attempted = empty.refresh()

    assert attempted is True
    assert snapshot["jobs"] == []
    assert snapshot["ai_updates"] == []
    assert snapshot["signal_status"]["status"] == "offline"
    assert snapshot["signal_status"]["fetched_at"] is None
    assert snapshot["signal_status"]["jobs_count"] == 0
    assert not empty.cache_path.exists()


def test_refresh_cooldown_prevents_repeat_requests_then_expires(store, monkeypatch, clock):
    calls = install_downloads(monkeypatch, clock)
    first, first_attempt = store.refresh()
    second, second_attempt = store.refresh()
    assert first_attempt is True
    assert second_attempt is False
    assert calls.qsize() == 2
    assert first["jobs"] == second["jobs"]
    allowed = sources.iso_time(clock[0] + timedelta(seconds=sources.REFRESH_SECONDS))
    assert second["signal_status"]["refresh_allowed_at"] == allowed

    clock[0] += timedelta(seconds=sources.REFRESH_SECONDS + 1)
    third, third_attempt = store.refresh()
    assert third_attempt is True
    assert calls.qsize() == 4
    assert third["fetched_at"] == sources.iso_time(clock[0])


def test_date_windows_are_equal_nonoverlapping_thirty_day_periods(clock):
    windows = sources.date_windows(clock[0])
    parsed = {key: datetime.fromisoformat(value) for key, value in windows.items()}
    assert parsed["recent_end"] - parsed["recent_start"] == timedelta(days=30)
    assert parsed["previous_end"] - parsed["previous_start"] == timedelta(days=30)
    assert windows["previous_end"] == windows["recent_start"]


def test_bounded_download_rejects_oversized_response_without_network(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, requested):
            assert requested == 11
            return b"x" * requested

    def fake_urlopen(request, timeout):
        assert request.full_url == sources.JOB_URL
        assert timeout == 25
        return Response()

    monkeypatch.setattr(sources, "urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="download size limit"):
        sources.download(sources.JOB_URL, max_bytes=10)
