# Contract: Recompute Backend

The pluggable interface the selective/full replay engines call to recompute a
node under an intervention. Tier-1 recompute is **live-only** and MUST degrade
gracefully (Constitution: Measured/Soundness).

## Interface

```
recompute(node_name: str,
          model_id: str,
          prompt_id: str,
          inputs: <node inputs assembled by the replay engine>) -> Outcome
```

`Outcome` is one of:
- `Produced(output: str, cost: {tokens, latency_ms})` — a real output.
- `Unavailable(reason: str)` — backend could not produce (not running, missing
  model, timeout, budget exhausted, error).

## Rules

- A backend MUST NOT raise for ordinary unavailability; it returns
  `Unavailable`. The replay engine treats `Unavailable` as "cannot recompute
  this node," which — because an un-recomputable affected node cannot be made
  sound — marks the trajectory's verdict for that node as **inconclusive**,
  never as "safe." Soundness is never satisfied by giving up.
- Backends MUST be deterministic enough to be seedable for the benchmark, or the
  benchmark MUST record that a backend is stochastic and account for it via the
  population CIs.
- Default backend: a thin local-model client (e.g. Ollama over `urllib`). A
  `max_calls` budget bounds live cost; exceeding it returns `Unavailable`.

## Non-goal

- The backend does not judge quality. Quality scoring is a separate configured
  evaluator applied equally to baseline and candidate outputs.
