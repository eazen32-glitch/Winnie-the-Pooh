"""Bounded public evidence checks for the synthetic employer-verification demo.

GLEIF publishes the Global Legal Entity Identifier Index. An LEI record is
evidence about a legal entity; it is neither an SSM company-register check nor
proof that an individual may recruit for that entity. DNS proves control of a
domain, not a person's identity or employment. An independent reviewer must
assess recruiter authorization separately.

Only the explicitly selected ``gleif`` mode contacts public services. The
default fixture contains invented data and never falls back to a live service.
No arbitrary URL, uploaded document, SMTP delivery or recruiting action is used.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
import hashlib
import ipaddress
import json
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


UTC = timezone.utc
MODES = {"synthetic", "gleif"}
GLEIF_ORIGIN = "https://api.gleif.org"
DNS_ORIGIN = "https://dns.google"
MAX_REGISTRY_BYTES = 256 * 1024
MAX_DNS_BYTES = 64 * 1024
NETWORK_TIMEOUT_SECONDS = 4
NETWORK_DEADLINE_SECONDS = 8
SYNTHETIC_FIXTURE = {
    "legal_name": "Verdant Labs (Demo)",
    "country": "MY",
    "registration_number": "SYNTHETIC-REG-2026-01",
    "lei": "SYNTHETIC00000000001",
    "domain": "verdant.example.invalid",
    "recruiter_email": "hr@verdant.example.invalid",
    "entity_status": "ACTIVE",
    "registration_status": "ISSUED",
    "registration_authority_id": "SYNTHETIC-REGISTRY",
}
REGISTRY_LIMITATIONS = (
    "GLEIF LEI data identifies a legal entity; this is not a Malaysian SSM "
    "company-register check and does not verify recruiter identity or authorization."
)
DOMAIN_LIMITATIONS = (
    "A DNS TXT challenge demonstrates domain control only. It does not verify "
    "an individual's identity, mailbox access, employment or recruiting authorization."
)


class VerificationError(ValueError):
    """A verification claim failed local validation before any network request."""


def _mode(value):
    if not isinstance(value, str) or value not in MODES:
        raise VerificationError("Choose synthetic or gleif verification mode.")
    return value


def _field(payload, key, maximum, *, required=True, multiline=False):
    value = payload.get(key, "")
    if not isinstance(value, str) or len(value) > maximum:
        raise VerificationError(f"{key.replace('_', ' ').capitalize()} must be text of at most {maximum} characters.")
    value = value.strip()
    if required and not value:
        raise VerificationError(f"{key.replace('_', ' ').capitalize()} is required.")
    if any((ord(char) < 32 and not (multiline and char in "\n\t")) or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise VerificationError(f"{key.replace('_', ' ').capitalize()} contains unsupported characters.")
    return value


def normalize_domain(value, *, mode="synthetic"):
    """Accept a plain ASCII DNS hostname, never an address or a URL."""
    _mode(mode)
    if not isinstance(value, str) or len(value) > 253:
        raise VerificationError("Provide the employer's domain without a URL or path.")
    domain = value.strip().lower()
    labels = domain.split(".")
    if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise VerificationError("Provide the employer's domain without a URL or path.")
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        pass
    else:
        raise VerificationError("A company domain cannot be an IP address.")
    if len(labels[-1]) < 2 or labels[-1].isdigit():
        raise VerificationError("Provide a valid company domain.")
    if mode == "gleif" and (labels[-1] in {"invalid", "localhost", "local", "test", "example", "internal"} or domain in {"example.com", "example.org", "example.net"}):
        raise VerificationError("Live domain checks require a public company domain.")
    return domain


def valid_lei(value):
    """Validate an ISO 17442 LEI, including its ISO 7064 MOD 97-10 check digits."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9]{18}[0-9]{2}", value):
        return False
    digits = "".join(str(ord(char) - 55) if char.isalpha() else char for char in value)
    return int(digits) % 97 == 1


