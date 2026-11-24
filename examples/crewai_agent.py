"""Capture a CausalShift trace from CrewAI.

Runs with NO crewai install: it uses stand-in Task / CrewOutput objects that
mirror CrewAI's real shape (Task.name, Task.context, CrewOutput.tasks_output[].raw)
so you can see the adapter end to end. With real CrewAI, delete the stand-ins
and use the commented call — CrewAI's `context` is a true data dependency, so it
maps directly onto declared dependency edges.

    python examples/crewai_agent.py     # -> examples/crewai_trace.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from causalshift.adapters.crewai import trace_from_crewai  # noqa: E402


def main() -> int:
    # mirror CrewAI Task objects (name + context = upstream tasks it depends on)
    research = SimpleNamespace(name="research", context=[])
    outline = SimpleNamespace(name="outline", context=[research])
    write = SimpleNamespace(name="write", context=[outline, research])
    tasks = [research, outline, write]

    # --- with real CrewAI, replace the stand-ins with: ---
    #   crew_output = crew.kickoff(inputs={...})
    crew_output = SimpleNamespace(tasks_output=[
        SimpleNamespace(raw="findings: ..."),
        SimpleNamespace(raw="outline: ..."),
        SimpleNamespace(raw="final article ..."),
    ])

    trace = trace_from_crewai(tasks, crew_output, workflow_id="crewai_writer")
    out = _ROOT / "examples" / "crewai_trace.json"
    out.write_text(json.dumps(trace, indent=2))
    print(f"captured {len(trace['trajectories'])} trajectory from CrewAI tasks → {out}")
    print(f"  nodes: {trace['graph']['nodes']}")
    print(f"  edges: {trace['graph']['edges']}   (task.context → dependency edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
