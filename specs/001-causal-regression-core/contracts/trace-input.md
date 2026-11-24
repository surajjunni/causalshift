# Contract: Instrumented Trajectory Input

The input a user supplies to ReplayGate. This is a **contract**, not an
implementation — any producer (an instrumentation seam, an adapter from another
trace format) must satisfy it. See [data-model.md](../data-model.md) for entity
semantics.

## Document shape (one workflow's trajectories)

```json
{
  "workflow_id": "string",
  "graph": {
    "nodes": ["node_name", "..."],
    "edges": [["src_node", "dst_node"], "..."]
  },
  "trajectories": [
    {
      "trajectory_id": "string",
      "steps": [
        {
          "step_index": 0,
          "node_name": "string",
          "input_fingerprint": "string",
          "output": "string",
          "model_id": "string",
          "prompt_id": "string",
          "cost": { "tokens": 0, "latency_ms": 0.0 }
        }
      ],
      "ground_truth": {
        "fault_node": "string|null",
        "regresses": true
      }
    }
  ]
}
```

## Requirements on a valid input

- `graph.edges` MUST be acyclic. A cyclic graph is **rejected** (FR-011); the
  tool does not analyze it.
- Every step's `input_fingerprint` MUST be present. It must change iff the
  step's real inputs change — this is what the validity predicate relies on. A
  step without it is never reused (always recomputed when in scope).
- Every `node_name` used in steps MUST appear in `graph.nodes`.
- `model_id` / `prompt_id` identify what an intervention can target.
- `ground_truth` is OPTIONAL and present only for benchmark cases; it is never
  read by the verdict path, only by the benchmark scorer.

## Out of contract (rejected or flagged, not analyzed)

- Cyclic graphs; trajectories whose steps revisit a node (loops).
- Opaque-stateful steps whose dependencies cannot be declared as edges.
