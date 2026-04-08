Review the data science notebook or script at $ARGUMENTS (or the most recently modified .ipynb/.py file if no argument given) as a staff data scientist would in a code review. Be specific, cite line numbers or cell numbers, and prioritize issues by severity.

## Review Dimensions

### 1. Statistical Rigor (Critical)
Check for:
- [ ] Using the right test for the data type and distribution
- [ ] Multiple testing without correction (running >2 tests on same data)
- [ ] Underpowered analyses (sample too small, never verified)
- [ ] Data leakage (fitting on test data, using future information)
- [ ] Survivorship bias (analyzing only entities that "survived")
- [ ] Ignoring class imbalance in classification
- [ ] Claiming causation from observational data without acknowledging it
- [ ] P-hacking patterns (trying many cuts until something is significant)
- [ ] **Type M error (winner's curse)**: if the study is underpowered, any "significant" result is likely an inflated overestimate of the true effect. Flag this explicitly and note that the magnitude should be treated skeptically.
- [ ] **Reporting only significance, not effect size + CI**: every numerical claim should include an estimate, its uncertainty interval, and the unit. "Statistically significant" alone is not a result.
- [ ] **Garden of forking paths**: were analysis decisions (window length, variable coding, subgroup choice) made after seeing data patterns? If so, label those findings as exploratory — the nominal p-value is not valid.
- [ ] **Estimand not stated**: is it clear what quantity is being estimated and for whom? (ATE for the full population? CATE for a segment? In-sample fit only?) Unstated estimands lead to over-generalized conclusions.
- [ ] **Effect heterogeneity ignored**: does the analysis report only an average effect without examining the distribution across subgroups? Identical averages can hide harm/benefit splits. Flag if no interaction terms or segment-level breakdowns are present.
- [ ] **R² used as primary metric**: flag its use for model selection. Prefer out-of-sample held-out metrics or LOO-CV. R² conflates noisiness of the outcome with model quality.
- [ ] **Model residuals not checked**: for any regression or ML model, verify that residuals vs. predicted and residuals vs. key covariates have been plotted. Unexamined residuals miss systematic model failures.

### 2. Censored Observation Windows (Critical — especially in experiments)
This is one of the most common senior-level failures. Check:
- [ ] **Assignment-date censoring**: does every user have the same length of observation time? If users were assigned at different calendar dates, those assigned later have less time to convert/churn. A naive aggregate rate is biased downward for late-assigned users.
- [ ] **Event-date censoring**: does a downstream metric require follow-up time after a prior event (e.g., cancel rate measured after signup)? Users who completed the prior event late in the experiment window have had almost no time to exhibit the downstream behavior. Including them in a "did not cancel" count inflates apparent retention.
- [ ] **Incorrect conclusion**: if the analysis concludes "no harm on retention" or "retention is unchanged" from an experiment shorter than the typical cancel window, flag this as a **critical error**. The correct conclusion is "retention is not measurable from this data — the observation window is censored." Recommend either a fixed follow-up window restricted to early-assigned users, or a Kaplan-Meier survival analysis.

### 3. ROI and Monetization Math (Critical for revenue-touching experiments)
- [ ] **Incrementality**: is the ROI computed on incremental gross profit, or is it mixing a lift percentage with an absolute revenue figure without tracing the units?
- [ ] **Cannibalization**: for free trial or discount experiments, does the analysis account for users who would have paid in control but now receive the benefit for free in treatment? Ignoring this overstates the incremental value.
- [ ] **Unit consistency**: verify that every multiplication step in the ROI formula has consistent units (per-user × users = total; lift × base rate × LTV = incremental revenue per user). Flag any step that silently switches between rates and absolutes.
- [ ] **Sensitivity analysis**: are the key assumptions (LTV, churn rate, cannibalization rate) varied? A single-point ROI estimate with no range is not trustworthy for a ship decision.

### 4. Subgroup Analysis and Targeting (High)
- [ ] **Interaction test missing**: if the analysis recommends targeting a subgroup (e.g., iOS users, weekend users, a specific timezone), check whether a treatment × subgroup interaction term was tested. A within-subgroup p-value without a significant interaction is not evidence of heterogeneity — it is noise.
- [ ] **Multiple comparisons not corrected**: if multiple subgroups were tested, was BH or Bonferroni correction applied across subgroups?
- [ ] **Targeting from noise**: flag any targeting recommendation derived from a non-significant interaction as unsupported. The correct statement is "directionally positive but interaction is not significant; insufficient basis for differential targeting."
- [ ] **Uplift model without proper validation**: if an uplift/causal ML model is used to derive targeting, check that (a) it uses a causal uplift framework (not a standard classifier), (b) it is trained and evaluated on separate data partitions, and (c) it is evaluated with an uplift curve (Qini), not classification metrics. A model trained and evaluated on the same experiment data with no prospective validation should be treated as illustrative only.

### 5. Code Quality (High)
Check for:
- [ ] Repeated code blocks that should be functions
- [ ] Magic numbers without explanation
- [ ] SettingWithCopyWarning patterns in pandas
- [ ] Unfinished comments (e.g., `# TODO`, `# do X here`)
- [ ] Unused variables or dead code
- [ ] Hard-coded file paths or credentials

### 6. Visualization Quality (Medium)
Check for:
- [ ] Missing axis labels or titles
- [ ] Y-axis not starting at 0 for bar charts (misleading)
- [ ] Color choices that are not colorblind-friendly
- [ ] Overcrowded subplots that are hard to read
- [ ] No annotation of key values on plots

### 7. Insight and Conclusion Quality (High)
Check for:
- [ ] Stating statistical significance without practical significance
- [ ] Conclusions stronger than the evidence supports (e.g., "no harm" when metric is unmeasurable)
- [ ] Obvious findings presented as insights
- [ ] Recommendations that don't connect to specific business actions
- [ ] Not quantifying uncertainty in conclusions

### 8. Completeness (Medium)
Check for:
- [ ] EDA section present before modeling
- [ ] Baseline model before complex models
- [ ] Evaluation on held-out test set (not just train or val)
- [ ] Feature importance or model explainability
- [ ] Explicit discussion of limitations and what would change the conclusion

## Output Format

Produce a structured review:

### 🔴 Critical Issues (must fix before sharing)
[Specific issues with cell/line references]

### 🟡 Important Issues (should fix)
[Specific issues]

### 🟢 Suggestions (nice to have)
[Specific suggestions]

### Overall Assessment
- Strengths: [what's done well]
- Readiness: [Not ready / Needs revision / Ready with minor fixes / Ready to share]
- Estimated effort to reach "ready": [Small / Medium / Large]
