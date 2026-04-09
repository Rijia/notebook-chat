Analyze an A/B experiment with full statistical rigor. $ARGUMENTS should describe the experiment (treatment/control column name, metric columns, and context). Use whatever dataframe is already loaded.

## Requirements

### 1. Randomization Check
- Compare pre-experiment covariates between treatment and control (t-test or chi-square)
- Check for sample ratio mismatch (SRM): expected vs actual split ratio
- Plot assignment over time to catch ramping or novelty effects

### 2. Descriptive Statistics
- N, mean, median, std, and 95% CI for each metric by group
- Distribution plots (KDE) overlaid for treatment vs control for each metric

### 3. Observation Window Audit (do this before any metric analysis)
For every metric, explicitly ask: is the observation window the same length for all users?

- **Assignment-date censoring**: users assigned later in the experiment have less time to convert/churn. Check the distribution of days-since-assignment. If it is not uniform, naive rates are biased.
- **Event-date censoring**: users who converted later have less time to exhibit downstream behavior (e.g., cancel). A user who signed up on day 29 of a 30-day experiment has had almost no time to cancel — including them in a "no cancel" count inflates retention.
- **Decision rule**: if any metric requires follow-up time beyond what is uniformly observed for all users, do NOT analyze it as a simple rate. Instead:
  - Option A: restrict to users with a full fixed follow-up window (e.g., only users assigned in week 1, analyzed through week 5)
  - Option B: use a Kaplan-Meier survival curve with log-rank test
  - If neither is feasible given the data, explicitly label the metric as **"not yet measurable — observation window too short / censored"** and exclude it from the ship decision
- Never conclude "no harm on retention" from a censored window. The correct statement is "retention is not estimable from this data."

### 4. Primary Metric Analysis
For each metric that passed the observation window audit:
- Choose the right test: two-proportion z-test for rates, t-test/Mann-Whitney for continuous
- Report: absolute lift, relative lift (%), p-value, 95% CI on the lift
- Compute observed statistical power given the realized sample size
- Flag if underpowered (power < 0.8)

### 5. Multiple Testing Correction
- If testing >1 metric, apply Benjamini-Hochberg correction
- Clearly label which results survive correction and which don't

### 6. Incremental ROI (monetization experiments)
For any experiment that changes pricing, introduces a free trial, or otherwise affects revenue, the ROI must be computed on **incremental gross profit**, not just lift on a conversion rate. Checklist:

- **Define the incremental unit**: what is the causal effect of treatment on one user's gross profit over a defined time horizon (e.g., 12 months)?
- **Cannibalization**: users in treatment who would have paid full price in control but now receive a discount or free period are a direct cost. Estimate: `cannibalization cost = P(would have converted in control) × (discount or free-month cost)`.
- **Incremental gross profit per treated user** = (incremental conversion lift × LTV per new subscriber) − (cannibalization cost per treated user) − (marginal cost of the feature)
- **Scale**: multiply by the number of users in scope per year
- **Sensitivity table**: vary LTV, cannibalization rate, and churn assumptions by ±20% and show how the breakeven changes. Label the base case and each scenario.
- Do not mix lift percentages with absolute dollar figures without showing the unit conversion explicitly at each step.

### 7. Subgroup Analysis — Caution Protocol
Subgroup / segmentation analysis is exploratory by default. Follow this protocol strictly:

- **Pre-specified subgroups only get confirmatory status**. Any subgroup not named before the experiment is exploratory.
- For each subgroup, test the **interaction term** (treatment × subgroup indicator), not just the within-subgroup effect. A subgroup-level p-value < 0.05 without a significant interaction is noise.
- Apply multiple testing correction across all subgroups tested.
- Report subgroup results as a forest plot with 95% CIs. Flag whether each interaction is statistically significant.
- **Do not convert point estimates from non-significant interactions into targeting recommendations.** If MST/PST or iOS shows a higher point estimate but the interaction is not significant, state: "directionally positive but not significant; not sufficient basis for targeting."
- Any targeting strategy derived from subgroup analysis must be validated in a follow-up experiment designed for that hypothesis.

