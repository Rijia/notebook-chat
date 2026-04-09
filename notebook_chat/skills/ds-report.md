Generate a polished, executive-ready report from the analysis in $ARGUMENTS (notebook or script path), or summarize the current notebook session if no argument given.

The report should be structured for a technical manager or cross-functional stakeholder — not too deep in math, but rigorous enough to be trustworthy.

## Report Structure

### Executive Summary (≤ 5 bullet points)
- What was the question?
- What data was used (size, time range, source)?
- What is the single most important finding?
- What is the recommended action?
- What is the estimated business impact?

### Background & Objective
- Business context: why does this matter?
- Success criteria: how will we know if we succeeded?

### Methodology (concise)
- Data sources and preprocessing steps taken
- Analytical approach and why it was chosen (not just what)
- Key assumptions made

### Results
- Primary findings with numbers and confidence ranges
- Supporting visualizations (reference the key charts by name)
- Segment or subgroup findings where relevant

### Business Impact
- Quantified impact: revenue, cost, conversion rate, retention, etc.
- Time horizon for the impact
- Sensitivity: how does the impact change if assumptions are off by 20%?

### Limitations & Risks
- What could make these findings wrong?
- What data was unavailable or imperfect?
- What would need to be true for the recommendation to fail?

### Recommendation & Next Steps
- Clear ship / don't ship / run follow-up decision
- If launching: target audience, rollout plan, guardrail metrics to monitor
- If more work needed: specific next analyses with expected value of information

## Formatting Rules
- Write in plain English; define any statistical term you use
- Every number should have a unit and context ("21% relative lift in 7-day signup rate, from 4.2% to 5.1%")
- No unexplained p-values or model metrics in the executive summary
- Maximum 2 pages equivalent of text; use tables and bullets liberally
- Output as markdown

## Uncertainty, Causation, and Communication Standards

### Always Report Estimates + Intervals
Never report only significance or a p-value. Every numerical claim must include: the estimate, its uncertainty interval, and the unit. "Statistically significant" is not a result — "21% relative lift in 7-day signup rate [95% CI: 8%–35%]" is.

### State the Estimand
Be explicit about what quantity is being reported and for whom:
- Is this an average treatment effect for the full population, or a conditional effect for a specific segment?
- Is this in-sample fit, or out-of-sample generalization?
- What is the time horizon?

Unstated estimands lead to overgeneralized conclusions and bad decisions.

### Forward vs. Reverse Causation
Distinguish between:
- **Forward causal questions** ("what does this feature change do to retention?"): answerable with a well-designed experiment; state the experimental design
- **Reverse causal questions** ("why did retention drop last month?"): these are hypothesis-generation, not causal estimation; label them as such and recommend a prospective test

Never write "X caused Y" from observational data without acknowledging the assumption. Write "X is associated with Y; our best causal interpretation is..." and note what would need to be true for that interpretation to hold.

### External Validity
State explicitly for whom and in what context these findings apply. An experiment run on power users in one country may not generalize to new users globally. A model trained on last year's data may not apply to next quarter's cohort. Flag any known gaps between the analysis sample and the deployment population.

### Winner's Curse Caveat
If the analysis rests on a single significant experiment or a model selected from many candidates: note that the first significant result systematically overstates the true effect due to the significance filter. Recommend replication or a follow-on holdout before scaling decisions.
