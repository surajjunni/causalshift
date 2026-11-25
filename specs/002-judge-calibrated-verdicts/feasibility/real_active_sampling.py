"""Active human-label selection (real data): can it beat random PPI's 1.28x, and does
naive (unweighted) active selection destroy coverage? (Reviewer's open question.)

Same real data (SummEval human + G-Eval GPT-4, coherence). Selection signal = judge
uncertainty per doc = std of the judge's 20 raw ratings (where the judge is shaky, the
human label is most informative). Three estimators at a fixed budget:

  1. random PPI        — random n docs, unweighted residual correction (the 1.28x baseline)
  2. naive active      — top-n most-uncertain docs, UNWEIGHTED (expected: lower RMSE but biased)
  3. PPS active        — sample n docs with prob proportional to uncertainty, Hajek-reweighted residual

EXPLORATORY ONLY. The active rows are not a validated design-based analysis: the top-uncertain
selection is deterministic (identical across draws), and the PPS variance is a plug-in, not a full
design-based (inclusion-probability) estimator. Treat these as a directional probe, not validated
coverage. The random human-only and random PPI rows use the corrected finite-population intervals.

Compared to random human-only@n as the cost baseline. Ground truth mu = full 100-doc human mean.
"""

import json, sys, itertools
import numpy as np

Z = 1.959964
RNG = np.random.default_rng(9)
DIM = "coherence"
MARGIN = 0.20
N = 30
DRAWS = 500
data_dir = sys.argv[1] if len(sys.argv) > 1 else "."

hum = json.load(open(f"{data_dir}/summeval.json"))
jud = json.load(open(f"{data_dir}/gpt4_coh_detailed.json"))
human = {(e["doc_id"], e["system_id"]): e["scores"][DIM] for e in hum}
jmean, jstd = {}, {}
for e in jud:
    r = np.array([float(x) for x in e["all_responses"]])
    jmean[(e["doc_id"], e["system_id"])] = r.mean()
    jstd[(e["doc_id"], e["system_id"])] = r.std()
docs = sorted({d for (d, s) in human}); systems = sorted({s for (d, s) in human})
H = {s: np.array([human[(d, s)] for d in docs]) for s in systems}
Jm = {s: np.array([jmean[(d, s)] for d in docs]) for s in systems}
Js = {s: np.array([jstd[(d, s)] for d in docs]) for s in systems}
nD = len(docs); pairs = list(itertools.permutations(systems, 2))

acc = {k: {"cov": [], "rmse": []} for k in ("human_rand", "ppi_rand", "active_naive", "active_pps")}

for a, b in pairs:
    dh = H[a] - H[b]; dj = Jm[a] - Jm[b]; mu = dh.mean()
    jm_all = dj.mean(); jv_all = dj.var(ddof=1) / nD
    unc = np.sqrt(Js[a] ** 2 + Js[b] ** 2) + 1e-6   # judge uncertainty of this doc's delta
    p_incl = unc / unc.sum() * N                     # PPS target inclusion probs (expected n)
    p_incl = np.clip(p_incl, 0.05, 1.0)              # bound weights (max ~20x) to keep it stable
    top_idx = np.argsort(-unc)[:N]                   # deterministic most-uncertain n
    for _ in range(DRAWS):
        # random baselines
        ridx = RNG.choice(nD, N, replace=False)
        hl, jl = dh[ridx], dj[ridx]
        fpc = 1.0 - N / nD   # finite-population correction (w/o-replacement labels)
        # human-only random
        mh, sh = hl.mean(), np.sqrt(fpc * hl.var(ddof=1) / N)
        # PPI random (no judge-variance term: judge fully observed)
        res = hl - jl; mp, sp = jm_all + res.mean(), np.sqrt(fpc * res.var(ddof=1) / N)
        # naive active (top-n uncertain, unweighted) — EXPLORATORY: deterministic selection, not a
        # valid probability design; CI shown for comparison only, not design-based coverage.
        ai = top_idx; ares = dh[ai] - dj[ai]
        ma, sa = jm_all + ares.mean(), np.sqrt(fpc * ares.var(ddof=1) / N)
        # PPS active (Poisson sampling by p_incl, HT-weighted residual)
        draw = RNG.random(nD) < p_incl
        if draw.sum() < 3:
            continue
        w = 1.0 / p_incl[draw]
        resid = (dh[draw] - dj[draw])
        corr = np.sum(w * resid) / np.sum(w)         # Hajek (weight-normalized) mean of residual
        mpps = jm_all + corr
        var_pps = np.sum((w * (resid - corr)) ** 2) / np.sum(w) ** 2 + jv_all
        spps = np.sqrt(max(var_pps, 1e-12))
        for key, (m, s) in (("human_rand", (mh, sh)), ("ppi_rand", (mp, sp)),
                            ("active_naive", (ma, sa)), ("active_pps", (mpps, spps))):
            lo, hi = m - Z * s, m + Z * s
            acc[key]["cov"].append(lo <= mu <= hi)
            acc[key]["rmse"].append((m - mu) ** 2)

base = np.sqrt(np.mean(acc["human_rand"]["rmse"]))
print("=" * 84)
print(f"ACTIVE SAMPLING (real: SummEval vs GPT-4, {DIM}, n={N}, margin={MARGIN})")
print(f"  selection signal = per-doc judge rating uncertainty; ground truth = full human mean")
print("=" * 84)
print(f"  {'estimator':14s} | coverage |  RMSE  | effective vs random human")
print("  " + "-" * 64)
for key in ("human_rand", "ppi_rand", "active_naive", "active_pps"):
    cov = np.mean(acc[key]["cov"]) * 100
    rmse = np.sqrt(np.mean(acc[key]["rmse"]))
    mult = (base / rmse) ** 2
    print(f"  {key:14s} |  {cov:5.1f}% | {rmse:.3f} |  {mult:.2f}x")
print("  " + "-" * 64)
print("  active_naive: unweighted top-uncertain selection — watch coverage.")
print("  active_pps:   probability-proportional + Horvitz-Thompson — coverage should hold.")
