"""The optional model routes intent only, with consent and no profile transfer."""

import json
from urllib.error import URLError

import pytest

from career import llm


@pytest.fixture(autouse=True)
def isolated_model_settings(monkeypatch):
    for name in ("NEXTSTEP_ENABLE_LLM", "NEXTSTEP_OPENAI_API_KEY", "NEXTSTEP_OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def enable_model(monkeypatch):
    monkeypatch.setenv("NEXTSTEP_ENABLE_LLM", "1")
    monkeypatch.setenv("NEXTSTEP_OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("NEXTSTEP_OPENAI_MODEL", "synthetic-test-model")


def local_reply(**options):
    return llm.enhanced_reply("Help with a professional direction", {"skills": [], "interests": "PRIVATE INTEREST", "weekly_hours": 6}, {"jobs": [], "ai_updates": [], "signal_status": {"status": "offline"}}, **options)


class ProviderResponse:
    def __init__(self, selection):
        self.raw = json.dumps({"choices": [{"message": {"content": json.dumps(selection)}}]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size):
        return self.raw[:size]


def test_capabilities_hide_secrets_and_require_all_settings(monkeypatch):
    assert llm.assistant_capabilities()["model_available"] is False
    monkeypatch.setenv("NEXTSTEP_OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("NEXTSTEP_ENABLE_LLM", "1")
    assert llm.assistant_capabilities()["model_available"] is False
    monkeypatch.setenv("NEXTSTEP_OPENAI_MODEL", "synthetic-test-model")
    capabilities = llm.assistant_capabilities()
    assert capabilities["model_available"] is True
    assert capabilities["consent_required"] is True
    assert "synthetic-test-key" not in json.dumps(capabilities)


def test_no_external_request_without_explicit_optin(enable_model, monkeypatch):
    monkeypatch.setattr(llm, "urlopen", lambda *args, **kwargs: pytest.fail("No request was authorised"))
    assert local_reply()["model_info"]["used"] is False
    with pytest.raises(ValueError, match="Consent"):
        local_reply(use_model=True, consent=False)


def test_not_configured_model_keeps_local_guidance_without_network(monkeypatch):
    monkeypatch.setattr(llm, "urlopen", lambda *args, **kwargs: pytest.fail("No configured model"))
    reply = local_reply(use_model=True, consent=True)
    assert reply["model_info"]["status"] == "not_configured"
    assert reply["answer"]


def test_model_selection_uses_local_facts_and_does_not_send_profile(enable_model, monkeypatch):
    captured = {}

    def provider(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["url"] = request.full_url
        assert timeout == 8
        return ProviderResponse({"intent": "skills", "role_id": "software-developer"})

    monkeypatch.setattr(llm, "urlopen", provider)
    reply = local_reply(use_model=True, consent=True)
    assert reply["model_info"]["used"] is True
    assert "Software Developer" in reply["answer"]
    assert "PRIVATE INTEREST" not in json.dumps(captured["payload"])
    assert "weekly_hours" not in json.dumps(captured["payload"])
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert reply["sources"]


@pytest.mark.parametrize("selection", [
    {"intent": "roles", "role_id": "fabricated-occupation"},
    {"intent": "roles", "role_id": None, "answer": "You have a 99% replacement risk"},
    {"intent": "invent-statistics", "role_id": None},
    {"intent": ["roles"], "role_id": None},
    ["roles", None],
])
def test_untrusted_model_output_never_becomes_factual_advice(enable_model, monkeypatch, selection):
    monkeypatch.setattr(llm, "urlopen", lambda *args, **kwargs: ProviderResponse(selection))
    reply = local_reply(use_model=True, consent=True)
    assert reply["model_info"]["status"] == "fallback"
    assert "99%" not in reply["answer"]
    assert "fabricated-occupation" not in reply["answer"]


def test_provider_error_is_sanitised_and_local_answer_remains(enable_model, monkeypatch):
    def unavailable(*args, **kwargs):
        raise URLError("do not expose synthetic-test-key or PRIVATE INTEREST")

    monkeypatch.setattr(llm, "urlopen", unavailable)
    reply = local_reply(use_model=True, consent=True)
    assert reply["model_info"]["status"] == "fallback"
    assert "synthetic-test-key" not in json.dumps(reply)
    assert "PRIVATE INTEREST" not in json.dumps(reply)


@pytest.mark.parametrize("options", [{"use_model": "yes"}, {"consent": 1}])
def test_adapter_rejects_truthy_non_boolean_preferences(options):
    with pytest.raises(ValueError, match="true or false"):
        local_reply(**options)
