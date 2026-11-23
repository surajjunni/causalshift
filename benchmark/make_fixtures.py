"""Emit the quickstart fixtures from the corpus generator (deterministic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from benchmark.faults.inject import case_to_input_dict, make_corpus  # noqa: E402

OUT = _ROOT / "benchmark" / "fixtures"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = make_corpus(n_normal=1, n_missing=0, n_nonreg=0, m_trajectories=30)
    case = corpus[0]
    wf = case_to_input_dict(case)
    wf["workflow_id"] = "demo"
    for t in wf["trajectories"]:
        t["trajectory_id"] = t["trajectory_id"].replace(case.case_id, "demo")
    (OUT / "demo_workflow.json").write_text(json.dumps(wf, indent=2))
    (OUT / "demo_intervention.json").write_text(json.dumps(
        {"workflow_id": "demo", "targets": {"mid": {"model_id": "B"}}}, indent=2))
    # An out-of-contract (cyclic) workflow for the rejection check.
    (OUT / "cyclic_workflow.json").write_text(json.dumps({
        "workflow_id": "cyclic",
        "graph": {"nodes": ["a", "b"], "edges": [["a", "b"], ["b", "a"]]},
        "trajectories": [],
    }, indent=2))
    print(f"wrote demo_workflow.json, demo_intervention.json, cyclic_workflow.json → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
