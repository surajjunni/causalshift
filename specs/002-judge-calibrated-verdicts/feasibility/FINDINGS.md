# ReplayGate v2 — Feasibility Simulation Findings

Run: `python3 specs/002-judge-calibrated-verdicts/feasibility/sim.py`
(10,000 Monte Carlo reps/config; n_eval=500; deploy margin = 5% genuinely-worse.)

## Verdict: statistically viable, product usefulness is the real constraint

The reviewer's predicted outcome held: **criteria 1–3 pass, criterion 4 fails** —
"the statistics are viable while the product may not be."

| Go/No-Go target | Result |
|---|---|
| Coverage ≥ 94% (informative judge, n_cal ≥ 100) | 77% of cells (reliable only at n_cal ≥ 300) |
| Corrected RMSE ≤ naive (moderate/weak judge) | 94% of cells pass — correction clearly helps |
| False-approval ≤ 5% (regressing configs) | 100% pass — **~0% false approvals; the gate is genuinely safe** |
| Actionable verdict ≥ 70% @ n_cal 100–300 | **median 22% — fails badly** |

## What the numbers say

1. **The correction works and is honest.** Bias ≈ 0 and coverage ≈ 94–95% once
   Se/Sp ≥ 0.85 and n_cal ≥ 300. RMSE is cut 2–3× vs naive for moderate/weak judges
   (e.g. Mod .85/.85, n_cal=300: 0.047 vs 0.121).

2. **The gate is safe by abstaining, not by being right.** False-approval is ~0%
   everywhere — but it achieves that by returning INCONCLUSIVE most of the time.
   At realistic label budgets (n_cal 100–300) the tool gives a decisive PASS/FAIL
   only ~22% of the time (median). It is only reliably actionable when the regression
   is large (prev=25%) or the judge is excellent. For the *subtle* regressions you
   most want to catch, it abstains.

3. **Label budget is higher than hoped.** n_cal=30 is useless (coverage 53–91%,
   mostly INCONCLUSIVE). Honest coverage needs **n_cal ≥ 300** — which sharpens the
   human-label adoption risk.

4. **Experiment C is the headline risk.** When calibration traffic ≠ evaluation
   traffic (calibrate on easy, deploy on hard), **coverage collapses to ~0–35%**,
   bias jumps to +0.11…+0.22, AND INCONCLUSIVE drops to ~0% — i.e. the tool becomes
   *confidently wrong*. Experiment B (matched mixtures) holds at ~94–95%. So the
   failure is specifically the mismatch: **global Se/Sp calibration is insufficient
   under distribution shift.** The FR-006 shift guard is load-bearing, not optional,
   and a feature-based detector must actually catch this or the gate produces
   confident false verdicts.

## Design implications

- **Stratified (per-category) calibration**, not a single global Se/Sp, is likely
  required to survive realistic heterogeneous judges and shift (directly addresses C).
- **The binary-prevalence estimand (Option A) throws away magnitude** and that is
  partly why intervals are wide and actionable rate is low. The deferred continuous
  quality-delta path (Option B / prediction-powered inference) may be *necessary for
  usefulness*, not a later nicety.
- Honest positioning: v2 as specced is a **conservative "flag large regressions or
  abstain" gate**, not a high-coverage deployment oracle. That is safe and truthful
  but niche.

## Bottom line (sim.py)

Nothing here says "don't build." It says the naive MVP (global calibration, modest
labels, binary estimand) is **safe but not very useful**, and the two levers that
would make it useful — stratified calibration and/or the continuous-delta estimand —
are more work than the MVP scope.

---

# Follow-up experiments (sim2.py)

Run: `python3 specs/002-judge-calibrated-verdicts/feasibility/sim2.py`

## E1 — Stratified vs global vs oracle calibration, under the shift that broke it

Scenario: calibrate on easy-heavy traffic, deploy on hard-heavy traffic, true_prev=10%.

