Perform a comprehensive, staff-level exploratory data analysis on the current dataset (use whatever dataframe/data is already loaded in the notebook, or load from $ARGUMENTS if a file path is given).

## Requirements

### 1. Data Overview
- Shape, dtypes, memory usage
- Missing value counts and percentages per column
- Duplicate rows
- Cardinality of categorical columns

### 2. Distribution Analysis
- Histograms + KDE for all numeric columns
- Value counts (top 10) for categorical columns
- Log-transform skewed distributions and show side-by-side comparison
- Flag extreme outliers (>3 IQR) with counts and examples

### 3. Temporal Analysis (if date/time columns exist)
- Parse and identify the time grain (daily, weekly, monthly)
- Plot time series of key metrics
- Check for seasonality, gaps, or anomalies
- Show cohort sizes over time to check for survivorship bias

### 4. Relationships
- Correlation heatmap for numeric columns (use Spearman for non-normal)
- Scatter plots for top correlated pairs with the target variable (if one exists)
- Pair plot colored by a key categorical variable if available

### 5. Segment Cuts (if group columns exist)
- Compare key metric distributions across segments using violin or KDE plots
- Flag segments with very different missingness or outlier rates

### 6. Actionable Summary
End with a markdown table:
| Finding | Severity | Recommended Action |
|---------|----------|-------------------|

Flag: data leakage risks, class imbalance, data freshness issues, inconsistent units, columns that should be dropped before modeling.

## Code Standards
- Write modular helper functions, no copy-pasted blocks
- Use `flush=True` on all prints
- All plots must have titles, axis labels, and legible font sizes (minimum 12pt)
- Save figures to `eda_output/` folder if it exists, otherwise display inline

## Plotting Standards
Apply these principles to every chart generated in this analysis:

**Chart type**
- Prefer bar charts over pie charts — bar lengths are judged far more accurately than angles
- Avoid 3D effects and dual y-axes — they distort without adding information
- For comparing distributions across many groups, use overlaid KDE or violin plots, not stacked bars
- For rank changes across time, use slope charts rather than grouped bars

**Axes**
- Bar/column charts: value axis MUST start at zero — truncating it exaggerates small differences
- Time on horizontal axis, left to right, with proportional spacing
- Use round tick values (0, 25, 50, 75 — not 13, 26, 39)

**Labels and titles**
- Titles should state the finding, not just the variable ("Churn spikes in month 3" not "Churn by Month")
- Use direct labels on chart elements instead of a legend when there are ≤5 series
- When a legend is required, order entries to match the visual order in the chart

**Color**
- Only use different colors when they encode a meaningful data distinction — don't rainbow-color a single-variable bar chart
- Default to seaborn's `colorblind` palette or matplotlib's `tab10`

**Ordering and context**
- Sort bars by value unless a natural order exists (time, ordinal categories)
- Never sort alphabetically
- Show variability alongside means: add error bars, confidence intervals, or full distributions

## Statistical Awareness

### Graph First, Always
Before computing any numerical summary, make a graph of the raw data. Summary statistics collapse distributions into single numbers that can hide radically different underlying patterns (the Anscombe quartet effect). Identical means, variances, and correlations can arise from data with completely different shapes.

### Variation Is the Signal
Always characterize variation, not just central tendency. Report the full distribution (histogram, KDE, quantiles) alongside the mean. Ask: why does this variable vary? Understanding variation is the central question of statistics.

### Measurement Quality
Note which columns are direct measurements vs. proxies vs. derived. Noisy or biased measurements attenuate effects in downstream modeling (attenuation bias). If a key variable appears to have measurement error (e.g., self-reported income, survey responses), flag it explicitly.

### Multiple Comparisons in Exploration
When scanning a correlation matrix or running many distributional tests, some patterns will be spurious by chance. Flag correlations and anomalies as hypotheses to test, not established facts. Every post-hoc observation requires prospective confirmation.
