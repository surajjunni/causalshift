"""CrewAI → CausalShift trace.

CrewAI is task-based: a Task may declare `context=[other_task, ...]`, which is an
EXPLICIT data dependency (unlike control-flow spans), so CrewAI maps unusually
cleanly — those context links become the declared dependency edges.

    trace = trace_from_crewai(tasks=[t1, t2, t3], crew_output=crew.kickoff())

`tasks` is the ordered list of CrewAI Task objects; `crew_output` is the
CrewOutput returned by `crew.kickoff()` (its `.tasks_output[i].raw` aligns with
`tasks[i]`). Produces a single-trajectory trace; call once per run and merge, or
pass several runs via `extra_runs`. Validated against CrewAI's documented Task/
CrewOutput shape — confirm against your CrewAI version. DAG-only (task context
must be acyclic)."""

from __future__ import annotations

from causalshift.adapters.spans import _as_str, _attr
from causalshift.replay.validity import fingerprint


def _task_name(task, idx: int) -> str:
    name = _attr(task, "name")
    if name:
        return str(name)
    desc = _attr(task, "description")
    return (str(desc)[:40] if desc else f"task_{idx}")


def _run_outputs(tasks, crew_output) -> dict[str, str]:
    outs = _attr(crew_output, "tasks_output") or []
    result = {}
    for i, task in enumerate(tasks):
        name = _task_name(task, i)
        to = outs[i] if i < len(outs) else None
        result[name] = _as_str(_attr(to, "raw") if to is not None else "")
    return result


def trace_from_crewai(tasks, crew_output, workflow_id: str = "crewai",
                      extra_runs=None, model_id: str = "task",
                      prompt_id: str = "default") -> dict:
    names = [_task_name(t, i) for i, t in enumerate(tasks)]
    name_set = set(names)
    edges = set()
    for i, t in enumerate(tasks):
        for c in (_attr(t, "context") or []):
            cn = _task_name(c, -1)
            if cn in name_set:
                edges.add((cn, names[i]))
    preds = {n: [s for s, d in edges if d == n] for n in names}

    runs = [crew_output] + list(extra_runs or [])
    trajectories = []
    for ri, out in enumerate(runs):
        outputs = _run_outputs(tasks, out)
        steps = []
        for i, name in enumerate(names):
            p = {d: outputs[d] for d in preds[name] if d in outputs}
            o = outputs.get(name, "")
            steps.append({
                "step_index": i, "node_name": name,
                "input_fingerprint": fingerprint(name, model_id, prompt_id, p),
                "output": o, "model_id": model_id, "prompt_id": prompt_id,
                "cost": {"tokens": max(1, len(o) // 4), "latency_ms": 0.0},
            })
        trajectories.append({"trajectory_id": f"{workflow_id}-t{ri}", "steps": steps})

    return {
        "workflow_id": workflow_id,
        "graph": {"nodes": names, "edges": [list(e) for e in sorted(edges)]},
        "prompts": {},
        "trajectories": trajectories,
    }
