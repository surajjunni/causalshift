"""Trace store: load instrumented trajectories (contracts/trace-input.md) and
persist/hydrate them in SQLite (normalized, ordinal-preserving; DuckDB-swappable)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Union

from replaygate.models import (
    Cost, GroundTruth, Step, Trajectory, Workflow,
)
from replaygate.store.validate import TraceInputError, validate_workflow


def workflow_from_dict(raw: dict) -> Workflow:
    try:
        wf_id = raw["workflow_id"]
        nodes = list(raw["graph"]["nodes"])
        edges = [tuple(e) for e in raw["graph"]["edges"]]
    except (KeyError, TypeError) as e:
        raise TraceInputError(f"malformed input: {e}") from e

    trajectories: list[Trajectory] = []
    for t in raw.get("trajectories", []):
        steps = []
        for s in t["steps"]:
            c = s.get("cost", {}) or {}
            steps.append(Step(
                step_index=s["step_index"],
                node_name=s["node_name"],
                input_fingerprint=s.get("input_fingerprint", ""),
                output=s["output"],
                model_id=s.get("model_id", "default"),
                prompt_id=s.get("prompt_id", "default"),
                cost=Cost(tokens=c.get("tokens", 0), latency_ms=c.get("latency_ms", 0.0)),
            ))
        gt = None
        if t.get("ground_truth"):
            gt = GroundTruth(
                fault_node=t["ground_truth"].get("fault_node"),
                regresses=bool(t["ground_truth"].get("regresses", False)),
            )
        trajectories.append(Trajectory(
            trajectory_id=t["trajectory_id"], workflow_id=wf_id,
            steps=steps, ground_truth=gt,
        ))

    wf = Workflow(workflow_id=wf_id, nodes=nodes, edges=edges, trajectories=trajectories,
                  prompts=dict(raw.get("prompts", {})))
    validate_workflow(wf)   # raises TraceInputError on out-of-contract input
    return wf


def load_workflow(path: Union[str, Path]) -> Workflow:
    with open(path) as f:
        return workflow_from_dict(json.load(f))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows(workflow_id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS nodes(workflow_id TEXT, ordinal INT, node_name TEXT);
CREATE TABLE IF NOT EXISTS edges(workflow_id TEXT, ordinal INT, src TEXT, dst TEXT);
CREATE TABLE IF NOT EXISTS trajectories(
    workflow_id TEXT, trajectory_id TEXT, ordinal INT,
    fault_node TEXT, regresses INT);
CREATE TABLE IF NOT EXISTS steps(
    workflow_id TEXT, trajectory_id TEXT, step_index INT, node_name TEXT,
    input_fingerprint TEXT, output TEXT, model_id TEXT, prompt_id TEXT,
    tokens INT, latency_ms REAL);
CREATE TABLE IF NOT EXISTS prompts(workflow_id TEXT, prompt_id TEXT, text TEXT);
"""


class TraceStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    def ingest(self, wf: Workflow) -> None:
        validate_workflow(wf)
        c = self.conn
        for tbl in ("steps", "trajectories", "edges", "nodes", "prompts", "workflows"):
            c.execute(f"DELETE FROM {tbl} WHERE workflow_id=?", (wf.workflow_id,))
        c.execute("INSERT INTO workflows VALUES(?)", (wf.workflow_id,))
        c.executemany("INSERT INTO prompts VALUES(?,?,?)",
                      [(wf.workflow_id, pid, txt) for pid, txt in wf.prompts.items()])
        c.executemany("INSERT INTO nodes VALUES(?,?,?)",
                      [(wf.workflow_id, i, n) for i, n in enumerate(wf.nodes)])
        c.executemany("INSERT INTO edges VALUES(?,?,?,?)",
                      [(wf.workflow_id, i, s, d) for i, (s, d) in enumerate(wf.edges)])
        for ti, t in enumerate(wf.trajectories):
            c.execute("INSERT INTO trajectories VALUES(?,?,?,?,?)", (
                wf.workflow_id, t.trajectory_id, ti,
                t.ground_truth.fault_node if t.ground_truth else None,
                int(t.ground_truth.regresses) if t.ground_truth else None,
            ))
            c.executemany("INSERT INTO steps VALUES(?,?,?,?,?,?,?,?,?,?)", [
                (wf.workflow_id, t.trajectory_id, s.step_index, s.node_name,
                 s.input_fingerprint, s.output, s.model_id, s.prompt_id,
                 s.cost.tokens, s.cost.latency_ms) for s in t.steps
            ])
        c.commit()

    def hydrate(self, workflow_id: str) -> Workflow:
        c = self.conn
        nodes = [r["node_name"] for r in c.execute(
            "SELECT node_name FROM nodes WHERE workflow_id=? ORDER BY ordinal", (workflow_id,))]
        edges = [(r["src"], r["dst"]) for r in c.execute(
            "SELECT src,dst FROM edges WHERE workflow_id=? ORDER BY ordinal", (workflow_id,))]
        trajs = []
        trows = c.execute(
            "SELECT trajectory_id,fault_node,regresses FROM trajectories "
            "WHERE workflow_id=? ORDER BY ordinal", (workflow_id,)).fetchall()
        for tr in trows:
            srows = c.execute(
                "SELECT * FROM steps WHERE workflow_id=? AND trajectory_id=? ORDER BY step_index",
                (workflow_id, tr["trajectory_id"])).fetchall()
            steps = [Step(
                step_index=s["step_index"], node_name=s["node_name"],
                input_fingerprint=s["input_fingerprint"], output=s["output"],
                model_id=s["model_id"], prompt_id=s["prompt_id"],
                cost=Cost(tokens=s["tokens"], latency_ms=s["latency_ms"]),
            ) for s in srows]
            gt = None
            if tr["regresses"] is not None:
                gt = GroundTruth(fault_node=tr["fault_node"], regresses=bool(tr["regresses"]))
            trajs.append(Trajectory(tr["trajectory_id"], workflow_id, steps, gt))
        prompts = {r["prompt_id"]: r["text"] for r in c.execute(
            "SELECT prompt_id,text FROM prompts WHERE workflow_id=?", (workflow_id,))}
        return Workflow(workflow_id, nodes, edges, trajs, prompts=prompts)