### 8. Uplift Modeling — Requirements if Used
If an uplift / causal ML model is included:
- Must use a proper causal uplift framework (e.g., Two-Model / T-Learner, X-Learner, or causal forests) — not a propensity model or a response model trained only on treatment users
- Must be trained on one held-out partition of the experiment and evaluated on a separate held-out partition; never train and evaluate on the same data
- Evaluate with a Qini curve or uplift curve, not standard classification metrics
- Acknowledge that any uplift model trained on a single experiment is likely overfit and requires a prospective validation experiment before acting on it

### 9. Ship Decision Framework
Produce a final recommendation table:
| Criterion | Status | Notes |
|-----------|--------|-------|
| Statistical significance (p < 0.05, BH-corrected) | ✅/❌ | |
| Practical significance (≥ threshold) | ✅/❌ | |
| Observation window sufficient for all claimed metrics | ✅/❌/⚠️ censored | |
| Incremental gross profit positive (if monetization) | ✅/❌/⚠️ uncertain | |
| No significant harm to guardrail metrics | ✅/❌ | |
| Adequate power | ✅/❌ | |
| No SRM detected | ✅/❌ | |
| Subgroup targeting supported by significant interactions | ✅/❌/N/A | |
| **Overall recommendation** | Ship / Hold / Run longer / Redesign | |

If any row is ⚠️ or ❌ on a critical criterion, the recommendation must be "Hold" or "Redesign" — never "Ship" with a footnote.

## Code Standards
- Write helper functions for each test type; do not repeat test logic
- All plots: titles, axis labels, annotate the lift on charts
- Print p-values and CIs with 4 decimal places

## Statistical Rigor — Gelman Framework

### Before Running: Retrodesign
Don't just calculate power. Run a **retrodesign analysis** using a *conservative*, realistic effect size (from prior experiments, not optimistic pilots):
- **Type S error**: probability a significant result has the wrong sign. At low power (< 20%), this can exceed 10%.
- **Type M error (exaggeration ratio)**: how much will a significant result overstate the true effect? At power 0.50, exaggeration ratios of 1.5–2× are common. At power 0.20, 4–8× is plausible.
- Rule of thumb: target power ≥ 0.80 for Type M to stay below ~1.1×. If you can't reach this, adjust scope or lower expectations for the first result.

### Pre-registration
Commit in writing to the primary metric, analysis specification, stopping rule, and any pre-specified subgroups **before looking at data**. Every analysis decision made after seeing data patterns (which window to use, which segment to highlight, which covariate to add) inflates Type I error — even when only one test is run. This is the **garden of forking paths**: data-contingent choices invalidate nominal error rates without any conscious fishing. Label all post-hoc choices as exploratory; never present them as confirmatory.

### Reporting: Estimates + Intervals, Not Significance
Replace "statistically significant (p=0.03)" with "lift of X units [95% CI: A, B]". Report effect size and uncertainty for every metric, regardless of significance status. Dichotomania — collapsing continuous uncertainty into a yes/no threshold — wastes information and distorts decisions.

### Winner's Curse
One significant A/B result is systematically an overestimate of the true effect due to the significance filter. Treat it as one data point in an ongoing series. If prior experiments exist in the same product area, use their results as an informative prior and shrink the current estimate toward the historical mean.

### Effect Heterogeneity and Causal Quartets
The average treatment effect (ATE) hides the distribution of individual effects. Two experiments can have identical ATEs while one has constant effects and the other has half the population harmed and half helped. Always:
- Report treatment effects across key subgroups using a **hierarchical model with partial pooling** — shrinking sparse segments toward the grand mean is the correct multiple-comparisons correction, not Bonferroni
- Test for significant treatment × subgroup interactions before interpreting subgroup differences
- Plot the distribution of effects, not just the mean
