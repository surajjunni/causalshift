"""Primary quality gate: selective vs full re-execution on injected faults with
known ground truth. Measures SC-001..SC-004 + the headline false-negative rate.

Run: python benchmark/run_benchmark.py [--json]
Exit non-zero if the measured false-negative bound (SC-002) is exceeded —
the gate must bite (Constitution: Soundness Over Savings)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from causalshift.attribute.causal import attribute          # noqa: E402
from causalshift.evaluate.quality import TerminalSignalEvaluator  # noqa: E402
from causalshift.graph.dag import DependencyGraph           # noqa: E402
from causalshift.models import ComparisonReport             # noqa: E402
from causalshift.replay.engine import full_replay, selective_replay  # noqa: E402
from causalshift.report.verdict import build_verdict        # noqa: E402
from causalshift.soundness.ledger import false_negative_rate  # noqa: E402
from benchmark.faults.inject import make_corpus             # noqa: E402

# SC targets (spec Success Criteria)
SC = {"agreement": 0.95, "false_neg": 0.05, "call_ratio": 0.50, "attribution": 0.80}


def run(corpus=None):
    corpus = corpus or make_corpus()
    evaluator = TerminalSignalEvaluator(target="leaf")
    sel_reg, full_reg = [], []
    attr_hits = attr_total = 0
    sc = fc = st = ft = 0
    sl = fl = 0.0

    for case in corpus:
        graph = DependencyGraph(case.workflow)
        full_results, sel_results = [], []
        for t in case.workflow.trajectories:
            full_results.append(full_replay(t, graph, case.intervention, case.backend, evaluator))
            sel_results.append(selective_replay(t, graph, case.intervention, case.backend, evaluator))
        fv = build_verdict(case.case_id, "full", full_results)
        sv = build_verdict(case.case_id, "selective", sel_results)
        full_reg.append(fv.regressed)
        sel_reg.append(sv.regressed)
        sc += sum(r.calls for r in sel_results); fc += sum(r.calls for r in full_results)
        st += sum(r.tokens for r in sel_results); ft += sum(r.tokens for r in full_results)
        sl += sum(r.latency_ms for r in sel_results); fl += sum(r.latency_ms for r in full_results)

        if case.regresses:
            attr_total += 1
            ranked = attribute(case.workflow.trajectories, graph, case.intervention,
                               case.backend, evaluator)
            if ranked and ranked[0][0] == case.fault_node:
                attr_hits += 1

    n = len(corpus)
    agreement = sum(1 for s, f in zip(sel_reg, full_reg) if s == f) / n
    fn = false_negative_rate(sel_reg, full_reg)
    attribution_acc = attr_hits / attr_total if attr_total else 1.0

    return ComparisonReport(
        n_cases=n, detection_agreement=agreement, missed_regressions=fn,
        attribution_accuracy=attribution_acc,
        selective_calls=sc, full_calls=fc, selective_tokens=st, full_tokens=ft,
        selective_latency_ms=sl, full_latency_ms=fl,
    )


def _gate(rep: ComparisonReport) -> bool:
    checks = [
        ("SC-001 detection_agreement ≥ 0.95", rep.detection_agreement >= SC["agreement"]),
        ("SC-002 false_negative ≤ 0.05", rep.missed_regressions <= SC["false_neg"]),
        ("SC-003 call_ratio ≤ 0.50", rep.call_ratio <= SC["call_ratio"]),
        ("SC-004 attribution ≥ 0.80", rep.attribution_accuracy >= SC["attribution"]),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    # Only the false-negative bound HARD-fails the gate (soundness is non-negotiable).
    return rep.missed_regressions <= SC["false_neg"]


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    as_json = "--json" in argv
    rep = run()
    if as_json:
        print(json.dumps(rep.__dict__ | {"call_ratio": rep.call_ratio}, indent=2))
    else:
        print("CausalShift benchmark — selective vs full (measured, ground truth)")
        print("=" * 64)
        print(f"  cases                 {rep.n_cases}")
        print(f"  detection_agreement   {rep.detection_agreement:.3f}")
        print(f"  missed_regressions    {rep.missed_regressions:.3f}   (HEADLINE false-negative)")
        print(f"  attribution_accuracy  {rep.attribution_accuracy:.3f}")
        print(f"  calls selective/full  {rep.selective_calls}/{rep.full_calls}  "
              f"(ratio {rep.call_ratio:.3f})")
        print(f"  latency sel/full ms   {rep.selective_latency_ms:.0f}/{rep.full_latency_ms:.0f}")
        print("=" * 64)
    ok = _gate(rep)
    print("GATE: PASS" if ok else "GATE: FAIL (false-negative bound exceeded)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