| n_cal | mode | coverage | bias | INCONCLUSIVE | actionable |
|---|---|---|---|---|---|
| 300 | global | 0.4% | +0.180 | 0% | 100% (confidently wrong) |
| 300 | stratified | 84.7% | +0.092 | 89% | 11% |
| 300 | oracle | 94.7% | +0.000 | 88% | 12% |
| 1000 | stratified | 93.6% | +0.002 | 89% | 11% |
| 3000 | stratified | 95.5% | −0.010 | 89% | 11% |

- **Stratification fixes the correctness collapse**: coverage goes from ~0% (global)
  back to ~94–95% (needs n_cal ≈ 1000+ because the hard stratum is label-starved).
- **But it does NOT fix power.** Even the *oracle* (perfect per-category Se/Sp) sits at
  ~88% INCONCLUSIVE / ~12% actionable. So the abstention is **intrinsic to the binary
  prevalence estimand**, not a calibration-estimation artifact. Stratified = honest and
  safe, still not useful.

## E2 — Continuous quality-delta: human-only vs naive-judge vs PPI

Deploy if mean Δ ≥ −5%. PPI = prediction-powered inference (small human set + many judge scores).

| scenario | judge | human act | naive act | PPI act | PPI coverage |
|---|---|---|---|---|---|
| safe −2%, n_h=100 | good (low noise) | 52% | 100% | **99.8%** | 94.9% |
| safe −2%, n_h=100 | biased+noisy | 51% | 98.8% (**cov 0%**) | 48.5% | 94.6% |
| safe −2%, n_h=300 | good | 94% | 100% | 100% | 95.0% |
| regress −10%, n_h=100 | biased+noisy | 91% | 100% (**cov 0%**) | 89% | 94.9% |

- **PPI safely exploits judge information.** When the judge is *informative* (noise ≪
  outcome spread), PPI lifts actionable from ~52% to ~**99.8%** at n_h=100 while holding
  ~95% coverage — i.e. it clears the ≥70% target the binary estimand could not.
- **When the judge is weak**, PPI gracefully degrades to human-only power (~50%) but
  **stays honest (95% coverage)**, whereas the naive judge collapses to **0% coverage**
  (confidently wrong under bias). This is exactly PPI's guarantee.
- **Continuous-delta >> binary** on power: 50–100% actionable vs the binary estimand's
  ~12–22%. The deferred "Option B" is the key to a useful product, not a nicety.

## Decision-framework verdict

| Experiment | Outcome | Signal |
|---|---|---|
| Stratified calibration | Restores coverage under shift; abstention still high (intrinsic to binary) | Necessary for shift-robustness, insufficient alone |
| Continuous-delta (PPI) | Reaches ≥70% actionable with 95% coverage **when judge is informative**; fails safe otherwise | The power lever |

**Conclusion: conditional GO, with a pivot.** The viable v2 is *not* the binary-prevalence
gate. It is **continuous-delta + PPI (label-efficient) + stratified / shift-aware
calibration**, whose power is contingent on (and must report) the judge's informativeness.

## Honesty caveats

- Near-zero false-approval reflects heavy abstention as much as safety; report PASS rate
  and PASS-precision alongside it (done here).
- PPI power is contingent on judge informativeness (noise ÷ outcome spread); not guaranteed.
- Gaussian Δ and additive judge error are idealized; real distributions are messier. This is
  directional evidence, not proof — real-data validation still required.

## Reframed opportunity

Not "judge-calibrated verdicts" (established) but **label-efficient, distribution-shift-aware
regression testing for LLM agents with statistically justified deployment decisions** — a
stronger, still-to-be-validated target. Keep v1 as the stable product; v2 is a research track.

---

# Real-data validation (SC-001) — `real_summeval.py`

Run: `python3 real_summeval.py <data_dir> [n_labels] [dim]`
Data (not committed, ~28 MB): **SummEval human scores + G-Eval GPT-4 judge ratings** on the same
1,600 summaries (100 docs × 16 systems). A "change" = system A vs B; ground truth μ = full 100-doc
human mean delta; this uses **real GPT-4 judge error**, not synthetic Se/Sp.

