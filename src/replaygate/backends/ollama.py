"""Live local-model recompute backend (real-world default). Text outputs.

Degrades gracefully: any network/HTTP/timeout error or exhausted budget returns
Unavailable rather than raising, so a run proceeds (affected nodes it cannot
recompute become inconclusive, never 'safe')."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from replaygate.backends.base import Outcome, Produced, Unavailable
from replaygate.models import Cost

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3:latest"


class OllamaBackend:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST,
                 timeout: float = 60.0, num_predict: int = 128,
                 max_calls: Optional[int] = None, prompts: Optional[dict] = None):
        self.model, self.host = model, host.rstrip("/")
        self.timeout, self.num_predict, self.max_calls = timeout, num_predict, max_calls
        self.prompts = prompts or {}   # prompt_id -> system prompt text (from the trace)
        self.calls = 0
        self.name = f"ollama:{model}"

    def recompute(self, node_name, model_id, prompt_id, current_outputs,
                  predecessors=None) -> Outcome:
        # Assemble this node's input from its DECLARED predecessors (what the tool knows).
        preds = predecessors if predecessors is not None else list(current_outputs)
        # A node with no declared inputs is an external input (source): echo it, don't regenerate.
        if not preds:
            return Produced(output=current_outputs.get(node_name, ""), cost=Cost(0, 0.0))
        if self.max_calls is not None and self.calls >= self.max_calls:
            return Unavailable("recompute budget exhausted")
        ctx = "\n".join(f"[{p}]: {current_outputs.get(p, '')}" for p in preds)
        system = self.prompts.get(prompt_id, f"You are the '{node_name}' step; produce only "
                                             f"this step's output.")
        model = model_id if model_id and model_id != "A" else self.model
        prompt = f"{system}\n\nInputs:\n{ctx}\n\nOutput:" if ctx else f"{system}\n\nOutput:"
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False,
                              "options": {"num_predict": self.num_predict}}).encode()
        req = urllib.request.Request(self.host + "/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode())
            text = (body.get("response") or "").strip()
            if not text:
                return Unavailable("empty response")
            self.calls += 1
            return Produced(output=text, cost=Cost(tokens=self.num_predict, latency_ms=0.0))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            return Unavailable(f"{type(e).__name__}: {e}")


def ollama_available(host: str = DEFAULT_HOST, timeout: float = 4.0) -> bool:
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
