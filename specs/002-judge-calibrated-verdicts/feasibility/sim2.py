"""ReplayGate v2 feasibility — follow-up experiments.

sim.py showed global binary calibration is safe-but-low-power and collapses under
distribution shift (Experiment C). Two targeted questions decide whether to pursue v2:

  E1. Does STRATIFIED (per-category) calibration restore coverage under shift,
      without needing so many labels per category that abstention gets worse?
  E2. Does a CALIBRATED CONTINUOUS-DELTA estimator (prediction-powered inference)
      raise the actionable-verdict rate from ~22% toward 70% without losing coverage?

Metric refinement (per reviewer): report PASS rate and the precision of PASS, not
only the unconditional false-approval rate — a gate that rarely approves looks
"safe" for the wrong reason.
"""

import numpy as np

Z = 1.959964
RNG = np.random.default_rng(11)
REPS = 10_000
CATS = {"easy": (0.95, 0.95), "medium": (0.85, 0.85), "hard": (0.65, 0.65)}


# ======================================================================
# E1. Stratified vs global vs oracle calibration, under cal!=eval shift
# ======================================================================
def binom_rate(n, p, reps):
    n = max(int(n), 0)
    if n == 0:
        return np.full(reps, np.nan)
    return RNG.binomial(n, p, reps) / n


def corrected(q, se_h, sp_h, n_eval_c, n_pos, n_neg):
    """Per-stratum corrected prevalence + delta-method variance (elementwise)."""
    D = se_h + sp_h - 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        p = (q + sp_h - 1.0) / D
        var_q = q * (1 - q) / n_eval_c
        var_se = se_h * (1 - se_h) / n_pos
        var_sp = sp_h * (1 - sp_h) / n_neg
        var_p = (var_q / D**2) + (p / D) ** 2 * var_se + ((se_h - q) / D**2) ** 2 * var_sp
    se_D = np.sqrt(var_se + var_sp)
    bad = (D <= 2 * se_D) | (D < 0.05) | ~np.isfinite(p)
    return p, var_p, bad


