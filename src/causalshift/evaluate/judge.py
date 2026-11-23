"""LLM-as-judge quality evaluator for TEXT traces (live, via Ollama).

Scores the response node's output in [0,1]. It is applied IDENTICALLY to
baseline and candidate outputs. HONEST LIMITATION: the judge is itself
stochastic, so a single score carries noise that the population bootstrap CI
(variation across trajectories) does not fully capture; average several judge
calls (k>1) to reduce it. Falls back to 0.0 on an unparseable/failed call."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Optional

from causalshift.graph.dag import DependencyGraph

_NUM = re.compile(r"(?<![\d.])(0(?:\.\d+)?|1(?:\.0+)?)")


class OllamaJudge:
    name = "ollama-judge"

    def __init__(self, model: str = "llama3:latest", host: str = "http://localhost:11434",
                 target: Optional[str] = None, k: int = 1, timeout: float = 60.0):
        self.model, self.host = model, host.rstrip("/")
        self.target, self.k, self.timeout = target, max(1, k), timeout

    def _one(self, answer: str, context: str) -> Optional[float]:
        prompt = ("You are a strict grader. Rate the ANSWER's quality for the task on a "
                  "scale from 0.0 (useless/wrong) to 1.0 (excellent). Reply with ONLY the "
                  f"number.\nContext:\n{context}\nANSWER:\n{answer}\n\nScore:")
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False,
                              "options": {"num_predict": 8, "temperature": 0}}).encode()
        req = urllib.request.Request(self.host + "/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                txt = (json.loads(r.read().decode()).get("response") or "")
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return None
        m = _NUM.search(txt)
        return float(m.group(1)) if m else None

    def score(self, outputs: dict[str, str], graph: DependencyGraph) -> float:
        target = self.target or (graph.terminal_nodes() or [None])[0]
        answer = outputs.get(target, "") if target else ""
        context = "\n".join(f"[{k}]: {v}" for k, v in outputs.items() if k != target)
        vals = [v for v in (self._one(answer, context) for _ in range(self.k)) if v is not None]
        return sum(vals) / len(vals) if vals else 0.0