def normalize_evidence(payload, mode="synthetic"):
    """Validate structured claims without treating employer-supplied text as proof."""
    _mode(mode)
    if not isinstance(payload, dict):
        raise VerificationError("Provide a JSON object with structured company evidence.")
    result = {
        "legal_name": _field(payload, "legal_name", 240),
        "country": _field(payload, "country", 2).upper(),
        "registration_number": _field(payload, "registration_number", 120),
        "lei": _field(payload, "lei", 20).upper(),
        "domain": normalize_domain(_field(payload, "domain", 253), mode=mode),
        "recruiter_email": _field(payload, "recruiter_email", 254).lower(),
        "evidence_note": _field(payload, "evidence_note", 2000, multiline=True),
    }
    if not re.fullmatch(r"[A-Z]{2}", result["country"]):
        raise VerificationError("Country must use a two-letter ISO country code.")
    if not re.fullmatch(r"[A-Z0-9]{20}", result["lei"]):
        raise VerificationError("An LEI must contain exactly 20 letters and digits.")
    email = result["recruiter_email"]
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9.-]+", email):
        raise VerificationError("Use a fictional recruiter email ending in .invalid.")
    local, email_domain = email.rsplit("@", 1)
    if local.startswith(".") or local.endswith(".") or ".." in local or not email_domain.endswith(".invalid"):
        raise VerificationError("The hackathon accepts fictional recruiter emails ending in .invalid only; do not enter a real individual's email.")
    normalize_domain(email_domain)
    if mode == "synthetic":
        if email_domain != result["domain"]:
            raise VerificationError("Use a fictional recruiter email on exactly the synthetic company domain.")
        if not result["domain"].endswith(".example.invalid"):
            raise VerificationError("The public demo accepts invented company domains and recruiter emails under example.invalid only.")
    elif not valid_lei(result["lei"]):
        raise VerificationError("The LEI check digits are invalid.")
    return result


