"""ReplayGate v2 feasibility simulation.

Question: does misclassification-corrected judge calibration produce a
statistically trustworthy deployment gate, and in which regimes?

No human labels, no product. Pure Monte Carlo over synthetic judges with known
sensitivity (Se) / specificity (Sp) and known true regression prevalence.

Estimand: corrected_regression_prevalence p = P(candidate genuinely worse).
Correction:  p_hat = (q_hat + Sp_hat - 1) / (Se_hat + Sp_hat - 1)
  q_hat  = observed fraction the judge calls "worse" on the eval set
  Se_hat = estimated from the truly-worse calibration items
  Sp_hat = estimated from the truly-not-worse calibration items
CI: delta method jointly over (q, Se, Sp)  -> calibration-aware.
Identifiability guard: if D_hat = Se_hat+Sp_hat-1 is not provably > 0, abstain.
Gate (margin m): PASS if CI above is entirely < m (safe); FAIL if entirely > m;
else INCONCLUSIVE.  Fail-closed.

Assumptions: balanced calibration (n/2 truly-worse, n/2 truly-not-worse);
n_eval fixed; judge decisions independent given category.
"""

import numpy as np

Z = 1.959964            # 95%
N_EVAL = 500            # evaluated trajectories per run
MARGIN = 0.05           # tolerate <=5% genuinely-worse to approve deploy
REPS = 10_000
RNG = np.random.default_rng(7)

CATS = {"easy": (0.95, 0.95), "medium": (0.85, 0.85), "hard": (0.65, 0.65)}


def pool(mix):
    """Mixture-weighted pooled (Se, Sp)."""
    se = sum(w * CATS[c][0] for c, w in mix.items())
    sp = sum(w * CATS[c][1] for c, w in mix.items())
    return se, sp


def run(se_eval, sp_eval, se_cal, sp_cal, true_prev, n_cal,
        n_eval=N_EVAL, reps=REPS, margin=MARGIN):
    """One configuration. se/sp_eval drive the eval judge; se/sp_cal drive what
    calibration measures (equal to eval in A/B, different in C)."""
    n_pos = n_neg = n_cal // 2

    # observed "worse" rate on eval, given the EVAL judge
    p_obs = true_prev * se_eval + (1 - true_prev) * (1 - sp_eval)
    q = RNG.binomial(n_eval, p_obs, reps) / n_eval
    # calibration estimates reflect the CALIBRATION judge/traffic
    se_h = RNG.binomial(n_pos, se_cal, reps) / n_pos
    sp_h = RNG.binomial(n_neg, sp_cal, reps) / n_neg

    D = se_h + sp_h - 1.0
    safe = D > 1e-9
    p = np.where(safe, (q + sp_h - 1.0) / np.where(safe, D, 1.0), np.nan)

    var_q = q * (1 - q) / n_eval
    var_se = se_h * (1 - se_h) / n_pos
    var_sp = sp_h * (1 - sp_h) / n_neg
    with np.errstate(divide="ignore", invalid="ignore"):
        dq = 1.0 / D
        dse = -p / D
        dsp = (se_h - q) / (D * D)
        var_p = dq**2 * var_q + dse**2 * var_se + dsp**2 * var_sp
        se_p = np.sqrt(var_p)
    lo, hi = p - Z * se_p, p + Z * se_p

    se_D = np.sqrt(var_se + var_sp)
    non_ident = (~safe) | (D <= 2 * se_D) | (D < 0.05) | ~np.isfinite(se_p)

    PASS = (~non_ident) & (hi < margin)
    FAIL = (~non_ident) & (lo > margin)
    INC = ~(PASS | FAIL)

    ident = ~non_ident
    k = ident.sum()
    def m(a):  # mean over identifiable
        return float(np.mean(a[ident])) if k else float("nan")

    naive_rmse = float(np.sqrt(np.mean((q - true_prev) ** 2)))
    corr_rmse = float(np.sqrt(np.mean((p[ident] - true_prev) ** 2))) if k else float("nan")
    cover = float(np.mean((lo[ident] <= true_prev) & (hi[ident] >= true_prev))) if k else float("nan")
    width = float(np.mean((hi - lo)[ident])) if k else float("nan")
    regressing = true_prev > margin
    false_appr = float(np.mean(PASS)) if regressing else float("nan")

    return dict(bias=m(p - true_prev), corr_rmse=corr_rmse, naive_rmse=naive_rmse,
                coverage=cover, width=width, inconclusive=float(np.mean(INC)),
                actionable=float(np.mean(PASS | FAIL)), false_approval=false_appr,
                ident_rate=float(np.mean(ident)))


