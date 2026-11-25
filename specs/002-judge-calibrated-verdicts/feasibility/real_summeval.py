"""Real-data validation of the PPI regression-verdict core (SC-001), on real judge error.

Data (not committed; ~28 MB, fetched to a local dir passed as argv[1]):
  SummEval human scores + G-Eval GPT-4 judge ratings on the SAME 1600 summaries
  (100 docs x 16 systems). Download:
    https://raw.githubusercontent.com/nlpyang/geval/main/data/summeval.json
    https://raw.githubusercontent.com/nlpyang/geval/main/results/gpt4_coh_detailed.json
    https://raw.githubusercontent.com/nlpyang/geval/main/results/gpt4_rel_detailed.json

Setup: a "change" = summarization system A vs system B. Over the 100 shared docs,
  Delta_human_d = human(A,d) - human(B,d)   (ground truth)
  Delta_judge_d = judge(A,d) - judge(B,d)   (GPT-4 prediction, REAL error)
True effect mu = full-sample human mean Delta (all 100 docs).

Question (SC-001): from a small human-labeled subset + the judge on all docs, does PPI
recover mu with honest coverage and more actionable verdicts than human-only, on a REAL judge?
"""

import json, sys, itertools
import numpy as np

Z = 1.959964
RNG = np.random.default_rng(3)
MARGIN = 0.20          # deploy if mean human delta >= -MARGIN (points, 1-5 scale)
DRAWS = 300            # random label subsets per change
data_dir = sys.argv[1] if len(sys.argv) > 1 else "."
N_LABELS = int(sys.argv[2]) if len(sys.argv) > 2 else 30
DIM = sys.argv[3] if len(sys.argv) > 3 else "coherence"


def judge_score(entry):
    return float(np.mean([float(x) for x in entry["all_responses"]]))


hum_raw = json.load(open(f"{data_dir}/summeval.json"))
jf = {"coherence": "gpt4_coh_detailed.json", "relevance": "gpt4_rel_detailed.json"}[DIM]
jud_raw = json.load(open(f"{data_dir}/{jf}"))

human = {(e["doc_id"], e["system_id"]): e["scores"][DIM] for e in hum_raw}
judge = {(e["doc_id"], e["system_id"]): judge_score(e) for e in jud_raw}
docs = sorted({d for (d, s) in human})
systems = sorted({s for (d, s) in human})

# doc-aligned score vectors per system
H = {s: np.array([human[(d, s)] for d in docs]) for s in systems}
J = {s: np.array([judge[(d, s)] for d in docs]) for s in systems}
nD = len(docs)

# judge informativeness: correlation between judge delta and human delta, pooled over pairs
dh_all, dj_all = [], []
for a, b in itertools.permutations(systems, 2):
    dh_all.append(H[a] - H[b]); dj_all.append(J[a] - J[b])
dh_all = np.concatenate(dh_all); dj_all = np.concatenate(dj_all)
rho = np.corrcoef(dh_all, dj_all)[0, 1]

agg = {k: {"cov": [], "act": [], "rmse": [], "fa": [], "width": []}
       for k in ("human", "naive", "ppi")}

for a, b in itertools.permutations(systems, 2):
    dh = H[a] - H[b]           # true per-doc human delta
    dj = J[a] - J[b]           # judge per-doc delta
    mu = dh.mean()             # ground-truth effect (all docs)
    regress = mu < -MARGIN
    judge_mean = dj.mean()
    judge_var = dj.var(ddof=1) / nD
    for _ in range(DRAWS):
        idx = RNG.choice(nD, N_LABELS, replace=False)
        hl, jl = dh[idx], dj[idx]
        fpc = 1.0 - N_LABELS / nD   # finite-population correction: labels drawn w/o replacement from the N docs
        # human-only (without-replacement sample mean of the finite population)
        mh, sh = hl.mean(), np.sqrt(fpc * hl.var(ddof=1) / N_LABELS)
        # naive judge: judge mean over all docs, uncorrected. Judge is fully observed, so its only
        # "uncertainty" is the mis-specified super-population judge-sample CI; it ignores judge bias.
        mn, sn = judge_mean, np.sqrt(judge_var)
        # PPI: judge pop-mean (a known constant here) + sampled residual correction.
        # Var(mu_ppi) = (1 - n/N) * s_resid^2 / n  -- NO judge_var term (judge fully observed).
        resid = hl - jl
        mp = judge_mean + resid.mean()
        sp = np.sqrt(fpc * resid.var(ddof=1) / N_LABELS)
        for key, (m, s) in (("human", (mh, sh)), ("naive", (mn, sn)), ("ppi", (mp, sp))):
            lo, hi = m - Z * s, m + Z * s
            agg[key]["cov"].append(lo <= mu <= hi)
            P = lo > -MARGIN
            F = hi < -MARGIN
            agg[key]["act"].append(P or F)
            agg[key]["width"].append(hi - lo)
            agg[key]["rmse"].append((m - mu) ** 2)
            if regress:
                agg[key]["fa"].append(P)

print("=" * 92)
print(f"REAL-DATA VALIDATION — SummEval human vs G-Eval GPT-4 judge   dim={DIM}")
print(f"  {len(systems)} systems, {nD} docs, {len(list(itertools.permutations(systems,2)))} ordered "
      f"changes; n_labels={N_LABELS}, {DRAWS} draws/change, margin={MARGIN}")
print(f"  judge informativeness: corr(judge Δ, human Δ) = {rho:.3f}  (real GPT-4 coherence vs human)")
print("=" * 92)
print(f"  {'estimator':8s} | coverage | actionable |  RMSE  | CI width | false-approval")
print("  " + "-" * 78)
for key in ("human", "naive", "ppi"):
    a = agg[key]
    cov = np.mean(a["cov"]) * 100
    act = np.mean(a["act"]) * 100
    rmse = np.sqrt(np.mean(a["rmse"]))
    width = np.mean(a["width"])
    fa = (np.mean(a["fa"]) * 100) if a["fa"] else float("nan")
    print(f"  {key:8s} |  {cov:5.1f}% |   {act:5.1f}%  | {rmse:.3f} |  {width:.3f}  |   {fa:5.1f}%")
print("  " + "-" * 78)
print("  human = label the subset only; naive = GPT-4 mean uncorrected; ppi = judge + human residual")
print("  (ground truth mu = full 100-doc human mean delta; coverage = CI contains mu)")