def _stamp(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _base(provider, source, *, now=None, ttl_days=30, simulation=False, limitations=""):
    when = now or datetime.now(UTC)
    if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise VerificationError("Evidence dates must include a timezone.")
    ttl = ttl_days if isinstance(ttl_days, int) and not isinstance(ttl_days, bool) else 30
    ttl = min(90, max(1, ttl))
    return {"schema_version": 1, "provider": provider, "source": source,
            "checked_at": _stamp(when), "expires_at": _stamp(when + timedelta(days=ttl)),
            "simulation": simulation, "limitations": limitations}


def _hashed(snapshot):
    # The digest covers the captured facts and provenance, not an arbitrary URL
    # or the employer's declarations. It is an audit checksum, not a signature.
    snapshot["sha256"] = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return snapshot


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Verification providers may not redirect requests.")


def _fetch_json(url, max_bytes):
    """Fetch one fixed-provider HTTPS resource with TLS verification and limits."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {"api.gleif.org", "dns.google"} or parsed.username or parsed.password:
        raise ValueError("Unsupported verification provider.")
    request = Request(url, headers={"User-Agent": "NextStep-Synthetic-Demo/1.0", "Accept": "application/json", "Accept-Encoding": "identity"})
    deadline = time.monotonic() + NETWORK_DEADLINE_SECONDS
    chunks, total = [], 0
    with build_opener(_NoRedirect()).open(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
        if response.geturl() != url:
            raise ValueError("Unexpected verification provider redirect.")
        length = response.headers.get("Content-Length")
        if length is not None and (not length.isdigit() or int(length) > max_bytes):
            raise ValueError("Verification response exceeds its size limit.")
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Verification response exceeded its time limit.")
            reader = getattr(response, "read1", response.read)
            part = reader(min(16 * 1024, max_bytes + 1 - total))
            if not part:
                break
            total += len(part)
            if total > max_bytes:
                raise ValueError("Verification response exceeds its size limit.")
            chunks.append(part)
    data = json.loads(b"".join(chunks))
    if not isinstance(data, dict):
        raise ValueError("Verification provider returned an unexpected JSON shape.")
    return data


def _record_text(value, maximum=240):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("Public registry record has a missing or malformed field.")
    return value.strip()


def _gleif_record(raw, expected_lei):
    """Read only the public identity fields required by our check."""
    data = raw.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("attributes"), dict):
        raise ValueError("Public registry returned no legal entity record.")
    attributes = data["attributes"]
    entity, registration = attributes.get("entity"), attributes.get("registration")
    if not isinstance(entity, dict) or not isinstance(registration, dict):
        raise ValueError("Public registry returned incomplete legal entity data.")
    name, address = entity.get("legalName"), entity.get("legalAddress")
    if not isinstance(name, dict) or not isinstance(address, dict):
        raise ValueError("Public registry returned incomplete legal identity data.")
    lei = _record_text(attributes.get("lei"), 20).upper()
    identifier = _record_text(data.get("id"), 20).upper()
    if lei != expected_lei or identifier != expected_lei or not valid_lei(lei):
        raise ValueError("Public registry returned a different or invalid LEI.")
    authority = entity.get("registeredAt")
    # registeredAs is GLEIF API v1's registrationAuthorityEntityID equivalent.
    registration_number = entity.get("registeredAs")
    if not registration_number and isinstance(entity.get("registrationAuthority"), dict):
        registration_number = entity["registrationAuthority"].get("registrationAuthorityEntityID")
    return {
        "lei": lei,
        "legal_name": _record_text(name.get("name")),
        "country": _record_text(address.get("country"), 2).upper(),
        "registration_number": _record_text(registration_number, 120),
        "registration_authority_id": _record_text(authority.get("id"), 120) if isinstance(authority, dict) and authority.get("id") else "",
        "entity_status": _record_text(entity.get("status"), 40).upper(),
        "registration_status": _record_text(registration.get("status"), 40).upper(),
    }


def _identity_text(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def check_registry(claims, mode="synthetic", *, now=None, ttl_days=30):
    """Capture a fixed fixture or exact-LEI GLEIF result; never infer authorization."""
    _mode(mode)
    if not isinstance(claims, dict):
        raise VerificationError("Provide structured company evidence.")
    lei = claims.get("lei")
    if not isinstance(lei, str) or not re.fullmatch(r"[A-Z0-9]{20}", lei):
        raise VerificationError("An LEI must contain exactly 20 letters and digits.")
    if mode == "gleif" and not valid_lei(lei):
        raise VerificationError("The LEI check digits are invalid.")
    source = "synthetic://nextstep/registry/verdant-labs-v1" if mode == "synthetic" else f"{GLEIF_ORIGIN}/api/v1/lei-records/{lei}"
    snapshot = _base("NextStep synthetic fixture" if mode == "synthetic" else "GLEIF Global LEI Index", source,
                     now=now, ttl_days=ttl_days, simulation=mode == "synthetic", limitations=REGISTRY_LIMITATIONS)
    try:
        record = deepcopy({key: value for key, value in SYNTHETIC_FIXTURE.items() if key not in {"domain", "recruiter_email"}}) if mode == "synthetic" else _gleif_record(_fetch_json(source, MAX_REGISTRY_BYTES), lei)
        matches = {key: isinstance(claims.get(key), str) and _identity_text(claims[key]) == _identity_text(record[key])
                   for key in ("legal_name", "country", "registration_number", "lei")}
        matches["active"] = record["entity_status"] == "ACTIVE" and record["registration_status"] == "ISSUED"
        snapshot.update(status="matched" if all(matches.values()) else "mismatch", record=record, matches=matches, error="")
    except HTTPError as error:
        missing = error.code == 404
        snapshot.update(status="mismatch" if missing else "unavailable", record=None, matches={},
                        error="No GLEIF record was found for this LEI." if missing else "The public registry is unavailable; retry before approval.")
    except (OSError, URLError, HTTPException, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        snapshot.update(status="unavailable", record=None, matches={}, error="The public registry could not be checked; retry before approval.")
    return _hashed(snapshot)


def _txt_value(value):
    """Decode the quoted TXT chunks emitted by Google's DNS-over-HTTPS API."""
    if not isinstance(value, str) or len(value) > 4096:
        return None
    # DNS JSON quotes each character-string separately. Reject escapes instead
    # of accidentally treating a loosely decoded value as an exact challenge.
    if re.fullmatch(r'"[^"\\]*"(?:\s+"[^"\\]*")*', value):
        return "".join(re.findall(r'"([^"\\]*)"', value))
    return None


def check_domain(domain, token, mode="synthetic", *, now=None, ttl_days=30):
    """Check an exact TXT token; callers must bind it to their submitted claims."""
    _mode(mode)
    domain = normalize_domain(domain, mode=mode)
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,160}", token):
        raise VerificationError("The domain challenge token is invalid or expired.")
    name = "_nextstep-verification." + domain
    source = "synthetic://nextstep/dns/verdant-labs-v1" if mode == "synthetic" else DNS_ORIGIN + "/resolve?" + urlencode({"name": name, "type": "TXT"})
    snapshot = _base("NextStep synthetic DNS fixture" if mode == "synthetic" else "Google Public DNS over HTTPS", source,
                     now=now, ttl_days=ttl_days, simulation=mode == "synthetic", limitations=DOMAIN_LIMITATIONS)
    snapshot.update(domain=domain, record_name=name, token_sha256=hashlib.sha256(token.encode("ascii")).hexdigest())
    try:
        if mode == "synthetic":
            matched = domain == SYNTHETIC_FIXTURE["domain"]
            snapshot.update(status="matched" if matched else "missing", dnssec_authenticated=False, error="")
        else:
            raw = _fetch_json(source, MAX_DNS_BYTES)
            status = raw.get("Status")
            if isinstance(status, bool) or not isinstance(status, int) or status not in {0, 3}:
                raise ValueError("DNS service could not resolve the company challenge.")
            answers = raw.get("Answer", [])
            if not isinstance(answers, list):
                raise ValueError("DNS service returned malformed challenge records.")
            matched = any(isinstance(answer, dict) and answer.get("type") == 16
                          and isinstance(answer.get("name"), str) and answer["name"].rstrip(".").lower() == name
                          and _txt_value(answer.get("data")) == token for answer in answers)
            snapshot.update(status="matched" if status == 0 and matched else "missing", dnssec_authenticated=raw.get("AD") is True, error="")
    except (OSError, URLError, HTTPException, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        snapshot.update(status="unavailable", dnssec_authenticated=False, error="The public DNS challenge could not be checked; retry before approval.")
    return _hashed(snapshot)