**Judge informativeness (real): corr(judge Δ, human Δ) = 0.60** (coherence) — a *moderately*
informative judge, i.e. the realistic middle regime, not the "informative judge" best case.

| dim / n_labels | estimator | coverage | actionable | RMSE | false-approval |
|---|---|---|---|---|---|
| coherence, 30 | human-only | 97.4% | 66.2% | 0.173 | 0.1% |
| coherence, 30 | naive GPT-4 | **24.2%** | 82.1% | 0.499 | **8.4%** |
| coherence, 30 | **PPI** | **98.5%** | 67.5% | **0.153** | **0.0%** |
| coherence, 15 | human / naive / PPI | 94.8 / 24.2 / **95.7%** | 54.9 / 82.1 / 58.3% | 0.271 / 0.499 / **0.241** | 0.2 / 8.4 / 0.2% |
| coherence, 50 | human / naive / PPI | 99.2 / 24.2 / **99.7%** | 72.8 / 82.1 / 73.0% | 0.114 / 0.499 / **0.101** | 0.0 / 8.4 / 0.0% |
| relevance, 30 | human / naive / PPI | 97.4 / 52.5 / **98.8%** | 60.2 / 80.0 / 58.1% | 0.137 / 0.239 / **0.127** | 0.1 / 1.1 / 0.0% |

## What the real data says

1. **The safety claim holds, strongly.** The naive uncorrected GPT-4 verdict is *confidently wrong*:
   coverage collapses to 24–52% and false-approval hits 8.4% (over the 5% limit). PPI rescues
   coverage to ~95–99.7%, drives false-approval to ~0%, and gives the **best RMSE in every cell**.
   The "don't ship the judge's biased verdict" value is real and validated on real judge error.

2. **The power claim does NOT materialize on a moderate real judge.** PPI's actionable-verdict rate
   is essentially tied with human-only (e.g. 67.5% vs 66.2%; on relevance slightly *lower*). The
   dramatic synthetic gain (52% → 99.8%) required a *highly* informative judge (noise ≪ spread);
   GPT-4-on-SummEval (ρ≈0.6) is not that. PPI here is a modest accuracy/width improvement, not a
   jump in decisive verdicts.

## Verdict on "validate before building"

- **Validated:** PPI as a **safety + accuracy layer** over an LLM judge — it prevents the naive
  judge's confident-but-wrong deployment approvals and gives the most accurate estimate, honestly.
- **Not validated:** the **central SC-001 / SC-003 claim** — "substantially more actionable decisions
  than human-only at 100–300 labels." On a real, moderately-informative judge it is roughly a tie.
  That claim holds only when the judge is highly aligned with human quality, which must be measured
  per deployment, not assumed.

## Caveats

- One task (news-summary quality), one judge (G-Eval GPT-4), and a noisy/ill-defined target
  (human inter-annotator agreement ≈ 0.48 in the literature) cap the achievable signal.
- SummEval is summary quality, **not agent trajectories** — this validates the statistical core on
  real judge error, not ReplayGate's actual agent-regression setting (that still needs bespoke data).
- Results depend on margin (0.2) and budget; a better-aligned judge would give PPI more power.

## Bottom line (real-data safety vs power)

Real data **tempers** the pivot: build v2 as an **honest safety wrapper over the judge** (its
validated value), not as a "get many more actionable verdicts from few labels" engine (not validated
on a moderate judge).

---

# Label-efficiency experiment — `real_label_efficiency.py`

The decisive commercial question is not actionability but **how many human labels PPI saves**. Swept
budgets 10–80 on the same real data (coverage / actionable / RMSE per budget), and converted PPI's
accuracy gain into an effective-sample multiplier `(RMSE_human / RMSE_ppi)²`.

| budget | human RMSE | PPI RMSE | PPI effective | labels saved |
|---|---|---|---|---|
| 10 | 0.339 | 0.300 | 1.28× | ~2.8 (22%) |
| 20 | 0.227 | 0.202 | 1.27× | ~5.3 (21%) |
| 30 | 0.174 | 0.154 | 1.28× | ~8.3 (22%) |
| 50 | 0.114 | 0.101 | 1.28× | ~13.9 (22%) |
| 80 | 0.057 | 0.050 | 1.28× | ~22.5 (22%) |

