"""False-negative sweep across topologies × hidden-edge frequency (review P1).

The single-corpus benchmark reports one false-negative number; its value depends
on how many hidden-dependency cases the corpus happens to contain, and on the
topology. This sweep varies both and reports the selective false-negative rate
(with a 95% CI) per condition, alongside full re-execution's own miss rate
against INDEPENDENT ground truth (the oracle-quality check).

Run:  python benchmark/sweep.py [--json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (str(_ROOT), str(_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from benchmark.faults.inject import TOPOLOGIES, make_corpus   # noqa: E402
from benchmark.run_benchmark import run                       # noqa: E402

HIDDEN_FRACTIONS = [0.0, 0.1, 0.25, 0.5]


def sweep(n_reg: int = 20, n_nonreg: int = 5, m: int = 20, seed: int = 1729):
    rows = []
    for topo in TOPOLOGIES:
        for hf in HIDDEN_FRACTIONS:
            n_missing = round(hf * n_reg)
            n_normal = n_reg - n_missing
            corpus = make_corpus(seed=seed, n_normal=n_normal, n_missing=n_missing,
                                 n_nonreg=n_nonreg, m_trajectories=m, topo=topo)
            rep = run(corpus)
            rows.append({
                "topology": topo.name, "hidden_fraction": hf,
                "false_negative": round(rep.missed_regressions, 3),
                "fn_ci": [round(rep.missed_ci_low, 3), round(rep.missed_ci_high, 3)],
                "full_missed": round(rep.full_missed, 3),
                "detection_agreement": round(rep.detection_agreement, 3),
                "call_ratio": round(rep.call_ratio, 3),
            })
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    rows = sweep()
    if "--json" in argv:
        print(json.dumps(rows, indent=2))
        return 0
    print("False-negative sweep — topology × hidden-edge frequency (vs INDEPENDENT truth)")
    print("=" * 78)
    print(f"  {'topology':10s} {'hidden%':>8s} {'false_neg':>10s} {'95% CI':>16s} "
          f"{'full_miss':>10s} {'call_ratio':>11s}")
    for r in rows:
        ci = f"[{r['fn_ci'][0]:.2f},{r['fn_ci'][1]:.2f}]"
        print(f"  {r['topology']:10s} {r['hidden_fraction']*100:7.0f}% "
              f"{r['false_negative']:10.3f} {ci:>16s} {r['full_missed']:10.3f} "
              f"{r['call_ratio']:11.3f}")
    print("=" * 78)
    print("  Reads: selective false-negatives scale with hidden-edge frequency (the")
    print("  declared graph's completeness), NOT with the policy; full_missed ~0 shows")
    print("  full is a sound oracle for these topologies — and the rate is measured")
    print("  against independent ground truth either way.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
