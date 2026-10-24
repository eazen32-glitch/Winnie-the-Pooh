"""Public evidence ingestion with bounded downloads, dated caches and offline fallback.

No CVs or personal profiles are collected. Only minimal public posting metadata
is retained. Feed failures never become invented job or technology evidence.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
import tempfile
import threading
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

UTC = timezone.utc
JOB_URL = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"
AI_URL = "https://github.com/huggingface/transformers/releases.atom"
JOB_ATTRIBUTION = "Simplify / Coder Quad public new-graduate listings"
AI_ATTRIBUTION = "Hugging Face Transformers releases"
REFRESH_SECONDS = 300
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def now_utc():
    return datetime.now(UTC)


def iso_time(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_url(value):
    """Only clickable HTTPS links; reject javascript/data and credential-bearing URLs."""
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlparse(value)
        return value if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password else ""
    except ValueError:
        return ""


def plain_text(value, limit=240):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()[:limit]


def download(url, max_bytes):
    request = Request(url, headers={"User-Agent": "NextStep-SDC/1.0 (public research prototype)", "Accept": "application/json, application/atom+xml, */*"})
    # Default certificate and hostname verification stays enabled.
    with urlopen(request, timeout=25) as response:
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError("Source exceeded its download size limit")
    return body


def parse_jobs(body, fetched_at):
    raw = json.loads(body)
    if not isinstance(raw, list):
        raise ValueError("Unexpected job-source format")
    cutoff = fetched_at - timedelta(days=61)
    jobs, seen = [], set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            posted = datetime.fromtimestamp(float(row.get("date_posted", 0)), UTC)
        except (ValueError, TypeError, OverflowError, OSError):
            continue
        title = plain_text(row.get("title"))
        url = safe_url(row.get("url"))
        key = str(row.get("id") or url)
        if not title or not url or key in seen or not cutoff <= posted <= fetched_at + timedelta(days=1):
            continue
        seen.add(key)
        jobs.append({
            "id": key[:200], "title": title,
            "company": plain_text(row.get("company_name"), 140),
            "description": plain_text(row.get("category"), 100),
            "posted_at": iso_time(posted), "url": url,
            "active": row.get("active") is True,
        })
    if not jobs:
        raise ValueError("The source returned no valid dated job records")
    return sorted(jobs, key=lambda job: (job["posted_at"], job["id"]), reverse=True)


def parse_ai_updates(body):
    root = ET.fromstring(body)
    updates = []
    for entry in root.findall("a:entry", ATOM)[:20]:
        title = plain_text(entry.findtext("a:title", "", ATOM))
        date = entry.findtext("a:published", "", ATOM) or entry.findtext("a:updated", "", ATOM)
        link = next((safe_url(item.attrib.get("href")) for item in entry.findall("a:link", ATOM) if item.attrib.get("rel", "alternate") == "alternate"), "")
        try:
            parsed_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            continue
        if title and link:
            updates.append({"title": title, "summary": plain_text(entry.findtext("a:content", "", ATOM), 18000), "published_at": iso_time(parsed_date), "url": link})
    if not updates:
        raise ValueError("The AI feed contained no usable dated releases")
    return updates


def date_windows(as_of):
    # Two equal, non-overlapping 30-day windows, inclusive start/exclusive end.
    end = as_of.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    recent = end - timedelta(days=30)
    previous = recent - timedelta(days=30)
    return {"recent_start": previous_to_date(recent), "recent_end": previous_to_date(end), "previous_start": previous_to_date(previous), "previous_end": previous_to_date(recent)}


def previous_to_date(value):
    return value.date().isoformat()


def valid_snapshot(data):
    """Reject partially corrupt local state before it can break a request."""
    if not isinstance(data, dict) or not isinstance(data.get("jobs"), list) or not data["jobs"]:
        return False
    try:
        datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00"))
        for row in data["jobs"]:
            if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not safe_url(row.get("url")):
                return False
            datetime.fromisoformat(row["posted_at"].replace("Z", "+00:00"))
        if not isinstance(data.get("ai_updates", []), list):
            return False
        for row in data.get("ai_updates", []):
            if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not safe_url(row.get("url")):
                return False
            datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
        if data.get("ai_fetched_at"):
            datetime.fromisoformat(data["ai_fetched_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False
    return True


class SourceStore:
    def __init__(self, cache_path, seed_path):
        self.cache_path = Path(cache_path)
        self.seed_path = Path(seed_path)
        self.lock = threading.RLock()
        self._data = None
        self._last_attempt = None
        self._refreshing = False
        self._cache_mtime = None
        self._mode = "offline"
        self._message = "No evidence available. Refresh the public sources."
        self._load()

    def _load(self):
        for path in (self.cache_path, self.seed_path):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if not valid_snapshot(data):
                    continue
                self._data = data
                if path == self.cache_path:
                    self._cache_mtime = path.stat().st_mtime_ns
                self._mode = "cached"
                self._message = "Dated public-source snapshot. Refresh to check for new evidence."
                return
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue

    def snapshot(self):
        with self.lock:
            # Other web processes share the scheduled worker's atomic cache.
            # A worker refresh must not leave their in-memory evidence stale.
            try:
                modified = self.cache_path.stat().st_mtime_ns
                if modified != self._cache_mtime:
                    cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
                    if valid_snapshot(cached):
                        self._data = cached
                        self._cache_mtime = modified
                        self._mode = "cached"
                        self._message = "Updated dated public-source cache from another worker. Source timestamps show when it was fetched."
            except (OSError, ValueError, TypeError):
                pass
            data = deepcopy(self._data or {"jobs": [], "ai_updates": []})
            reference = datetime.fromisoformat(data["fetched_at"].replace("Z", "+00:00")) if data.get("fetched_at") else now_utc()
            next_refresh = self._last_attempt + timedelta(seconds=REFRESH_SECONDS) if self._last_attempt else now_utc()
            data["signal_status"] = {
                "status": self._mode, "message": self._message,
                "refreshing": self._refreshing,
                "fetched_at": data.get("fetched_at"),
                "source_name": JOB_ATTRIBUTION, "source_url": JOB_URL,
                "jobs_count": len(data["jobs"]),
                "active_jobs_count": sum(job.get("active", False) for job in data["jobs"]),
                "windows": date_windows(reference),
                "refresh_allowed_at": iso_time(next_refresh),
                "ai_source_name": AI_ATTRIBUTION, "ai_source_url": AI_URL,
                "ai_fetched_at": data.get("ai_fetched_at"),
                "ai_updates": [{k: row[k] for k in ("title", "published_at", "url")} for row in data.get("ai_updates", [])],
                "scope": "International new-graduate technical job sample, mainly US/Canada/remote; includes inactive historical postings. Not Malaysian labor-market statistics.",
                "method": "Title/category keyword mentions; two equal 30-day posting windows. Dates use UTC; window end is exclusive. Releases are technology evidence, not job demand.",
            }
            return data

    def refresh(self, force=False):
        with self.lock:
            current = now_utc()
            if self._refreshing or (not force and self._last_attempt and (current - self._last_attempt).total_seconds() < REFRESH_SECONDS):
                return self.snapshot(), False
            self._last_attempt = current
            self._refreshing = True
            existing = deepcopy(self._data or {"jobs": [], "ai_updates": []})
        # Network IO runs outside the snapshot lock: the interface can keep
        # serving the last dated evidence while scheduled refreshes are pending.
        failures = []
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                requests = {"jobs": executor.submit(download, JOB_URL, 24 * 1024 * 1024), "ai_updates": executor.submit(download, AI_URL, 3 * 1024 * 1024)}
                for name, future in requests.items():
                    try:
                        body = future.result()
                        existing[name] = parse_jobs(body, current) if name == "jobs" else parse_ai_updates(body)
                        existing["fetched_at" if name == "jobs" else "ai_fetched_at"] = iso_time(current)
                    except Exception:
                        # Never expose proxy URLs, credentials, or remote response bodies.
                        failures.append(name)
        except BaseException:
            with self.lock:
                self._refreshing = False
            raise
        with self.lock:
            if existing.get("jobs"):
                self._data = existing
                self._mode = "live" if not failures else "cached"
                self._message = "Public evidence refreshed successfully; unchanged feeds can produce the same recommendations." if not failures else "Could not refresh " + ", ".join(failures) + "; using the last dated evidence where available."
                try:
                    self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = None
                    try:
                        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".signals-", suffix=".tmp", dir=self.cache_path.parent, delete=False) as output:
                            temporary = Path(output.name)
                            json.dump(existing, output, ensure_ascii=False)
                        temporary.replace(self.cache_path)
                        self._cache_mtime = self.cache_path.stat().st_mtime_ns
                    finally:
                        if temporary is not None:
                            temporary.unlink(missing_ok=True)
                except OSError:
                    self._message += " Cache could not be saved; current evidence is held in memory."
            else:
                self._mode = "offline"
                self._message = "Public sources unavailable and no job snapshot exists. Market support remains zero."
            self._refreshing = False
            return self.snapshot(), True
