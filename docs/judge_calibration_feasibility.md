# ReplayGate Judge Calibration: Feasibility and Failure Modes

*How I tried to build a trustworthy deployment gate on top of an untrustworthy LLM judge, what broke,
and what actually worked. All numbers below are from synthetic Monte-Carlo simulation, not real
traffic yet.*

## The problem

ReplayGate replays recorded agent trajectories under a prompt or model change and tells you whether
quality regressed. To decide "regressed," it runs a quality evaluator, which in practice is an
LLM-as-judge. The whole verdict rests on that judge being right.

But the 2026 literature is clear that LLM judges are biased, noisy, and unreliable under distribution
shift. They can be internally consistent and still systematically wrong. So a natural next step for
ReplayGate was obvious: stop trusting the judge blindly, measure how wrong it is, and fold that into
the verdict.

The naive design was textbook: calibrate the judge's binary "worse / not worse" decision against a
small set of human labels, estimate its sensitivity and specificity, apply the standard
misclassification correction, and report a confidence interval. Before writing any product code, I
simulated it. That turned out to be the most useful thing I did.

## What the simulation measured

For each configuration (judge reliability, human-label budget, true regression rate), I ran 10,000
Monte-Carlo replications with independent calibration and evaluation samples, and measured six things:
estimation bias and RMSE, 95% interval coverage, interval width, the rate of INCONCLUSIVE verdicts,
and the false deployment-approval rate. A deployment gate is only useful if it is both *honest*
(coverage holds) and *actionable* (it does not abstain on everything).

## Failure mode 1: binary calibration is safe but low-power

The binary approach passed the statistical tests. Bias was near zero. With enough labels (around 300)
and a decent judge, interval coverage sat at a healthy 94 to 95 percent. The correction cut RMSE two
to three times versus the uncorrected judge. And the gate essentially never approved a regressing
deploy by mistake: false-approval was near zero across the board.

The catch is *how* it stayed safe. It abstained. At a realistic budget of 100 to 300 human labels, the
gate returned a decisive PASS or FAIL only about 22 percent of the time (median). The rest of the
time it said INCONCLUSIVE. It was only confident when the regression was large or the judge was
excellent. For the subtle regressions you most want to catch, it shrugged.

A tool that says "I cannot tell" four times out of five is safe in the way that a smoke detector with
the battery removed never gives a false alarm. The near-zero false-approval rate reflected heavy
abstention, not a useful gate. That distinction (reporting the PASS rate, not only the false-approval
rate) matters, and it is easy to miss.

## Failure mode 2: global calibration collapses under distribution shift

The second failure is worse, because it is silent. Real judges do not have one fixed error rate. They
are better on easy, short answers and worse on long, tool-heavy, ambiguous ones. So I modeled a judge
whose sensitivity and specificity vary by task category, and then calibrated on one traffic mixture
while evaluating on another (calibrate on easy-heavy traffic, deploy on hard-heavy traffic).

Coverage collapsed from ~95 percent to near zero. Bias jumped by 0.18 to 0.22. And crucially, the
abstention rate dropped to almost zero: the tool stopped saying "I cannot tell" and started
confidently returning wrong answers. A single global sensitivity/specificity profile does not survive
a change in the traffic mix, and nothing in the estimator notices.

Stratified calibration (estimate error separately per task category) *did* restore coverage, back to
94 to 95 percent, once there were enough labels per stratum. But it did not restore power. Even an
*oracle* using the true per-category error rates still abstained about 88 percent of the time. That
confirmed the abstention was intrinsic to the binary-prevalence estimand, not an artifact of
estimation error. Stratification makes the binary gate honest. It does not make it useful.

## What worked: continuous deltas and prediction-powered inference

The binary decision throws away information: it collapses "how much worse" into a yes/no. So I tested
the continuous alternative. Keep the judge's continuous quality-delta score, and correct it with
prediction-powered inference (PPI): take the judge's mean over the whole evaluation set, then debias it
using the human-minus-judge residuals on a small labeled subset.

This is the result that changed the project's direction. With an informative judge (one whose noise is
small relative to the spread in true quality), PPI lifted the actionable-verdict rate from about 52
percent to 99.8 percent at just 100 human labels, while holding coverage at 95 percent. That clears the
70 percent actionable bar the binary estimand never could.

And when the judge was weak, PPI did the honest thing. It degraded gracefully to human-only power
(around 50 percent actionable) while keeping coverage at 95 percent. The naive uncorrected judge, by
contrast, collapsed to zero percent coverage under the same bias. That is exactly PPI's guarantee: it
safely exploits whatever signal the judge carries, and no more.

## The honest limits

None of this is a guarantee yet, for three reasons worth stating plainly.

First, these are synthetic, Gaussian-idealized judges. Real quality distributions and real judge errors
are messier. This is directional evidence, not proof. The next step is reproducing the result on real
agent traces, not building a bigger feature.

Second, PPI's power is contingent on judge informativeness. If the judge carries little information, you
get human-only power, no matter how clever the estimator. That contingency has to be measured and
reported with every verdict, not assumed.

Third, and most important: correcting judge error is not the same as correcting replay error. PPI
debiases the evaluator relative to the human sample. It does nothing about the separate uncertainty
introduced when selective replay produces a different execution than the true counterfactual, nor about
the uncertainty from how the human sample was drawn. Those are three different problems. Until they are
jointly validated, no single end-to-end 95 percent number is defensible, and advertising one would
repeat exactly the overconfidence this whole exercise was meant to remove.

## What this became

The project pivoted. The target is no longer "calibrated judge verdicts," which is established work
anyway. It is label-efficient, distribution-shift-aware regression testing for LLM agents, with
statistically justified and deliberately conservative deployment decisions. The individual techniques
are known; the contribution is applying them correctly to the agent-replay deployment question, and,
longer term, modeling evaluator and replay uncertainty together.

The broader lesson is cheaper than the feature would have been. A day of simulation, before any API
design, turned "I think this is a good idea" into a map of where it works, where it quietly fails, and
what to measure before trusting it. The negative results (binary calibration abstains; global
calibration lies under shift; low false-approval can be an artifact of abstention) were more valuable
than the positive one.

---

*Reproduce it: `sim.py` and `sim2.py` in the ReplayGate repo under
`specs/002-judge-calibrated-verdicts/feasibility/`. Numbers are synthetic and will move with the
assumptions; the point is the shape of the failure modes, not the third decimal.*
