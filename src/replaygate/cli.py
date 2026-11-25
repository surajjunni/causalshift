"""ReplayGate CLI (contracts/cli.md): ingest / evaluate / benchmark."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from replaygate.attribute.causal import attribute
from replaygate.backends.base import UnavailableBackend
from replaygate.evaluate.quality import TerminalSignalEvaluator
from replaygate.graph.dag import DependencyGraph
from replaygate.intervene.apply import validate_intervention
from replaygate.models import Intervention
from replaygate.replay.engine import full_replay, selective_replay
from replaygate.report.diff import diff_report
from replaygate.report.verdict import build_verdict, format_verdict, verdict_exit_code
from replaygate.store.db import TraceStore, load_workflow
from replaygate.store.validate import TraceInputError


def _nonneg_float(s: str) -> float:
    v = float(s)
    if not math.isfinite(v) or v < 0:
        raise argparse.ArgumentTypeError("must be a finite number >= 0")
    return v


def _pos_int(s: str) -> int:
    v = int(s)
    if v < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return v

DEFAULT_DB = "replaygate.db"


def _backend(name: str, prompts: dict, model: str, max_calls):
    if name == "ollama":
        from replaygate.backends.ollama import OllamaBackend, ollama_available
        if not ollama_available():
            print("  [warn] Ollama not reachable; affected nodes will be inconclusive",
                  file=sys.stderr)
        return OllamaBackend(model=model, prompts=prompts, max_calls=max_calls)
    if name in ("openai", "anthropic"):
        from replaygate.backends.cloud import make_cloud_backend
        # if --model wasn't overridden from the ollama default, use the provider default
        m = None if model == "llama3:latest" else model
        return make_cloud_backend(name, model=m, prompts=prompts, max_calls=max_calls)
    return UnavailableBackend()


def _evaluator(name: str, model: str):
    if name == "judge":
        from replaygate.evaluate.judge import OllamaJudge
        return OllamaJudge(model=model)
    return TerminalSignalEvaluator()


def _cmd_ingest(args) -> int:
    try:
        wf = load_workflow(args.input)
    except TraceInputError as e:
        print(f"ingest rejected: {e}", file=sys.stderr)
        return 2
    TraceStore(args.db).ingest(wf)
    print(f"ingested workflow {wf.workflow_id!r}: {len(wf.nodes)} nodes, "
          f"{len(wf.trajectories)} trajectories → {args.db}")
    return 0


def _cmd_evaluate(args) -> int:
    wf = TraceStore(args.db).hydrate(args.workflow)
    if not wf.nodes:
        print(f"workflow {args.workflow!r} not found in {args.db}", file=sys.stderr)
        return 2
    with open(args.intervention) as f:
        spec = json.load(f)
    intervention = Intervention(workflow_id=wf.workflow_id, targets=spec["targets"])
    graph = DependencyGraph(wf)
    validate_intervention(intervention, graph)
    # a candidate intervention may introduce new prompt ids: merge them into the registry
    prompts = dict(wf.prompts)
    prompts.update(spec.get("prompts", {}))
    backend = _backend(args.backend, prompts, args.model, args.max_recompute)
    evaluator = _evaluator(args.evaluator, args.judge_model)

    replay = full_replay if args.mode == "full" else selective_replay
    results = [replay(t, graph, intervention, backend, evaluator) for t in wf.trajectories]
    ranked = None if args.no_attribution else \
        attribute(wf.trajectories, graph, intervention, backend, evaluator)
    verdict = build_verdict(wf.workflow_id, args.mode, results, attribution=ranked)
    print(f"  [backend recompute calls: {getattr(backend, 'calls', 0)}]", file=sys.stderr)

    if args.json:
        print(json.dumps(verdict.__dict__, indent=2, default=list))
    else:
        print(format_verdict(verdict))
    # Fail closed: inconclusive → exit 2 (never a silent pass), regressed → 1, else 0.
    return verdict_exit_code(verdict)


def _cmd_diff(args) -> int:
    """One-command 'is this change safe?' report (selective mode)."""
    wf = TraceStore(args.db).hydrate(args.workflow)
    if not wf.nodes:
        print(f"workflow {args.workflow!r} not found in {args.db}", file=sys.stderr)
        return 2
    with open(args.intervention) as f:
        spec = json.load(f)
    intervention = Intervention(workflow_id=wf.workflow_id, targets=spec["targets"])
    graph = DependencyGraph(wf)
    validate_intervention(intervention, graph)
    prompts = dict(wf.prompts)
    prompts.update(spec.get("prompts", {}))
    backend = _backend(args.backend, prompts, args.model, args.max_recompute)
    evaluator = _evaluator(args.evaluator, args.judge_model)

    results = [selective_replay(t, graph, intervention, backend, evaluator)
               for t in wf.trajectories]
    verdict = build_verdict(wf.workflow_id, "selective", results,
                            min_samples=args.min_samples, epsilon=args.margin)
    selective_calls = sum(r.calls for r in results)
    # Fair full-baseline estimate: every non-source node recomputes once per trajectory.
    full_estimate = sum(1 for t in wf.trajectories for s in t.steps
                        if graph.predecessors(s.node_name))
    if args.json:
        print(json.dumps(verdict.__dict__ | {
            "selective_calls": selective_calls, "full_estimate": full_estimate,
            "targets": list(intervention.targets), "margin": args.margin,
            "dependency_coverage": wf.dependency_coverage}, indent=2, default=list))
    else:
        print(diff_report(verdict, list(intervention.targets), selective_calls, full_estimate,
                          margin=args.margin, min_samples=args.min_samples, fmt=args.format,
                          dependency_coverage=wf.dependency_coverage))
    return verdict_exit_code(verdict)


def _cmd_benchmark(args) -> int:
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from benchmark.run_benchmark import main as bench_main
    except ImportError:
        print("benchmark package not found; run `python benchmark/run_benchmark.py` "
              "from the repo root instead", file=sys.stderr)
        return 2
    return bench_main(["--json"] if args.json else [])


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="replaygate")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="validate + load instrumented trajectories")
    p_ing.add_argument("input")
    p_ing.add_argument("--db", default=DEFAULT_DB)
    p_ing.set_defaults(func=_cmd_ingest)

    p_ev = sub.add_parser("evaluate", help="run a regression evaluation for an intervention")
    p_ev.add_argument("--workflow", required=True)
    p_ev.add_argument("--intervention", required=True)
    p_ev.add_argument("--db", default=DEFAULT_DB)
    p_ev.add_argument("--mode", choices=["full", "selective"], default="full")
    p_ev.add_argument("--backend", choices=["none", "ollama", "openai", "anthropic"], default="none")
    p_ev.add_argument("--evaluator", choices=["signal", "judge"], default="signal")
    p_ev.add_argument("--model", default="llama3:latest", help="recompute model (ollama)")
    p_ev.add_argument("--judge-model", default="llama3:latest")
    p_ev.add_argument("--max-recompute", type=int, default=None,
                      help="cap live recompute calls")
    p_ev.add_argument("--no-attribution", action="store_true",
                      help="skip attribution (cheaper; US2 off)")
    p_ev.add_argument("--json", action="store_true")
    p_ev.set_defaults(func=_cmd_evaluate)

    p_df = sub.add_parser("diff", help="one-command 'is this change safe?' risk report")
    p_df.add_argument("--workflow", required=True)
    p_df.add_argument("--intervention", required=True)
    p_df.add_argument("--db", default=DEFAULT_DB)
    p_df.add_argument("--backend", choices=["none", "ollama", "openai", "anthropic"], default="none")
    p_df.add_argument("--evaluator", choices=["signal", "judge"], default="signal")
    p_df.add_argument("--model", default="llama3:latest")
    p_df.add_argument("--judge-model", default="llama3:latest")
    p_df.add_argument("--max-recompute", type=int, default=None)
    p_df.add_argument("--margin", type=_nonneg_float, default=0.0,
                      help="non-inferiority margin (>= 0): PASS needs the 95%% CI to stay above -margin")
    p_df.add_argument("--min-samples", type=_pos_int, default=3,
                      help="minimum usable trajectories (>= 1); fewer → INCONCLUSIVE (fail closed)")
    p_df.add_argument("--format", choices=["text", "markdown"], default="text",
                      help="human-readable output format (use --json for machine-readable)")
    p_df.add_argument("--json", action="store_true")
    p_df.set_defaults(func=_cmd_diff)

    p_bn = sub.add_parser("benchmark", help="run the injected-fault gate (selective vs full)")
    p_bn.add_argument("--json", action="store_true")
    p_bn.set_defaults(func=_cmd_benchmark)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
