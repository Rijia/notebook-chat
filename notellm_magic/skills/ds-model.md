Build a production-quality ML model pipeline. $ARGUMENTS should describe the target variable, problem type (classification/regression), and any domain constraints. Use the dataframe already loaded.

## Requirements

### 1. Feature Engineering
- Create lag features for time-series data (7d, 14d, 30d, 90d, 180d windows)
- Log-transform right-skewed numeric features
- Encode categoricals (target encoding for high-cardinality, one-hot for low)
- Document every feature created and its business rationale

### 2. Data Splitting
- For time-series data: use time-based split, never shuffle. Exclude the most recent period from training to prevent leakage.
- For non-time-series: stratified train/val/test (60/20/20)
- Check class balance in each split; apply `class_weight='balanced'` or SMOTE if imbalance ratio > 5:1

### 3. Baseline
- Fit a simple baseline (majority class, mean predictor, or logistic regression)
- Report baseline metrics before touching any complex model

### 4. Model Training with Hyperparameter Tuning
- Train at minimum: gradient boosting (XGBoost or LightGBM) and one linear model
- Use cross-validated grid search or Optuna for tuning
- Key params to tune for tree models: max_depth, n_estimators, learning_rate, min_child_weight

### 5. Evaluation — Classification
- ROC-AUC on train, val, and test (flag if val/test gap > 0.02)
- Classification report (precision, recall, F1) at default threshold
- Precision-Recall curve (more informative than ROC for imbalanced problems)
- Gains/Lift table: show lift at top 10%, 20%, 30% of population
- Confusion matrix

### 5. Evaluation — Regression
- RMSE, MAE, MAPE on train/val/test
- Residual plot (predicted vs actual, residuals vs predicted)
- Flag if residuals are heteroscedastic

### 6. Feature Importance
- Plot top 20 features by importance (permutation importance preferred over impurity)
- Group related features and comment on which domains drive the model
- Flag features that could be proxies for protected attributes

### 7. Business Impact Statement
Produce:
- "By targeting the top X% of [predicted churners / converters / etc.], we capture Y% of actual positives with Z% precision"
- Expected revenue impact or cost savings with pessimistic/base/optimistic scenarios

## Code Standards
- All steps in functions; main pipeline callable end-to-end
- Seed everything (`random_state=42`)
- Save model artifact and feature list to disk
- No data leakage: fit scalers/encoders on train only, transform val/test

## Plotting Standards
Apply these principles to every chart generated in this analysis:

**Chart type**
- Use line charts for ROC and Precision-Recall curves (these are continuous thresholds — not bars)
- Use scatter plots for residuals vs. predicted; keep points small and semi-transparent if the dataset is large (alpha ≈ 0.3)
- Avoid 3D effects and dual y-axes
- For feature importance, use horizontal bar charts sorted descending by importance value

**Axes**
- Bar charts: value axis MUST start at zero
- ROC/PR curves: fix both axes to [0, 1] so curves are comparable across models
- Residual plots: draw a horizontal reference line at y=0

**Labels and titles**
- Titles state the finding ("XGBoost outperforms baseline by 8 AUC points" not "ROC Curve")
- Annotate the AUC value directly on the ROC chart; annotate the AP on the PR chart
- Label the baseline (majority class / mean predictor) as a dashed reference line

**Color**
- Use a consistent color per model across all evaluation charts
- Default to seaborn's `colorblind` palette or matplotlib's `tab10`

## Model Checking and Validation

### Start Simple, Fit Many Models
Always begin with a simple baseline (mean predictor, logistic regression, or linear model). Add complexity incrementally. Each model should be interpretable enough to check. Never jump to gradient boosting without understanding what the baseline gets right and wrong.

### Fake-Data Simulation
Before fitting real data, simulate from your assumed data-generating process and verify that your method recovers the true parameters. This builds intuition and catches implementation bugs before they're invisible in real data.

### Residual Diagnostics (Required for All Models)
After fitting, systematically check residuals:
- Plot predicted vs. actual: look for bias at the tails, non-linearity, heteroscedasticity
- Plot residuals vs. each key predictor: any remaining pattern indicates model misspecification
- Plot residuals over time if temporal structure exists: autocorrelation is a common unmodeled structure
- For probabilistic models, run posterior predictive checks: simulate new outcomes from your model and compare their distribution to the observed data. Ask whether the model generates data that looks like what you actually have.

### Don't Use R² as the Primary Metric
R² conflates the noisiness of the outcome with model quality and is scale-dependent. Prefer:
- **Out-of-sample held-out RMSE/MAE/log-loss** for frequentist models
- **LOO-CV** (leave-one-out cross-validation) for model comparison when a test set is not available
- Report prediction error in original units so practical magnitude is clear

### Report Uncertainty on Model Metrics
Point estimates of accuracy, AUC, or RMSE are not sufficient. Report confidence intervals using bootstrap or CV fold variance. A difference of 0.01 AUC between two models is not meaningful if the CI is ±0.03.

### Regularization by Default
Apply ridge (L2) regularization to all regression-style models. Unregularized models with many features overfit. When in doubt, regularize more than you think you need to.

### Effect Heterogeneity
Fit interaction terms or varying-slope models to detect whether effects differ across key subgroups. "Anything that affects anyone affects different people differently." Detecting heterogeneity requires ~16× the sample size of detecting the average effect — if the data allow it, fit the interactions and report the distribution of effects.

## Integration

### Feature Pipeline
- Define and document feature schemas (names, types, expected ranges) in code
- Features used at training time must be reproducible at inference time from the same upstream data. Validate that train-time and serve-time feature logic are identical
- Flag features derived from post-event data (future leakage): they will not be available at inference time
- Store feature transformation logic (scalers, encoders) as serialized artifacts alongside the model

### Serving Architecture
- Decide early: **batch** (scheduled scoring, results written to a table) vs. **real-time** (online API, latency < 200ms). The choice affects feature engineering constraints
- For real-time: enforce a latency budget and test under realistic load. Cache or precompute expensive features
- For batch: make the scoring pipeline idempotent — re-running should produce the same output without double-writing

### Rollout
- Ship via **shadow mode** first (model scores in production but decisions are not acted on): validate prediction distribution matches training distribution before live traffic
- Then **canary rollout**: send 5–10% of traffic through the new model, compare guardrail metrics to baseline before full cutover
- Document the rollback procedure before launch, not after

## Monitoring

### Data Drift (Input)
Monitor the distribution of each input feature in production against the training distribution:
- Track mean, variance, and null rate weekly per feature
- Alert when any feature shifts by > 2 standard deviations from its training baseline
- Categorical features: track the rate of novel/unseen values
- Investigate upstream data pipeline changes before retraining

### Prediction Drift (Output)
- Track the distribution of model scores (predicted probabilities or values) over time
- A shift in score distribution that precedes a metric change is an early warning signal
- For classification: monitor the positive rate (fraction of users/events classified as positive)

### Model Performance (Outcome Labels)
- If ground truth labels are available with a delay (e.g., 7-day conversion), compute held-out accuracy/AUC/RMSE weekly as labels arrive
- Set alert thresholds based on the variance observed during the post-launch shadow period, not on an arbitrary percentage
- Define a **retraining trigger**: e.g., "retrain if 7-day rolling AUC drops below [threshold] for 2 consecutive weeks"

### Logging
- Log every prediction with: timestamp, entity ID, feature values (or a feature hash), model version, and score
- Retain prediction logs for at least the full outcome observation window so you can reconstruct accuracy at any past point
- Never overwrite logs; append-only
