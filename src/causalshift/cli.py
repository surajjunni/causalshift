"""CausalShift CLI (contracts/cli.md): ingest / evaluate / benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from causalshift.attribute.causal import attribute
from causalshift.backends.base import UnavailableBackend
from causalshift.evaluate.quality import TerminalSignalEvaluator
from causalshift.graph.dag import DependencyGraph
from causalshift.intervene.apply import validate_intervention
from causalshift.models import Intervention
from causalshift.replay.engine import full_replay, selective_replay
from causalshift.report.verdict import build_verdict, format_verdict
from causalshift.store.db import TraceStore, load_workflow
from causalshift.store.validate import TraceInputError

DEFAULT_DB = "causalshift.db"


def _backend(name: str, prompts: dict, model: str, max_calls):
    if name == "ollama":
        from causalshift.backends.ollama import OllamaBackend, ollama_available
        if not ollama_available():
            print("  [warn] Ollama not reachable; affected nodes will be inconclusive",
                  file=sys.stderr)
        return OllamaBackend(model=model, prompts=prompts, max_calls=max_calls)
    return UnavailableBackend()


def _evaluator(name: str, model: str):
    if name == "judge":
        from causalshift.evaluate.judge import OllamaJudge
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
    return 1 if verdict.regressed else 0


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
    ap = argparse.ArgumentParser(prog="causalshift")
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
    p_ev.add_argument("--backend", choices=["none", "ollama"], default="none")
    p_ev.add_argument("--evaluator", choices=["signal", "judge"], default="signal")
    p_ev.add_argument("--model", default="llama3:latest", help="recompute model (ollama)")
    p_ev.add_argument("--judge-model", default="llama3:latest")
    p_ev.add_argument("--max-recompute", type=int, default=None,
                      help="cap live recompute calls")
    p_ev.add_argument("--no-attribution", action="store_true",
                      help="skip attribution (cheaper; US2 off)")
    p_ev.add_argument("--json", action="store_true")
    p_ev.set_defaults(func=_cmd_evaluate)

    p_bn = sub.add_parser("benchmark", help="run the injected-fault gate (selective vs full)")
    p_bn.add_argument("--json", action="store_true")
    p_bn.set_defaults(func=_cmd_benchmark)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
