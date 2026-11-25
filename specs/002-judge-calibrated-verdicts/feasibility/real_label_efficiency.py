"""Label-efficiency experiment (real data): how many human labels does PPI SAVE?

Same real data as real_summeval.py (SummEval human + G-Eval GPT-4 judge, coherence).
The decision metric per the review: not actionability alone, but the human-label budget PPI
needs to match human-only on accuracy (RMSE) / coverage / false-approval.

NOTE on informativeness: corr(judge Δ, human Δ) is computed on DELTAS over the same
baseline/candidate pairs (H[a]-H[b] vs J[a]-J[b]), not on individual summary scores — the
quantity that matters for a regression verdict.

n_eval is capped at 100 docs/system (SummEval), so label budgets run 10..90.
"""

import json, sys, itertools
import numpy as np

Z = 1.959964
RNG = np.random.default_rng(5)
DIM = "coherence"
MARGIN = 0.20
DRAWS = 400
BUDGETS = [10, 20, 30, 50, 80]
data_dir = sys.argv[1] if len(sys.argv) > 1 else "."


def judge_score(e):
    return float(np.mean([float(x) for x in e["all_responses"]]))


hum = json.load(open(f"{data_dir}/summeval.json"))
jud = json.load(open(f"{data_dir}/gpt4_coh_detailed.json"))
H = {}; J = {}
human = {(e["doc_id"], e["system_id"]): e["scores"][DIM] for e in hum}
judge = {(e["doc_id"], e["system_id"]): judge_score(e) for e in jud}
docs = sorted({d for (d, s) in human}); systems = sorted({s for (d, s) in human})
H = {s: np.array([human[(d, s)] for d in docs]) for s in systems}
J = {s: np.array([judge[(d, s)] for d in docs]) for s in systems}
nD = len(docs)
pairs = list(itertools.permutations(systems, 2))

dh_all = np.concatenate([H[a] - H[b] for a, b in pairs])
dj_all = np.concatenate([J[a] - J[b] for a, b in pairs])
rho_delta = np.corrcoef(dh_all, dj_all)[0, 1]

print("=" * 86)
print(f"LABEL-EFFICIENCY (real: SummEval human vs GPT-4 judge, {DIM})")
print(f"  corr(judge Δ, human Δ) on same baseline/candidate pairs = {rho_delta:.3f}   "
      f"[DELTAS, not scores]")
print(f"  {nD} docs/system, {len(pairs)} changes, {DRAWS} draws/change, margin={MARGIN}")
print("=" * 86)
print(f"  budget | human cov/act/RMSE        | PPI cov/act/RMSE          | PPI eff.  labels saved")
print("  " + "-" * 82)

for n in BUDGETS:
    hc = ha = []; stats = {k: {"cov": [], "act": [], "rmse": []} for k in ("h", "p")}
    for a, b in pairs:
        dh = H[a] - H[b]; dj = J[a] - J[b]; mu = dh.mean()
        jm = dj.mean(); jv = dj.var(ddof=1) / nD
        for _ in range(DRAWS):
            idx = RNG.choice(nD, n, replace=False)
            hl, jl = dh[idx], dj[idx]
            fpc = 1.0 - n / nD   # finite-population correction (labels w/o replacement from N docs)
            mh, sh = hl.mean(), np.sqrt(fpc * hl.var(ddof=1) / n)
            resid = hl - jl
            # PPI var = (1 - n/N) s_resid^2 / n; judge fully observed, no judge-variance term
            mp, sp = jm + resid.mean(), np.sqrt(fpc * resid.var(ddof=1) / n)
            for key, (m, s) in (("h", (mh, sh)), ("p", (mp, sp))):
                lo, hi = m - Z * s, m + Z * s
                stats[key]["cov"].append(lo <= mu <= hi)
                stats[key]["act"].append((lo > -MARGIN) or (hi < -MARGIN))
                stats[key]["rmse"].append((m - mu) ** 2)
    hR = np.sqrt(np.mean(stats["h"]["rmse"])); pR = np.sqrt(np.mean(stats["p"]["rmse"]))
    mult = (hR / pR) ** 2                      # effective-sample multiplier
    equiv = n * mult                           # human labels needed to match PPI@n
    saved = equiv - n
    print(f"   {n:4d}  | {np.mean(stats['h']['cov'])*100:4.1f}% / {np.mean(stats['h']['act'])*100:4.1f}% / {hR:.3f}  "
          f"| {np.mean(stats['p']['cov'])*100:4.1f}% / {np.mean(stats['p']['act'])*100:4.1f}% / {pR:.3f}   "
          f"| {mult:.2f}x    ~{saved:4.1f} ({(1-1/mult)*100:3.0f}%)")
print("  " + "-" * 82)
print("  PPI eff. = (RMSE_human / RMSE_ppi)^2 = human labels equivalent to 1 PPI label.")
print("  'labels saved' = extra human labels needed to match PPI@n accuracy (and % of budget).")
