"""Cloud backends: graceful fallback + response parsing, with NO live API calls."""

import json

import causalshift.backends.cloud as cloud
from causalshift.backends.base import Produced, Unavailable
from causalshift.backends.cloud import AnthropicBackend, OpenAIBackend


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(payload):
    def _open(req, timeout=None):
        return _Resp(payload)
    return _open


def test_no_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = OpenAIBackend(prompts={}, api_key=None)
    out = b.recompute("gen", "m", "p", {"ctx": "x"}, ["ctx"])
    assert isinstance(out, Unavailable) and "OPENAI_API_KEY" in out.reason


def test_source_node_is_echoed_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    b = OpenAIBackend()
    out = b.recompute("root", "m", "p", {"root": "seed"}, [])   # no predecessors = source
    assert isinstance(out, Produced) and out.output == "seed"


def test_budget_exhausted_is_unavailable():
    b = OpenAIBackend(api_key="sk-test", max_calls=0)
    out = b.recompute("gen", "m", "p", {"ctx": "x"}, ["ctx"])
    assert isinstance(out, Unavailable) and "budget" in out.reason


def test_openai_parse_success(monkeypatch):
    payload = {"choices": [{"message": {"content": "  hello  "}}],
               "usage": {"total_tokens": 42}}
    monkeypatch.setattr(cloud.urllib.request, "urlopen", _fake_urlopen(payload))
    b = OpenAIBackend(api_key="sk-test", prompts={"p": "be brief"})
    out = b.recompute("gen", "m", "p", {"ctx": "x"}, ["ctx"])
    assert isinstance(out, Produced) and out.output == "hello" and out.cost.tokens == 42
    assert b.calls == 1


def test_anthropic_parse_success(monkeypatch):
    payload = {"content": [{"type": "text", "text": "answer"}],
               "usage": {"input_tokens": 3, "output_tokens": 7}}
    monkeypatch.setattr(cloud.urllib.request, "urlopen", _fake_urlopen(payload))
    b = AnthropicBackend(api_key="k", prompts={})
    out = b.recompute("gen", "m", "p", {"ctx": "x"}, ["ctx"])
    assert isinstance(out, Produced) and out.output == "answer" and out.cost.tokens == 10


def test_http_error_is_unavailable(monkeypatch):
    def _boom(req, timeout=None):
        raise OSError("connection refused")
    monkeypatch.setattr(cloud.urllib.request, "urlopen", _boom)
    b = OpenAIBackend(api_key="sk-test")
    out = b.recompute("gen", "m", "p", {"ctx": "x"}, ["ctx"])
    assert isinstance(out, Unavailable)
