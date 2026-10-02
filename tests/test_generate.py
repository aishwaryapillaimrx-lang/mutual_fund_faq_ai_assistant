from types import SimpleNamespace

import pytest
import groq

from app import config
from app.rag import generate
from app.rag.prompt import SYSTEM_PROMPT


def test_fallback_sends_system_message_and_rejects_truncation(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    finish_reason = "stop"

    def create(*, model, max_tokens, messages, temperature, reasoning_effort):
        assert temperature == 0
        assert reasoning_effort == "low"
        assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert messages[1]["role"] == "user"
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason=finish_reason,
            message=SimpleNamespace(content="SOURCE: 1\nLock-in is 3 years."),
        )])

    monkeypatch.setattr(groq, "Groq", lambda **kwargs: SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
    ))
    assert generate.generate_answer("ELSS lock-in?", []).endswith("3 years.")
    finish_reason = "length"
    with pytest.raises(generate.GenerationError):
        generate.generate_answer("ELSS lock-in?", [])


def test_anthropic_failure_uses_groq(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    def create(**kwargs):
        raise generate.anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(generate.anthropic, "Anthropic", lambda **kwargs:
        SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(generate, "_try_groq", lambda q, chunks: "Fallback answer.")
    assert generate.generate_answer("ELSS lock-in?", []) == "Fallback answer."


@pytest.mark.parametrize("retry_after, expected_calls", [("2", 2), ("60", 1), ("nan", 1)])
def test_rate_limit_retry_is_bounded(monkeypatch, retry_after, expected_calls):
    import httpx
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-key")
    calls = []
    sleeps = []
    def create(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            response = httpx.Response(429, headers={"retry-after": retry_after},
                request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
            raise groq.RateLimitError("rate limited", response=response, body=None)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",
            message=SimpleNamespace(content="Answer."))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = lambda **kwargs: client
    monkeypatch.setattr(groq, "Groq", lambda **kwargs: client)
    monkeypatch.setattr(generate.time, "sleep", sleeps.append)
    answer = generate._try_groq("benchmark?", [])
    assert len(calls) == expected_calls
    assert sleeps == ([2.0] if expected_calls == 2 else [])
    assert answer == ("Answer." if expected_calls == 2 else None)