def fmt(r):
    fa = "  n/a " if np.isnan(r["false_approval"]) else f"{r['false_approval']*100:5.1f}%"
    return (f"cov={r['coverage']*100:5.1f}%  bias={r['bias']:+.3f}  "
            f"rmse c/n={r['corr_rmse']:.3f}/{r['naive_rmse']:.3f}  "
            f"width={r['width']:.3f}  INC={r['inconclusive']*100:5.1f}%  "
            f"act={r['actionable']*100:5.1f}%  falseAppr={fa}")


# ---------- Experiment A: stationary judge, matches correction's assumptions ----------
print("=" * 108)
print(f"EXPERIMENT A - stationary judge (cal mixture == eval mixture)   "
      f"[n_eval={N_EVAL}, margin={MARGIN}, reps={REPS}]")
print("=" * 108)
RELIAB = {"High .95/.95": (0.95, 0.95), "Mod  .85/.85": (0.85, 0.85),
          "Weak .65/.65": (0.65, 0.65), "Chance .50/.50": (0.50, 0.50)}
for rname, (se, sp) in RELIAB.items():
    for n_cal in (30, 100, 300, 1000):
        line = []
        for prev in (0.02, 0.10, 0.25):
            r = run(se, sp, se, sp, prev, n_cal)
            line.append((prev, r))
        for prev, r in line:
            print(f"  {rname:15s} n_cal={n_cal:4d}  prev={prev:4.0%}  | {fmt(r)}")
    print("-" * 108)

# ---------- Experiments B & C: heterogeneous judge error ----------
uniform = {"easy": 1/3, "medium": 1/3, "hard": 1/3}
cal_easy = {"easy": 0.70, "medium": 0.20, "hard": 0.10}   # calibration from easy traffic
eval_hard = {"easy": 0.10, "medium": 0.20, "hard": 0.70}  # deploy on hard traffic

print("\n" + "=" * 108)
print("EXPERIMENTS B & C - judge error varies by task category (easy/med/hard = .95/.85/.65)")
print("=" * 108)
se_u, sp_u = pool(uniform)
se_ce, sp_ce = pool(cal_easy)
se_eh, sp_eh = pool(eval_hard)
print(f"  pooled Se/Sp: uniform={se_u:.3f}/{sp_u:.3f}  cal_easy={se_ce:.3f}/{sp_ce:.3f}  "
      f"eval_hard={se_eh:.3f}/{sp_eh:.3f}")
for prev in (0.02, 0.10, 0.25):
    for n_cal in (100, 300, 1000):
        # B: cal mixture == eval mixture (uniform) -> correction assumptions hold on average
        rB = run(se_u, sp_u, se_u, sp_u, prev, n_cal)
        # C: calibrate on easy, deploy on hard -> pooled Se/Sp mismatch
        rC = run(se_eh, sp_eh, se_ce, sp_ce, prev, n_cal)
        print(f"  B uniform      n_cal={n_cal:4d} prev={prev:4.0%} | {fmt(rB)}")
        print(f"  C cal!=eval    n_cal={n_cal:4d} prev={prev:4.0%} | {fmt(rC)}")
    print("-" * 108)

# ---------- Go / no-go summary ----------
print("\n" + "=" * 108)
print("GO / NO-GO  (targets: coverage>=94% in intended regime; corrected RMSE<naive where "
      "recommended;\n            false-approval<=5%; actionable>=70% at n_cal 100-300)")
print("=" * 108)

# Intended operating regime for coverage/false-approval: informative judge (Se/Sp>=0.65),
# stationary (Exp A), n_cal>=100.
cov_ok, fa_ok, rmse_ok, act_vals = [], [], [], []
for rname, (se, sp) in RELIAB.items():
    if se < 0.65:
        continue
    for n_cal in (100, 300, 1000):
        for prev in (0.02, 0.10, 0.25):
            r = run(se, sp, se, sp, prev, n_cal)
            cov_ok.append(r["coverage"] >= 0.94)
            if not np.isnan(r["false_approval"]):
                fa_ok.append(r["false_approval"] <= 0.05)
            # RMSE improvement expected mainly for moderate/weak judges
            if se <= 0.85:
                rmse_ok.append(r["corr_rmse"] <= r["naive_rmse"] + 1e-9)
            if n_cal in (100, 300):
                act_vals.append(r["actionable"])

print(f"  1. coverage>=94% (A, Se/Sp>=.65, n_cal>=100): "
      f"{int(np.mean(cov_ok)*100)}% of cells pass")
print(f"  2. corrected RMSE<=naive (moderate/weak judge): "
      f"{int(np.mean(rmse_ok)*100)}% of cells pass")
print(f"  3. false-approval<=5% (regressing configs):    "
      f"{int(np.mean(fa_ok)*100)}% of cells pass")
print(f"  4. actionable verdict rate @ n_cal 100-300:    "
      f"median {np.median(act_vals)*100:.0f}%  (target >=70%)")
print("\n  Experiment C is the stress test: if its coverage collapses while B holds,\n"
      "  global Se/Sp calibration is insufficient under distribution shift (expected).")
