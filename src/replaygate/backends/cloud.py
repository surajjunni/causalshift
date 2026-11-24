"""Cloud recompute backends (OpenAI / Anthropic), stdlib-only (urllib).

The API key is read from the ENVIRONMENT (OPENAI_API_KEY / ANTHROPIC_API_KEY) —
never passed on the command line, never logged, never echoed. Like every
backend, these degrade gracefully: a missing key, network/HTTP error, or an
exhausted call budget returns `Unavailable` (never raises), so a run proceeds
and affected nodes it cannot recompute become inconclusive (fails closed),
never "safe".

SCAFFOLD STATUS: offline-tested for the no-key / budget / response-parsing
paths; NOT exercised against the live OpenAI/Anthropic APIs here (no keys in this
environment). Validate against your account before relying on it.

Prompt construction matches the other backends: the system prompt comes from the
trace's prompt registry (prompt_id → text); the user message is the node's
declared-predecessor outputs. Only the user's own run sends data to the provider.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from replaygate.backends.base import Outcome, Produced, Unavailable
from replaygate.models import Cost


class _CloudBackend:
    env_var = ""        # subclass sets
    default_model = ""
    default_url = ""

    def __init__(self, model: Optional[str] = None, prompts: Optional[dict] = None,
                 max_calls: Optional[int] = None, max_tokens: int = 256,
                 timeout: float = 60.0, base_url: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.model = model or self.default_model
        self.prompts = prompts or {}
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.url = (base_url or self.default_url)
        # read from env if not explicitly provided; value is never stored in logs/output
        self._key = api_key or os.environ.get(self.env_var)
        self.calls = 0
        self.name = f"{self.__class__.__name__}:{self.model}"

    # subclasses implement the request/response wire format
    def _headers(self) -> dict: raise NotImplementedError
    def _body(self, system: str, user: str) -> dict: raise NotImplementedError
    def _parse(self, resp: dict) -> tuple[Optional[str], int]: raise NotImplementedError

    def recompute(self, node_name, model_id, prompt_id, current_outputs,
                  predecessors=None) -> Outcome:
        preds = predecessors if predecessors is not None else list(current_outputs)
        if not preds:   # source node: external input, echoed not regenerated
            return Produced(output=current_outputs.get(node_name, ""), cost=Cost(0, 0.0))
        if not self._key:
            return Unavailable(f"no {self.env_var} in environment")
        if self.max_calls is not None and self.calls >= self.max_calls:
            return Unavailable("recompute budget exhausted")

        system = self.prompts.get(prompt_id, f"You are the '{node_name}' step; "
                                             f"produce only this step's output.")
        user = "Inputs:\n" + "\n".join(f"[{p}]: {current_outputs.get(p, '')}" for p in preds)
        payload = json.dumps(self._body(system, user)).encode()
        req = urllib.request.Request(self.url, data=payload, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode())
            text, tokens = self._parse(body)
            if not text:
                return Unavailable("empty response")
            self.calls += 1
            return Produced(output=text, cost=Cost(tokens=tokens, latency_ms=0.0))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as e:
            return Unavailable(f"{type(e).__name__}: {e}")


class OpenAIBackend(_CloudBackend):
    env_var = "OPENAI_API_KEY"
    default_model = "gpt-4o-mini"
    default_url = "https://api.openai.com/v1/chat/completions"

    def _headers(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"}

    def _body(self, system, user):
        return {"model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}

    def _parse(self, resp):
        text = resp["choices"][0]["message"]["content"].strip()
        tokens = int(resp.get("usage", {}).get("total_tokens", 0))
        return text, tokens


class AnthropicBackend(_CloudBackend):
    env_var = "ANTHROPIC_API_KEY"
    default_model = "claude-3-5-haiku-latest"
    default_url = "https://api.anthropic.com/v1/messages"

    def _headers(self):
        return {"Content-Type": "application/json", "x-api-key": self._key,
                "anthropic-version": "2023-06-01"}

    def _body(self, system, user):
        return {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}

    def _parse(self, resp):
        text = "".join(b.get("text", "") for b in resp.get("content", [])).strip()
        u = resp.get("usage", {})
        tokens = int(u.get("input_tokens", 0)) + int(u.get("output_tokens", 0))
        return text, tokens


def make_cloud_backend(name: str, **kw) -> _CloudBackend:
    return {"openai": OpenAIBackend, "anthropic": AnthropicBackend}[name](**kw)