- **PPI saves a stable ~22% of human labels** to reach the same accuracy (1.28× effective sample),
  consistent across budgets, with a real, moderately-informative judge (ρ_Δ = 0.60).
- Coverage stays honest (93–100%) and actionable-rate is within ~2–4 points of human-only throughout
  — the label savings show up in **accuracy/variance, not in the coarse actionable metric**.

### On the correlation question (important)

`corr(judge Δ, human Δ) = 0.60` is computed on **deltas over the same baseline/candidate pairs**
(`H[a]−H[b]` vs `J[a]−J[b]`), not on individual summary scores. This is the correct informativeness
measure for a regression verdict, and it is the realistic value for GPT-4-on-SummEval.

## Final go / no-go

- **NO-GO** for shipping PPI as ReplayGate v2's **flagship** capability. On a realistic judge its
  benefits are: a **safety wrapper** (coverage 24%→98%, false-approval 8.4%→0%) and a **modest ~22%
  label saving** — real, but not a flagship product on their own.
- **GO** for: (1) publishing this as an empirical study — *the limits of LLM judges in deployment
  decisions*, where the 24%→98% coverage contrast and the honest synthetic-vs-real power gap are the
  contribution; (2) optionally offering PPI as a thin, clearly-scoped safety/efficiency add-on to v1,
  not a reframing of the product.
- **Keep v1** (causal counterfactual selective replay + trustworthy gating) as ReplayGate's
  distinctive capability. A stronger (higher-ρ) judge would raise PPI's savings, so informativeness
  must be measured per deployment, not assumed.

---

# Active sampling probe — `real_active_sampling.py`

Tests whether selecting the *informative* human labels (vs random) beats PPI's 1.28×, and whether
naive selection breaks coverage. Selection signal: per-doc judge rating uncertainty. n=30.

| estimator | coverage | RMSE | effective vs random human |
|---|---|---|---|
| random human-only | 97.4% | 0.173 | 1.00× |
| random PPI | 98.3% | 0.154 | 1.27× |
| active, top-uncertain (unweighted) | 99.2% | 0.157 | 1.22× |
| active, PPS + Hájek weighted | 97.7% | 0.174 | 1.00× |

- **No improvement over random PPI.** Unweighted active was slightly worse (1.22×); properly-weighted
  active gave no gain (1.00×). Judge rating-uncertainty is a poor proxy for where the human–judge
  residual is large (the quantity that reduces variance), and that residual is unobservable before
  labeling.
- A first naive Horvitz–Thompson estimator blew up (RMSE ~3.0) from tiny inclusion probabilities —
  concretely demonstrating the reviewer's warning that active weighting easily destroys the estimate
  if done carelessly. The stable Hájek version above fixes that but still shows no gain.
- **Conclusion:** active label selection is a genuine research sub-problem (needs a better
  informativeness signal and careful estimator design), not a quick lever. It does not change the
  verdict.

# FINAL VERDICT

- **NO-GO** for a judge-calibration-defined ReplayGate v2 (no elaborate calibration platform, drift
  service, or new deployment policy built just to gain ~22% label efficiency).
- **Conditional GO** for a **small, optional PPI estimator** that enhances v1's evaluation: its real,
  validated value is (a) a safety wrapper preventing the naive judge's confidently-wrong approvals
  (coverage 24%→98%, false-approval 8.4%→0%) and (b) a stable ~22% human-label saving — useful, not
  defining. Note 22% *label* saving ≠ 22% *cost* saving (PPI adds judge inference + integration).
- **GO** for an **empirical write-up**: *the limits of LLM judges in deployment decisions* (the
  24%→98% coverage contrast, the synthetic-vs-real power gap, the honest 1.28× efficiency, and the
  active-sampling null result).
- **Keep v1** — causal counterfactual replay + efficient regression gating — as the product's
  defining, differentiated capability.
