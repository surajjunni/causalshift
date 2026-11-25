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