def e1(true_prev, n_cal, cal_mix, eval_mix, mode, n_eval=500, reps=REPS, margin=0.05):
    cats = [c for c in CATS if eval_mix.get(c, 0) > 0]
    p_parts = np.zeros(reps)
    var_parts = np.zeros(reps)
    bad = np.zeros(reps, dtype=bool)
    for c in cats:
        se_c, sp_c = CATS[c]
        w_e = eval_mix[c]
        n_e = max(int(round(n_eval * w_e)), 1)
        p_obs = true_prev * se_c + (1 - true_prev) * (1 - sp_c)
        q = RNG.binomial(n_e, p_obs, reps) / n_e
        if mode == "oracle":
            D = se_c + sp_c - 1.0
            p_c = (q + sp_c - 1.0) / D
            var_c = (q * (1 - q) / n_e) / D**2
            bad_c = np.zeros(reps, dtype=bool)
        else:
            w_c = cal_mix[c] if mode == "stratified" else 1.0
            n_c = n_cal * (cal_mix[c] if mode == "stratified" else 1.0)
            n_pos = n_neg = max(int(n_c // 2), 0)
            if mode == "global":
                # pooled Se/Sp estimated from the WHOLE cal set (cal mixture)
                se_pool = sum(cal_mix[k] * CATS[k][0] for k in CATS)
                sp_pool = sum(cal_mix[k] * CATS[k][1] for k in CATS)
                npos = nneg = max(n_cal // 2, 1)
                se_h = RNG.binomial(npos, se_pool, reps) / npos
                sp_h = RNG.binomial(nneg, sp_pool, reps) / nneg
                p_c, var_c, bad_c = corrected(q, se_h, sp_h, n_e, npos, nneg)
            else:  # stratified
                if n_pos < 5 or n_neg < 5:
                    bad |= True  # too few labels in this stratum -> abstain
                    p_c = np.full(reps, np.nan); var_c = np.full(reps, np.nan)
                    bad_c = np.ones(reps, bool)
                else:
                    se_h = RNG.binomial(n_pos, se_c, reps) / n_pos
                    sp_h = RNG.binomial(n_neg, sp_c, reps) / n_neg
                    p_c, var_c, bad_c = corrected(q, se_h, sp_h, n_e, n_pos, n_neg)
        p_parts += np.where(np.isfinite(p_c), w_e * p_c, 0.0)
        var_parts += np.where(np.isfinite(var_c), (w_e**2) * var_c, 0.0)
        bad |= bad_c
        if mode == "global":
            break  # global applies one correction to the whole eval set
    if mode == "global":
        # redo global as single pooled correction over the whole eval set
        se_pool = sum(cal_mix[k] * CATS[k][0] for k in CATS)
        sp_pool = sum(cal_mix[k] * CATS[k][1] for k in CATS)
        se_eval = sum(eval_mix.get(k, 0) * CATS[k][0] for k in CATS)
        sp_eval = sum(eval_mix.get(k, 0) * CATS[k][1] for k in CATS)
        p_obs = true_prev * se_eval + (1 - true_prev) * (1 - sp_eval)
        q = RNG.binomial(n_eval, p_obs, reps) / n_eval
        npos = nneg = max(n_cal // 2, 1)
        se_h = RNG.binomial(npos, se_pool, reps) / npos
        sp_h = RNG.binomial(nneg, sp_pool, reps) / nneg
        p_parts, var_parts, bad = corrected(q, se_h, sp_h, n_eval, npos, nneg)

    se_p = np.sqrt(var_parts)
    lo, hi = p_parts - Z * se_p, p_parts + Z * se_p
    ident = ~bad & np.isfinite(se_p)
    PASS = ident & (hi < margin)
    FAIL = ident & (lo > margin)
    INC = ~(PASS | FAIL)
    k = ident.sum()
    cover = float(np.mean((lo[ident] <= true_prev) & (hi[ident] >= true_prev))) if k else float("nan")
    regress = true_prev > margin
    return dict(
        coverage=cover,
        bias=float(np.nanmean(p_parts[ident] - true_prev)) if k else float("nan"),
        inconclusive=float(np.mean(INC)),
        actionable=float(np.mean(PASS | FAIL)),
        pass_rate=float(np.mean(PASS)),
        false_appr=float(np.mean(PASS)) if regress else float("nan"),
        pass_wrong=float(np.mean(PASS) / max(np.mean(PASS | FAIL), 1e-9)) if regress else float("nan"),
    )


cal_easy = {"easy": 0.70, "medium": 0.20, "hard": 0.10}
eval_hard = {"easy": 0.10, "medium": 0.20, "hard": 0.70}

print("=" * 100)
print("E1 — STRATIFIED vs GLOBAL vs ORACLE under shift (calibrate easy-heavy, deploy hard-heavy)")
print("    true_prev=10% (regressing; margin 5%).  cov=coverage  INC=inconclusive  act=actionable")
print("=" * 100)
for n_cal in (300, 1000, 3000):
    for mode in ("global", "stratified", "oracle"):
        r = e1(0.10, n_cal, cal_easy, eval_hard, mode)
        fa = f"{r['false_appr']*100:4.1f}%" if not np.isnan(r["false_appr"]) else " n/a"
        print(f"  n_cal={n_cal:4d}  {mode:10s} | cov={r['coverage']*100:5.1f}%  bias={r['bias']:+.3f}  "
              f"INC={r['inconclusive']*100:5.1f}%  act={r['actionable']*100:5.1f}%  "
              f"PASS={r['pass_rate']*100:4.1f}%  falseAppr={fa}")
    print("-" * 100)
print("  (hard stratum gets only ~10% of labels under easy-heavy calibration — that is the cost)")


# ======================================================================
# E2. Continuous-delta: human-only vs naive-judge vs PPI
# ======================================================================
def e2(mu, n_h, judge_bias, judge_noise, sigma_delta=0.15, N=2000, reps=REPS, margin=0.05):
    """mu = true mean quality change (negative = worse). Deploy if mu >= -margin.
    judge score f = delta + judge_bias + N(0, judge_noise)."""
    out = {k: [] for k in ("human", "naive", "ppi")}
    cov = {k: 0 for k in out}
    act = {k: 0 for k in out}
    passc = {k: 0 for k in out}
    falsea = {k: 0 for k in out}
    regress = mu < -margin
    for _ in range(reps):
        delta_lab = RNG.normal(mu, sigma_delta, n_h)
        f_lab = delta_lab + judge_bias + RNG.normal(0, judge_noise, n_h)
        f_big = RNG.normal(mu, sigma_delta, N) + judge_bias + RNG.normal(0, judge_noise, N)

        # human-only
        mh, sh = delta_lab.mean(), delta_lab.std(ddof=1) / np.sqrt(n_h)
        # naive judge (all judge scores, uncorrected)
        mn, sn = f_big.mean(), f_big.std(ddof=1) / np.sqrt(N)
        # PPI: debias judge mean using labeled residuals
        resid = delta_lab - f_lab
        mp = f_big.mean() + resid.mean()
        sp = np.sqrt(resid.var(ddof=1) / n_h + f_big.var(ddof=1) / N)

        for key, (m, s) in (("human", (mh, sh)), ("naive", (mn, sn)), ("ppi", (mp, sp))):
            lo, hi = m - Z * s, m + Z * s
            cov[key] += (lo <= mu <= hi)
            P = lo > -margin      # confident not-worse-beyond-margin -> PASS
            F = hi < -margin      # confident worse-beyond-margin -> FAIL
            act[key] += (P or F)
            passc[key] += P
            if regress:
                falsea[key] += P
    def pack(key):
        return dict(coverage=cov[key] / reps, actionable=act[key] / reps,
                    pass_rate=passc[key] / reps,
                    false_appr=(falsea[key] / reps) if regress else float("nan"))
    return {k: pack(k) for k in out}


print("\n" + "=" * 100)
print("E2 — CONTINUOUS-DELTA: human-only vs naive-judge vs PPI   (N=2000 judge-scored, margin 5%)")
print("    judge f = delta + bias + noise;  deploy if mean delta >= -5%")
print("=" * 100)
for mu, tag in ((-0.02, "safe -2%"), (-0.10, "regress -10%"), (-0.20, "regress -20%")):
    for n_h in (100, 300):
        for bias, noise, jtag in ((0.0, 0.05, "good"), (-0.05, 0.15, "biased+noisy")):
            res = e2(mu, n_h, bias, noise)
            for key in ("human", "naive", "ppi"):
                r = res[key]
                fa = f"{r['false_appr']*100:4.1f}%" if not np.isnan(r["false_appr"]) else " n/a"
                print(f"  {tag:12s} n_h={n_h:3d} judge={jtag:12s} {key:5s} | "
                      f"cov={r['coverage']*100:5.1f}%  act={r['actionable']*100:5.1f}%  "
                      f"PASS={r['pass_rate']*100:5.1f}%  falseAppr={fa}")
        print("  " + "-" * 94)
