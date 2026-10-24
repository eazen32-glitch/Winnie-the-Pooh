"""Public verification parsing and network boundaries, without live requests."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.client import BadStatusLine, IncompleteRead
import hashlib
import json
from urllib.error import HTTPError, URLError

import pytest

from career import verification as verification


REAL_LEI = "5493001KJTIIGC8Y1R12"
OTHER_REAL_LEI = "213800D1EI4B9WTWWD28"
TOKEN = "nextstep_synthetic_challenge_123456789"
DOMAIN = "public-company.com"
STAMP = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def synthetic_claims():
    return dict(verification.SYNTHETIC_FIXTURE, evidence_note="Synthetic recruiter authorization reviewed.\nNo personal documents.")


@pytest.fixture
def real_claims(synthetic_claims):
    return dict(synthetic_claims, legal_name="Public Entity Limited", country="GB",
                registration_number="COMPANY-012345", lei=REAL_LEI, domain=DOMAIN)


@pytest.fixture
def gleif_record():
    return {"data": {"id": REAL_LEI, "attributes": {
        "lei": REAL_LEI,
        "entity": {
            "legalName": {"name": "Public Entity Limited"},
            "legalAddress": {"country": "GB"},
            "registeredAt": {"id": "RA000585"},
            "registeredAs": "COMPANY-012345",
            "status": "ACTIVE",
        },
        "registration": {"status": "ISSUED"},
    }}}


@pytest.fixture(autouse=True)
def prohibit_live_network(monkeypatch):
    def reject(*args, **kwargs):
        pytest.fail("Connector tests must never contact live services.")
    monkeypatch.setattr(verification, "build_opener", reject)


def assert_digest(snapshot):
    fields = {key: value for key, value in snapshot.items() if key != "sha256"}
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert snapshot["sha256"] == hashlib.sha256(encoded).hexdigest()


def test_synthetic_registry_is_fixed_independent_evidence_not_an_echo(synthetic_claims):
    expected = verification.check_registry(synthetic_claims, now=STAMP)
    assert expected["status"] == "matched"
    forged = verification.check_registry(dict(synthetic_claims, legal_name="Invented Claim", registration_number="FORGED-123"), now=STAMP)
    assert forged["status"] == "mismatch"
    assert forged["record"] == expected["record"]
    assert forged["matches"]["legal_name"] is False
    assert forged["matches"]["registration_number"] is False
    assert forged["source"].startswith("synthetic://")
    assert forged["simulation"] is True
    assert "recruiter_email" not in forged["record"]
    expected["record"]["legal_name"] = "Mutated snapshot"
    assert verification.check_registry(synthetic_claims)["record"]["legal_name"] == verification.SYNTHETIC_FIXTURE["legal_name"]


def test_synthetic_unknown_lei_and_domain_never_fall_back_to_a_real_provider(synthetic_claims):
    result = verification.check_registry(dict(synthetic_claims, lei=REAL_LEI))
    assert result["status"] == "mismatch"
    assert result["matches"]["lei"] is False
    assert verification.check_domain("other.example.invalid", TOKEN)["status"] == "missing"
    assert verification.check_domain(verification.SYNTHETIC_FIXTURE["domain"], TOKEN)["status"] == "matched"


@pytest.mark.parametrize("days,expected", [(0, 1), (-100, 1), (365, 90), (7, 7), (True, 30), ("7", 30)])
def test_evidence_has_dated_bounded_expiry_and_reproducible_checksum(synthetic_claims, days, expected):
    result = verification.check_registry(synthetic_claims, now=STAMP, ttl_days=days)
    assert result["checked_at"] == "2026-10-23T12:00:00Z"
    expires = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00"))
    assert expires == STAMP + timedelta(days=expected)
    assert_digest(result)
    assert "SSM" in result["limitations"]
    assert "authorization" in result["limitations"]


@pytest.mark.parametrize("value,expected", [
    (REAL_LEI, True), (OTHER_REAL_LEI, True),
    ("5493001KJTIIGC8Y1R13", False), (REAL_LEI.lower(), False),
    ("5493001KJTIIGC8Y1R1A", False), ("A" * 20, False),
    ("5493001KJTIIGC8Y1R12/../../", False), (None, False), (True, False),
])
def test_iso_17442_lei_format_and_check_digits(value, expected):
    assert verification.valid_lei(value) is expected


def test_live_claims_retain_a_fictional_recruiter_reference(real_claims):
    result = verification.normalize_evidence(real_claims, "gleif")
    assert result["domain"] == DOMAIN
    assert result["recruiter_email"].endswith(".invalid")
    assert result["recruiter_email"].rsplit("@", 1)[1] != DOMAIN


@pytest.mark.parametrize("mode", ["synthetic", "gleif"])
@pytest.mark.parametrize("email", ["real.person@public-company.com", "person@gmail.com", "real@localhost", "person@invalid"])
def test_real_individual_email_is_rejected_in_every_mode(synthetic_claims, real_claims, mode, email):
    claims = real_claims if mode == "gleif" else synthetic_claims
    with pytest.raises(verification.VerificationError):
        verification.normalize_evidence(dict(claims, recruiter_email=email), mode)


@pytest.mark.parametrize("field,value", [
    ("legal_name", ""), ("legal_name", "bad\ud800"), ("legal_name", "bad\x00name"),
    ("country", "MYS"), ("country", "1!"), ("registration_number", []),
    ("lei", "SYNTHETIC000000000001"), ("evidence_note", ""),
    ("recruiter_email", ".bad@verdant.example.invalid"),
    ("recruiter_email", "bad..dots@verdant.example.invalid"),
    ("recruiter_email", "hr@another.example.invalid"),
])
def test_structured_evidence_rejects_malformed_or_unsafe_fields(synthetic_claims, field, value):
    with pytest.raises(verification.VerificationError):
        verification.normalize_evidence(dict(synthetic_claims, **{field: value}))


@pytest.mark.parametrize("domain", [
    "http://public-company.com", "public-company.com/path", "user@public-company.com",
    "127.0.0.1", "[::1]", "localhost", "company.local", "company.invalid",
    "a..public-company.com", "-bad.public-company.com", "public-company.com:443",
    "public-company.com\n.evil.test", "example.com", "a" * 64 + ".com",
])
def test_live_company_domain_rejects_urls_addresses_and_nonpublic_names(domain):
    with pytest.raises(verification.VerificationError):
        verification.normalize_domain(domain, mode="gleif")


@pytest.mark.parametrize("mode", [None, [], "ssm", "https://evil.test"])
def test_unknown_mode_is_rejected_instead_of_contacting_an_arbitrary_provider(synthetic_claims, mode):
    with pytest.raises(verification.VerificationError):
        verification.check_registry(synthetic_claims, mode)


def test_exact_live_lei_record_matches_with_public_provenance(monkeypatch, real_claims, gleif_record):
    fetched = []
    def fetch(url, limit):
        fetched.append((url, limit))
        return deepcopy(gleif_record)
    monkeypatch.setattr(verification, "_fetch_json", fetch)
    result = verification.check_registry(real_claims, "gleif", now=STAMP)
    assert fetched == [("https://api.gleif.org/api/v1/lei-records/" + REAL_LEI, verification.MAX_REGISTRY_BYTES)]
    assert result["status"] == "matched"
    assert result["simulation"] is False
    assert all(result["matches"].values())
    assert result["record"]["registration_authority_id"] == "RA000585"
    assert "SSM" in result["limitations"]
    assert_digest(result)


@pytest.mark.parametrize("field,value", [("legal_name", "Wrong Entity"), ("country", "MY"), ("registration_number", "OTHER-012345")])
def test_public_identity_mismatch_cannot_be_marked_matched(monkeypatch, real_claims, gleif_record, field, value):
    monkeypatch.setattr(verification, "_fetch_json", lambda *_: deepcopy(gleif_record))
    result = verification.check_registry(dict(real_claims, **{field: value}), "gleif")
    assert result["status"] == "mismatch"
    assert result["matches"][field] is False


@pytest.mark.parametrize("entity_status,registration_status", [
    ("INACTIVE", "ISSUED"), ("ACTIVE", "LAPSED"), ("ACTIVE", "PENDING_TRANSFER"), ("INACTIVE", "RETIRED"),
])
def test_entity_must_be_active_and_lei_registration_issued(monkeypatch, real_claims, gleif_record, entity_status, registration_status):
    gleif_record["data"]["attributes"]["entity"]["status"] = entity_status
    gleif_record["data"]["attributes"]["registration"]["status"] = registration_status
    monkeypatch.setattr(verification, "_fetch_json", lambda *_: gleif_record)
    result = verification.check_registry(real_claims, "gleif")
    assert result["status"] == "mismatch"
    assert result["matches"]["active"] is False


@pytest.mark.parametrize("alteration", ["wrong_id", "wrong_lei", "no_registered_as", "no_legal_name", "missing_attributes", "data_list"])
def test_malformed_or_different_public_registry_record_fails_closed(monkeypatch, real_claims, gleif_record, alteration):
    if alteration == "wrong_id":
        gleif_record["data"]["id"] = OTHER_REAL_LEI
    elif alteration == "wrong_lei":
        gleif_record["data"]["attributes"]["lei"] = OTHER_REAL_LEI
    elif alteration == "no_registered_as":
        del gleif_record["data"]["attributes"]["entity"]["registeredAs"]
    elif alteration == "no_legal_name":
        gleif_record["data"]["attributes"]["entity"]["legalName"] = None
    elif alteration == "missing_attributes":
        del gleif_record["data"]["attributes"]
    else:
        gleif_record["data"] = []
    monkeypatch.setattr(verification, "_fetch_json", lambda *_: gleif_record)
    result = verification.check_registry(real_claims, "gleif")
    assert result["status"] == "unavailable"
    assert result["record"] is None
    assert result["matches"] == {}
    assert result["simulation"] is False


@pytest.mark.parametrize("error", [URLError("offline"), TimeoutError("timeout"), ValueError("bad JSON"), RecursionError("nested JSON"), IncompleteRead(b"partial"), BadStatusLine("malformed provider response")])
def test_provider_failure_never_falls_back_or_produces_a_positive_match(monkeypatch, real_claims, error):
    def fail(*_):
        raise error
    monkeypatch.setattr(verification, "_fetch_json", fail)
    result = verification.check_registry(real_claims, "gleif")
    assert result["status"] == "unavailable"
    assert result["record"] is None
    assert result["source"].startswith("https://api.gleif.org/")
    assert result["simulation"] is False
    assert verification.check_domain(DOMAIN, TOKEN, "gleif")["status"] == "unavailable"


@pytest.mark.parametrize("status,expected", [(404, "mismatch"), (429, "unavailable"), (503, "unavailable")])
def test_public_registry_http_status_has_no_positive_fallback(monkeypatch, real_claims, status, expected):
    def fail(*_):
        raise HTTPError("https://api.gleif.org", status, "provider error", {}, None)
    monkeypatch.setattr(verification, "_fetch_json", fail)
    result = verification.check_registry(real_claims, "gleif")
    assert result["status"] == expected
    assert result["record"] is None


def dns_answer(**updates):
    return {"name": "_nextstep-verification." + DOMAIN + ".", "type": 16, "data": '"' + TOKEN + '"', **updates}


def test_live_dns_uses_fixed_doh_provider_and_exact_chunked_txt_token(monkeypatch):
    calls = []
    answer = dns_answer(name=("_nextstep-verification." + DOMAIN).upper() + ".", data='"' + TOKEN[:10] + '" "' + TOKEN[10:] + '"')
    def fetch(url, limit):
        calls.append((url, limit))
        return {"Status": 0, "AD": True, "Answer": [answer]}
    monkeypatch.setattr(verification, "_fetch_json", fetch)
    result = verification.check_domain(DOMAIN, TOKEN, "gleif", now=STAMP)
    assert result["status"] == "matched"
    assert calls == [("https://dns.google/resolve?name=_nextstep-verification.public-company.com&type=TXT", verification.MAX_DNS_BYTES)]
    assert result["dnssec_authenticated"] is True
    assert result["simulation"] is False
    assert result["token_sha256"] == hashlib.sha256(TOKEN.encode("ascii")).hexdigest()
    assert TOKEN not in json.dumps(result)
    assert "domain control only" in result["limitations"]
    assert_digest(result)


@pytest.mark.parametrize("answer", [
    dns_answer(type=1), dns_answer(type="16"),
    dns_answer(name="_nextstep-verification.attacker.com."),
    dns_answer(name="_nextstep-verification." + DOMAIN + ".attacker.com."),
    dns_answer(data='"prefix-' + TOKEN + '"'), dns_answer(data='"' + TOKEN + '-suffix"'),
    dns_answer(data=TOKEN), dns_answer(data='"nextstep\\095synthetic_challenge_123456789"'),
    dns_answer(data=None), {"type": 16}, None,
])
def test_dns_record_name_type_and_decoded_token_must_all_match(monkeypatch, answer):
    monkeypatch.setattr(verification, "_fetch_json", lambda *_: {"Status": 0, "Answer": [answer]})
    assert verification.check_domain(DOMAIN, TOKEN, "gleif")["status"] == "missing"


@pytest.mark.parametrize("raw,expected", [
    ({"Status": 3}, "missing"), ({"Status": 3, "Answer": [dns_answer()]}, "missing"),
    ({"Status": 0}, "missing"), ({"Status": 0, "Answer": []}, "missing"),
    ({"Status": 2}, "unavailable"), ({"Status": False}, "unavailable"),
    ({"Status": "0"}, "unavailable"), ({}, "unavailable"),
    ({"Status": 0, "Answer": None}, "unavailable"),
])
def test_dns_nxdomain_empty_and_malformed_results_fail_closed(monkeypatch, raw, expected):
    monkeypatch.setattr(verification, "_fetch_json", lambda *_: raw)
    assert verification.check_domain(DOMAIN, TOKEN, "gleif")["status"] == expected


@pytest.mark.parametrize("token", ["short", "a" * 161, "a" * 20 + "/", "a" * 20 + "\n", None])
def test_invalid_challenge_token_is_rejected_before_network(token):
    with pytest.raises(verification.VerificationError):
        verification.check_domain(DOMAIN, token, "gleif")


class FakeResponse:
    def __init__(self, body=b'{"ok":true}', *, url="https://api.gleif.org/api/v1/lei-records/" + REAL_LEI, headers=None):
        self.body = body
        self.url = url
        self.headers = headers or {}
        self.closed = False
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def geturl(self):
        return self.url

    def read1(self, amount):
        self.reads += 1
        part, self.body = self.body[:amount], self.body[amount:]
        return part

    read = read1


def install_response(monkeypatch, response):
    calls = []
    class FakeOpener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            return response
    def opener(*handlers):
        assert len(handlers) == 1 and isinstance(handlers[0], verification._NoRedirect)
        return FakeOpener()
    monkeypatch.setattr(verification, "build_opener", opener)
    return calls


def test_http_reader_uses_bounded_timeout_and_closes_successful_response(monkeypatch):
    response = FakeResponse()
    calls = install_response(monkeypatch, response)
    assert verification._fetch_json(response.url, 100) == {"ok": True}
    request, timeout = calls[0]
    assert request.full_url == response.url
    assert timeout == verification.NETWORK_TIMEOUT_SECONDS
    assert request.get_header("Accept-encoding") == "identity"
    assert response.closed is True


@pytest.mark.parametrize("url", [
    "http://api.gleif.org/x", "https://evil.test/x", "https://api.gleif.org.evil.test/x",
    "https://user:secret@api.gleif.org/x", "https://api.gleif.org:443/x",
    "file:///etc/passwd", "https://127.0.0.1/x", "https://dns.google.evil.test/resolve",
])
def test_http_reader_rejects_arbitrary_urls_before_opening(url):
    with pytest.raises(ValueError, match="Unsupported verification provider"):
        verification._fetch_json(url, 100)


def test_redirect_handler_refuses_to_follow_a_redirect():
    with pytest.raises(ValueError, match="may not redirect"):
        verification._NoRedirect().redirect_request(None, None, 302, "Found", {}, "https://evil.test")


def test_unexpected_final_url_is_rejected_even_if_a_transport_follows_it(monkeypatch):
    response = FakeResponse(url="https://evil.test/redirected")
    install_response(monkeypatch, response)
    with pytest.raises(ValueError, match="redirect"):
        verification._fetch_json("https://api.gleif.org/api/v1/lei-records/" + REAL_LEI, 100)
    assert response.closed is True and response.reads == 0


@pytest.mark.parametrize("headers,body", [
    ({"Content-Length": "101"}, b'{}'), ({"Content-Length": "-1"}, b'{}'),
    ({"Content-Length": "unknown"}, b'{}'), ({}, b"x" * 101),
])
def test_http_reader_limits_declared_and_actual_response_size(monkeypatch, headers, body):
    response = FakeResponse(body, headers=headers)
    install_response(monkeypatch, response)
    with pytest.raises(ValueError, match="size limit"):
        verification._fetch_json(response.url, 100)
    assert response.closed is True


def test_http_reader_deadline_stops_reading_and_closes_response(monkeypatch):
    response = FakeResponse(b"x" * 100)
    install_response(monkeypatch, response)
    readings = iter([0, verification.NETWORK_DEADLINE_SECONDS + 1])
    monkeypatch.setattr(verification.time, "monotonic", lambda: next(readings))
    with pytest.raises(TimeoutError, match="time limit"):
        verification._fetch_json(response.url, 100)
    assert response.closed is True and response.reads == 0


@pytest.mark.parametrize("body", [b"not JSON", b"[]", b"null", b'"text"'])
def test_http_reader_requires_a_json_object(monkeypatch, body):
    response = FakeResponse(body)
    install_response(monkeypatch, response)
    with pytest.raises(ValueError):
        verification._fetch_json(response.url, 100)
    assert response.closed is True
